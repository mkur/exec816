#!/usr/bin/env python3
"""Physical nonmodal drags, independent recomposition and cancellation checks."""
import argparse
from desktop_mouse import schedule
from bisect import bisect_left
import hashlib
import json
import os
from pathlib import Path
import adapter_state as adapter
from native_program import read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from generate_desktop import layout as desktop_layout
from generate_layers import layout as layer_layout
from gem_render_oracle import Raster, font_bytes, PENS, PALETTE
from bitmap_console_oracle import Terminal
from test_gem_cursor import overlay
from test_desktop_presentation import frame, rectangle, text as paint_text
from sio_transaction_trace import BASE_HZ
from measure_desktop import distribution
from make_data_disk import make


def publication_times(path, pc):
    # Stream long passive traces instead of retaining every timer IRQ tuple.
    result = []
    tick = 0
    with path.open() as source:
        for line in source:
            tag = next((tag for tag in ('[SIOPOC] ', '[SIOTXN] ') if tag in line), None)
            if tag is None:
                continue
            fields = line.split(tag, 1)[1].split()
            value = int(fields[1])
            fraction = 0
            if fields[0] in ('cpu', 'mask'):
                value += round((tick-value)/(1 << 32))*(1 << 32)
                require(int(fields[3]) == 8, 'Observer multiplier changed')
                fraction = int(fields[2])/8
            tick = value
            if fields[0] == 'cpu' and int(fields[4], 16) == pc:
                result.append(value+fraction)
    return result


def run(out, program, count=30, loads=('idle', 'scroll', 'disk')):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    second_app = any('_DESKAPP_WINDOWID_' in d['name'] for d in p['image']['data'])
    source = p['output'].parent
    font = font_bytes(source/'selected/src/vdi/font8x8.c')
    at = lambda module, name: next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    os.environ.update(EXEC816_MOUSE_TRACE='1', EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='0',
        EXEC816_LATENCY_PCS=f'{p["labels"]["pointer_notify"]:x}')
    files = out/'media/TOOLS/SUB'
    files.mkdir(parents=True, exist_ok=True)
    (files/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    make(out/'disk.atr', out/'media', binary_names={'TOOLS/SUB/DATA.BIN'}, filesystem='sdfs')
    report = dict(status='running', tier='development', qualification=False, build=p['build'],
                  second_app=second_app, samples=[], scenes=[], cancellations=[])
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            b.mount(0, str(out/'disk.atr'))
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)
            read = lambda module, name, size=2: int.from_bytes(b.memdump(at(module, name), size), 'little')
            write = lambda module, name, value, size=2: b.memload(at(module, name), value.to_bytes(size, 'little'))
            clock = lambda: b.eval_expr('@clk') & 0xffffffff
            def reach(condition, label='native_nmi'):
                b.bp_clear_all()
                marker = p['labels'][label]
                b.bp_set(marker, condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                original = b.regs
                def registers():
                    regs = original()
                    if int(regs['PC'].lstrip('$'), 16) == p['labels']['done']:
                        require(b.peek16(adapter.STATE) == 65535, 'Guest stopped: '+str(b.peek16(adapter.STATE)))
                    return regs
                b.regs = registers
                try:
                    run_to(b, marker, condition=condition, frame_limit=12000, timeout=150)
                finally:
                    b.regs = original
            def frames(n=1):
                reach(f'@frame>={b.eval_expr("@frame")+n}', 'native_irq')
            service = scene = 0
            position = [320, 120]
            shell = [32, 24, 560, 208]
            panel = [440, 80, 624, 224]
            graphical = False
            app_behind_shell = False
            app_live = second_app
            def bounds(slot=0):
                address = scene+layer_layout()['Scene']['fields']['items']+slot*layer_layout()['Layer']['size']+4
                return [int.from_bytes(b.memdump(address+i*2, 2), 'little', signed=True) for i in range(4)]
            def raster(outline=None):
                model = Raster(font)
                rectangle(model, (0, 0, 640, 240), 8)
                focused = int.from_bytes(b.memdump(service+desktop_layout()['Service']['fields']['focus'], 4), 'little')
                def application():
                    frame(model, (432,80,624,224), b'Exec816 App', focused == 3, 15, close=True)
                    for y, value in ((104,b'Independent Task'), (120,b'Key/click: compute'), (136,b'Close: retire')):
                        paint_text(model,448,y,value,bg=15)
                    rectangle(model,(448,160,608,184),2+(read('DESKAPP','updates') & 3))
                if app_live and app_behind_shell:
                    application()
                frame(model, shell, b'Exec816 Shell', focused == 1)
                terminal = Terminal(64, 20)
                text = bytes(10 if i & 63 == 63 else 65+i % 26 for i in range(512))
                for _ in range(1+read('DESKTEST', 'writes')):
                    terminal.feed(text)
                terminal.paint(model, (shell[0]+8)//8, (shell[1]+16)//8, caret=focused == 1)
                if app_live and not app_behind_shell:
                    application()
                if graphical:
                    frame(model, panel, b'Input', focused == 2, close=True)
                if outline is not None:
                    l, t, r, bot = outline
                    for x in range(l, r):
                        model.pixels[t*640+x] ^= 15
                        model.pixels[(bot-1)*640+x] ^= 15
                    for y in range(t+1, bot-1):
                        model.pixels[y*640+l] ^= 15
                        model.pixels[y*640+r-1] ^= 15
                return overlay(model, position)
            colors = {hw: bytes((v & 254)+(v >> 7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen, hw in enumerate(PENS)}
            def visible(outline=None, whole=True):
                # A steady background margin is insufficient for XOR outlines:
                # compare the entire retained scene whenever the model is idle.
                expected = raster(outline)
                golden = b''.join(colors[v >> 4]+colors[v & 15] for v in expected)
                selected = None
                if not whole:
                    # The scrolling client interior changes independently. The
                    # frame/background remain an exact oracle for the outline.
                    selected = [i for y in range(240) for x in range(640)
                                if not (shell[0]+8 <= x < shell[2]-8
                                        and shell[1]+16 <= y < shell[3]-8)
                                for i in range((y*640+x)*3, (y*640+x)*3+3)]
                    golden = bytes(golden[i] for i in selected)
                for attempt in range(200):
                    f = b.rawscreen(str(out/'scanout.bgra'))
                    raw = (out/'scanout.bgra').read_bytes()
                    actual = b''.join(raw[y*f.stride+64:y*f.stride+2624] for y in range(240))
                    rgb = b''.join(actual[i:i+3] for i in range(0, len(actual), 4))
                    if selected is not None:
                        rgb = bytes(rgb[i] for i in selected)
                    if rgb == golden:
                        return dict(clock=clock(), sha256=hashlib.sha256(rgb).hexdigest(), observations=attempt+1)
                    frames()
                b.screenshot(str(out/'failure.png'))
                raise RuntimeError('No exact drag scene; bounds='+str(bounds())+' expected='+str(shell)+' phase='+str(read('DESKDRAG','phase',1)))
            def move(x, y):
                nonlocal position
                start = clock()
                x,y=schedule(b,p,position,(x,y))
                reach(f'(dw(${at("DESKINPUT", "cursorX"):x})={x})&(dw(${at("DESKINPUT", "cursorY"):x})={y})', 'native_irq')
                position = [x, y]
                return start, clock()
            def button(down):
                nonlocal app_behind_shell
                # The fixture presses the shell title to raise it, and later
                # raises its separate Input panel. Track that expected stacking
                # independently instead of reading the target's layer order.
                if down and shell[0] <= position[0] < shell[2] and shell[1] <= position[1] < shell[1]+16:
                    app_behind_shell = True
                start = clock()
                b._cmd_ok(f'MOUSE AT 2000 0 0 {1 if down else 0}')
                reach(f'dw(${at("DESKINPUT", "buttons"):x})={1 if down else 0}', 'native_irq')
                return start, clock()
            def target_at(origin, press, point):
                width, height = origin[2]-origin[0], origin[3]-origin[1]
                x = min((640-width) & ~7, (max(0, origin[0]+point[0]-press[0])+4) & ~7)
                y = min((240-height) & ~7, (max(0, origin[1]+point[1]-press[1])+4) & ~7)
                return [x, y, x+width, y+height]
            def before(bridge):
                nonlocal service, scene, shell, panel, graphical, app_live
                b.profile_start()
                reach(f'dw(${at("DESKTEST", "ready"):x})=1')
                service = read('DESKSTATE', 'service', 3)
                scene = service+desktop_layout()['Service']['fields']['scene']
                visible()
                for load in loads:
                    for n in range(count):
                        origin = list(shell)
                        press = [shell[0]+40, shell[1]+6]
                        move(*press)
                        if load != 'idle':
                            write('DESKTEST', 'mode', 2 if load == 'scroll' else 3)
                            reach(f'dw(${at("DESKTEST", "runningMode"):x})={2 if load == "scroll" else 3}')
                            frames(4)
                        button(True)
                        reach(f'db(${at("DESKDRAG", "phase"):x})=1', 'native_irq')
                        sign = 1 if n % 2 == 0 else -1
                        outline = origin
                        for dx, dy in [(8*sign, 0), (0, 8*sign), (-8*sign, 0), (8*sign, 0)]:
                            start, consumed = move(position[0]+dx, position[1]+dy)
                            outline = target_at(origin, press, position)
                            item = dict(load=load, kind='outline', submitted=start, consumed=consumed, target=outline)
                            item['visible'] = visible(outline, whole=load == 'idle')['clock']
                            report['samples'].append(item)
                        start, consumed = button(False)
                        # Stop the producer for a reproducible complete-scene
                        # oracle, draining any write already in flight.
                        write('DESKTEST', 'mode', 0)
                        reach(f'db(${at("DESKDRAG", "phase"):x})=0', 'native_irq')
                        committed = clock()
                        require(bounds() == outline, 'Release geometry differs from clamped/grid oracle')
                        shell = outline
                        reach(f'dw(${at("DESKTEST", "runningMode"):x})=0')
                        frames(2)
                        item = dict(load=load, kind='release', submitted=start, consumed=consumed,
                                    committed=committed, target=outline)
                        picture = visible()
                        item['visible'] = picture['clock']
                        report['samples'].append(item)
                        report['scenes'].append(picture)
                        if n % 5 == 0:
                            print(load, n, flush=True)
                # Captured motion outside the title clamps both screen edges.
                for destination in ((639, 239), (0, 0)):
                    print('edge', destination, flush=True)
                    origin = list(shell)
                    press = [shell[0]+40, shell[1]+6]
                    move(*press)
                    button(True)
                    move(*destination)
                    target = target_at(origin, press, position)
                    button(False)
                    reach(f'db(${at("DESKDRAG", "phase"):x})=0', 'native_irq')
                    require(bounds() == target, 'Screen-edge clamp differs')
                    shell = target
                    report['scenes'].append(visible())
                print('cancellation cases', flush=True)
                # Escape cancels a held drag; later motion cannot commit it.
                move(shell[0]+40, shell[1]+6)
                button(True)
                move(position[0]+16, position[1]+8)
                b._cmd_ok('KEY ESC down')
                reach(f'db(${at("DESKDRAG", "phase"):x})=0')
                b._cmd_ok('KEY ESC up')
                move(position[0]-8, position[1])
                button(False)
                require(bounds() == shell, 'Escape committed a move')
                report['cancellations'].append(dict(kind='escape', scene=visible()))
                if app_live:
                    # The independent app completely covers the fixture's
                    # smaller Input panel. Retire it through its real close
                    # gadget before exercising that panel's slow consumer.
                    move(616,87)
                    button(True)
                    frames(2)
                    button(False)
                    reach(f'db(${at("DESKAPP", "finished"):x})=1')
                    app_live=False
                    report['cancellations'].append(dict(kind='independent_app_close',scene=visible()))
                # A slow graphical event consumer fills the real native queue.
                write('DESKTEST', 'mode', 4)
                reach(f'dw(${at("DESKTEST", "runningMode"):x})=4')
                frames(40)
                graphical = True
                move(panel[2]-40, panel[1]+6)
                button(True)
                reach(f'db(${at("DESKDRAG", "phase"):x})=1', 'native_irq')
                move(position[0]+8, position[1]+8)
                write('DESKTEST', 'holdEvents', 1, 1)
                old_loss = read('DESKSTATE', 'lossGeneration', 4)
                for i in range(20):
                    key = chr(65+i)
                    b._cmd_ok(f'KEY {key} down')
                    frames(3)
                    b._cmd_ok(f'KEY {key} up')
                    frames(3)
                if read('DESKSTATE', 'lossGeneration', 4) == old_loss:
                    print('Queue loss debug', {n: read('DESKTEST',n) for n in ('eventCount','keyCount','lastKind','cancelCount')}, 'held',read('DESKTEST','holdEvents',1), 'phase',read('DESKDRAG','phase',1), flush=True)
                require(read('DESKSTATE', 'lossGeneration', 4) != old_loss, 'No queue loss boundary exercised')
                require(read('DESKDRAG', 'phase', 1) == 0, 'Queue loss left gesture armed')
                button(False)
                write('DESKTEST', 'holdEvents', 0, 1)
                frames(4)
                require(bounds(1) == panel, 'Loss committed a move')
                report['cancellations'].append(dict(kind='event_queue_loss', scene=visible()))
                # The close gadget requests retirement; this fixture refuses.
                move(panel[2]-8, panel[1]+7)
                button(True)
                frames(2)
                button(False)
                reach(f'dw(${at("DESKTEST", "lastKind"):x})=5')
                require(bounds(1) == panel, 'Close gadget forcibly removed the window')
                report['cancellations'].append(dict(kind='cooperative_close_refused', scene=visible()))
                # Hiding a captured window cancels without moving it.
                move(panel[2]-40, panel[1]+6)
                button(True)
                move(position[0]+8, position[1]+8)
                write('DESKTEST', 'mode', 0)
                reach(f'dw(${at("DESKTEST", "runningMode"):x})=0')
                reach(f'db(${at("DESKDRAG", "phase"):x})=0')
                require(bounds(1) == panel, 'Hide committed a move')
                button(False)
                graphical = False
                report['cancellations'].append(dict(kind='hide', scene=visible()))
                # Retirement also cancels a held gesture, and shutdown releases
                # the source while the physical button remains pressed.
                move(shell[0]+40, shell[1]+6)
                button(True)
                move(position[0]+8, position[1]+8)
                write('DESKTEST', 'mode', 9)
                report['cancellations'].append(dict(kind='retirement_while_held'))
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, timeout=180, frame_limit=12000)
            b.profile_stop()
            ownership(b, p, p['output'])
        notify = publication_times(out/'emulator.log', p['labels']['pointer_notify'])
        for item in report['samples']:
            align = lambda value: value+round((notify[0]-value)/(1 << 32))*(1 << 32)
            captures = [t for t in notify if align(item['submitted']) <= t <= align(item['consumed'])]
            require(captures, 'Missing physical gesture capture')
            item['capture_cycle'] = captures[-1]
            for endpoint in ('committed', 'visible'):
                if endpoint in item:
                    item['capture_to_'+endpoint+'_ms'] = (align(item[endpoint])-captures[-1])/BASE_HZ*1000
        report['timing'] = {load: distribution([s['capture_to_visible_ms'] for s in report['samples'] if s['load'] == load and s['kind'] == 'release']) for load in loads}
        report['outline_timing'] = {load: distribution([s['capture_to_visible_ms'] for s in report['samples'] if s['load'] == load and s['kind'] == 'outline']) for load in loads}
        report['repair_target_pass'] = all(v['max_ms'] <= 250 for v in report['timing'].values())
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=30)
    parser.add_argument('--loads', nargs='+', choices=('idle', 'scroll', 'disk'), default=['idle', 'scroll', 'disk'])
    args = parser.parse_args()
    run(args.output.resolve(), args.program, args.count, args.loads)
