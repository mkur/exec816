#!/usr/bin/env python3
"""Independent Task client, two-window pixels and reverse retirement."""
import argparse
from desktop_mouse import schedule
from control_panel_oracle import panel
import hashlib
import json
import os
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from gem_render_oracle import Raster, font_bytes, PALETTE, PENS
from bitmap_console_oracle import Terminal
from test_desktop_presentation import rectangle, text, frame
from test_gem_cursor import overlay
from generate_desktop import layout
from desktop_budget import delta


def run(out, mode, existing=None, cases=(0, 1), prepare=None):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(existing) if existing else build_bitmap(ROOT/'tests/programs/desktop_apps.act',
        out/'build', optimize=mode == 'opt', desktop=True, stack_checks=True)
    resident = (p['output']/'hosted.bin').read_bytes()
    fault_offset = p['labels']['heap_fault']-p['build']['memory']['regions']['resident'][0]
    fault_stored = int.from_bytes(resident[fault_offset+3:fault_offset+5], 'little')+4
    font = font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
    at = lambda module, name: next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    report = dict(status='running', tier='development', qualification=False, mode=mode,
                  build=p['build'], reserved_bank_zero_delta=delta(p['build']['memory']), cases=[])
    try:
        for reverse in cases:
            case = dict(reverse=bool(reverse), scenes=[])
            directory = out/('shell-first' if reverse else 'app-first')
            directory.mkdir(exist_ok=True)
            with emulator(BRIDGE, ROM, directory, pin=PIN) as b:
                b._cmd_ok('MOUSE ST')
                report['machine'] = verify_machine(b, ROM, PIN)
                read = lambda mod, name, size=2: int.from_bytes(b.memdump(at(mod, name), size), 'little')
                def reach(condition):
                    b.bp_clear_all()
                    marker = p['labels']['native_irq']
                    b.bp_set(marker, condition=condition)
                    b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                    b.bp_set(fault_stored, condition=adapter.STOPPED)
                    original = b.regs
                    def registers():
                        regs = original()
                        if int(regs['PC'].lstrip('$'), 16) == fault_stored and b.peek16(adapter.STATE) != 65535:
                            raise RuntimeError('Native termination: '+hex(b.peek16(adapter.STATE))+' stage='+str(read('DESKAPPS','stage')))
                        if int(regs['PC'].lstrip('$'), 16) == p['labels']['done']:
                            require(b.peek16(adapter.STATE) == 65535, 'Guest stopped: '+str(b.peek16(adapter.STATE)))
                        return regs
                    b.regs = registers
                    try:
                        run_to(b, marker, condition=condition, frame_limit=6000, timeout=120)
                    finally:
                        b.regs = original
                def frames(n=1):
                    reach(f'@frame>={b.eval_expr("@frame")+n}')
                position = [320, 120]
                shell_live = True
                panel_live = True
                focused = 1
                terminal = Terminal(64, 20)
                terminal.feed(b'Shell alive')
                def move(x, y):
                    nonlocal position
                    x,y=schedule(b,p,position,(x,y))
                    reach(f'(dw(${at("DESKINPUT", "cursorX"):x})={x})&(dw(${at("DESKINPUT", "cursorY"):x})={y})')
                    position = [x, y]
                def click(x, y):
                    move(x, y)
                    for down in (1, 0):
                        b._cmd_ok(f'MOUSE AT 2000 0 0 {down}')
                        reach(f'dw(${at("DESKINPUT", "buttons"):x})={down}')
                        frames(2)
                colors = {hw: bytes((v & 254)+(v >> 7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen, hw in enumerate(PENS)}
                def picture(label):
                    raster = Raster(font)
                    rectangle(raster, (0, 0, 640, 240), 8)
                    if shell_live:
                        frame(raster, (32, 24, 560, 208), b'Exec816 Shell', focused == 1)
                        terminal.paint(raster, 5, 5, focused == 1)
                    if panel_live:
                        panel(raster, focused == 2, status='Large [5]' if read('DESKAPP', 'updates') else 'Ready',
                              radio=5 if read('DESKAPP', 'updates') else 4,
                              focus=5 if read('DESKAPP', 'updates') else 2)
                    expected = overlay(raster, position)
                    golden = b''.join(colors[v >> 4]+colors[v & 15] for v in expected)
                    for n in range(1500):
                        f = b.rawscreen(str(directory/'scanout.bgra'))
                        raw = (directory/'scanout.bgra').read_bytes()
                        actual = b''.join(raw[y*f.stride+64:y*f.stride+2624] for y in range(240))
                        rgb = b''.join(actual[i:i+3] for i in range(0, len(actual), 4))
                        if rgb == golden:
                            case['scenes'].append(dict(label=label, sha256=hashlib.sha256(rgb).hexdigest(), observations=n+1))
                            return
                        frames()
                    b.screenshot(str(directory/'failure.png'))
                    case['app_failure']={name:read('DESKAPP',name,size) for name,size in (('updates',2),('lastObject',2),('refresh',1),('snapshot',3),('windowId',4),('tree',3),('patch',3))}
                    case['app_failure']['snapshot_bytes']=b.memdump(read('DESKAPP','snapshot',3),140).hex()
                    report['failed_case']=case
                    raise RuntimeError('Two-client recomposition differs: '+label)
                def before(bridge):
                    nonlocal shell_live, panel_live, focused
                    if os.environ.get('EXEC816_LATENCY_TRACE'):
                        b.profile_start()
                    if prepare is not None:
                        prepare(b,p)
                    b.poke(at('DESKAPPS', 'reverse'), reverse)
                    reach(f'dw(${at("DESKAPPS", "stage"):x})=1')
                    service = read('DESKSTATE', 'service', 3)
                    owner = int.from_bytes(b.memdump(service+layout()['Service']['fields']['owner'], 3), 'little')
                    client_owner = int.from_bytes(b.memdump(at('DESKAPP', 'client')+layout()['Client']['fields']['owner'], 3), 'little')
                    require(owner != client_owner and client_owner != read('DESKAPP', 'parent', 3), 'App is not an independent Task')
                    case['owners'] = dict(presenter=owner, app=client_owner, shell=read('DESKAPP', 'parent', 3))
                    picture('overlapping app, focused shell')
                    click(584, 160)
                    focused = 2
                    reach(f'dw(${at("DESKAPP", "updates"):x})>=1')
                    picture('semantic action and status patch')
                    old = read('DESKAPP', 'updates')
                    b._cmd_ok('KEY SPACE down')
                    reach(f'dw(${at("DESKAPP", "updates"):x})>{old}')
                    b._cmd_ok('KEY SPACE up')
                    frames(4)
                    picture('graphical keyboard route')
                    b.poke16(at('DESKAPPS', 'advance'), 1)
                    reach(f'dw(${at("DESKAPPS", "stage"):x})=2')
                    terminal.feed(b'\nBehind the panel')
                    picture('console output behind app')
                    if reverse:
                        b.poke16(at('DESKAPPS', 'advance'), 2)
                        reach(f'dw(${at("DESKAPPS", "stage"):x})=3')
                        shell_live = False
                        picture('shell retired, app remains live')
                        old = read('DESKAPP', 'updates')
                        b._cmd_ok('KEY SPACE down')
                        reach(f'dw(${at("DESKAPP", "updates"):x})>{old}')
                        b._cmd_ok('KEY SPACE up')
                        picture('app works after shell retirement')
                        b.poke16(at('DESKAPPS', 'advance'), 3)
                        panel_live = False
                        focused = 0
                    else:
                        click(616, 87)
                        reach(f'db(${at("DESKAPP", "finished"):x})=1')
                        panel_live = False
                        focused = 0
                        picture('cooperative app close exposes shell')
                        b.poke16(at('DESKAPPS', 'advance'), 2)
                    reach(f'dw(${at("DESKAPPS", "stage"):x})=4')
                    picture('retirement settled')
                    b.poke16(at('DESKAPPS', 'advance'), 4)
                    b.bp_clear_all()
                case['runtime'], _ = execute(b, p, before_run=before, timeout=180, frame_limit=10000)
                ownership(b, p, p['output'])
                case['checks'] = read('DESKAPPS', 'checks')
            report['cases'].append(case)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--case', choices=('both', 'app-first', 'shell-first'), default='both')
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.from_build, (0, 1) if args.case == 'both' else (int(args.case == 'shell-first'),))
