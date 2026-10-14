#!/usr/bin/env python3
"""Compare the worker-hosted desktop with an independent complete raster."""
import argparse
import json
import os
import generate_tasks
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data
from gem_render_oracle import Raster, font_bytes, PENS
from bitmap_console_oracle import Terminal
from gem_render_oracle import DESKTOP_PALETTE
from test_gem_interactive import pixels
from test_gem_cursor import overlay
from desktop_budget import delta as desktop_delta
from generate_memory import PROFILE
from generate_desktop import layout as desktop_layout
from generate_layers import layout as layers_layout
from stack_budget import bank_zero_delta, stack_usage


def rectangle(raster, bounds, pen):
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        for x in range(left, right):
            raster.pixel(x, y, pen)


def text(raster, x, y, value, fg=1, bg=0):
    for index, char in enumerate(value):
        for row in range(8):
            for col in range(8):
                raster.pixel(x + index*8 + col, y + row,
                             fg if raster.font[row*256+char] & (128 >> col) else bg)


def desktop(raster):
    # The desktop is a flat neutral field; titles retain their own pattern.
    for y in range(240):
        for x in range(640):
            raster.pixels[y*640+x]=PENS[8]


def frame(raster, bounds, title, focused, background=0, close=False, kind=0, slider=(0,0), info=b''):
    x, y, right, bottom = bounds
    rectangle(raster, bounds, 0)
    def box(l,t,r,b):
        rectangle(raster,(l,t,r,t+1),1)
        rectangle(raster,(l,b-1,r,b),1)
        rectangle(raster,(l,t+1,l+1,b-1),1)
        rectangle(raster,(r-1,t+1,r,b-1),1)
    box(x,y,right,bottom)
    rectangle(raster,(x,y+15,right,y+16),12 if focused else 1)
    name_left=x+(16 if close else 1)
    icon_right=right-(16 if kind&4 else 0)
    name_right=icon_right-(16 if right-x>=64 else 1)
    title=title[:max(0,min(64,(name_right-name_left-4)//8))]
    tx=name_left+(name_right-name_left-len(title)*8)//2
    if focused:
        for py in range(y+1,y+15):
            for px in range(name_left,name_right):
                if (px-x)&1 and (py-y)&1: raster.pixel(px,py,1)
    if title:
        rectangle(raster,(tx-2,y+1,tx+len(title)*8+2,y+15),0)
        text(raster,tx,y+4,title,fg=12 if focused else 1)
    if close:
        box(x+1,y+1,x+15,y+15)
        text(raster,x+4,y+4,bytes([5]))
    if right-x>=64:
        box(icon_right-16,y+1,icon_right-1,y+15)
        box(icon_right-12,y+4,icon_right-4,y+12)
        rectangle(raster,(icon_right-8,y+8,icon_right-5,y+11),1)
    if kind&4:
        box(right-16,y+1,right-1,y+15)
        text(raster,right-12,y+4,bytes([7]))
    wt=28 if kind&16 else 16
    if kind&16:
        rectangle(raster,(x,y+27,right,y+28),1)
        text(raster,x+8,y+18,info[:min(64,(right-x-16)//8)])
    wr=16 if kind&448 else 8
    wb=16 if kind&32 else 8
    rectangle(raster,(x+8,y+wt,right-wr,bottom-wb),background)
    if kind&448:
        l,t,b=right-16,y+wt,bottom-wb
        rectangle(raster,(l,t,right,b),8)
        if kind&64:
            rectangle(raster,(l,t,right,t+16),0);box(l,t,right,t+16)
            for dy in range(5):rectangle(raster,(l+8-dy,t+5+dy,l+9+dy,t+6+dy),1)
            t+=16
        if kind&128:
            rectangle(raster,(l,b-16,right,b),0);box(l,b-16,right,b)
            for dy in range(5):rectangle(raster,(l+8-dy,b-6-dy,l+9+dy,b-5-dy),1)
            b-=16
        box(l,t,right,b)
        if kind&256:
            t=y+slider[0];b=t+slider[1]
            rectangle(raster,(l+1,t,right-1,b),0);box(l,t,right,b)
    if kind&32:
        box(right-16,bottom-16,right,bottom)
        for distance in (3,6,9):
            for step in range(distance):raster.pixel(right-3-step,bottom-3-distance+step,1)


def tile(raster, bounds, title):
    x,y,right,bottom=bounds
    rectangle(raster,bounds,0)
    for l,t,r,b in [(x,y,right,y+1),(x,bottom-1,right,bottom),
                    (x,y+1,x+1,bottom-1),(right-1,y+1,right,bottom-1),
                    (x+4,y+3,x+16,y+4),(x+4,y+12,x+16,y+13),
                    (x+4,y+4,x+5,y+12),(x+15,y+4,x+16,y+12)]:
        rectangle(raster,(l,t,r,b),1)
    rectangle(raster,(x+5,y+4,x+15,y+6),12)
    text(raster,x+20,y+4,title[:8])


def menu_bar(raster, title=b'Shell'):
    rectangle(raster,(0,0,640,16),0)
    text(raster,8,4,title[:14])
    text(raster,568,4,b'Windows')
    rectangle(raster,(0,15,640,16),1)


def scenes(font, accepted=None, full_coverage=False):
    terminal = Terminal(64, 20)
    terminal.feed(b'ABC')
    for stage in range(1, 20):
        if stage == 2:
            for row in range(25):
                terminal.feed(bytes(33+(row*7+col) % 90 for col in range(64)))
        if stage == 5:
            terminal.feed(b'\x0cHello')
        if stage == 16:
            for row in range(25):
                terminal.feed(bytes(33+(row*11+col) % 90 for col in range(64)))
        if stage == 17:
            terminal.feed(bytes(10 if col % 7 == 6 else 65+col % 26
                                for col in range(512)))
        if stage == 19:
            if accepted is None:
                yield None
                continue
            terminal.feed(b'\x0c'+b'\n'*13)
            terminal.feed(bytes(65+col % 26 for col in range(accepted)))
        raster = Raster(font)
        desktop(raster)
        left, top = (32, 24) if stage < 3 else (80, 48)
        frame(raster, (left, top, left+528, top+184), b'Shell', True)
        terminal.paint(raster, (left+8)//8, (top+16)//8, True)
        if stage in (4, 5):
            frame(raster, (113, 93, 273, 173), b'Clip', False, 3, close=True)
            text(raster, 124, 112, b'XYZ', bg=3)
        positions = [(0, 0), (32, 24), (16, 24), (16, 8), (16, 32),
                     (480, 160), (480, 0), (0, 160)]
        if 7 <= stage <= 14:
            x, y = positions[stage-7]
            frame(raster, (x, y, x+160, y+80), b'Clip', False, 3, close=True)
            text(raster, x+11, y+19, b'XYZ', bg=3)
        if stage in (16, 17, 19):
            x,y,r,b=(80,48,608,232) if full_coverage and stage in (16,17) else (377,0,537,173)
            frame(raster, (x,y,r,b), b'Clip', False, 3, close=True)
            text(raster, x+11, y+19, b'XYZ', bg=3)
        menu_bar(raster)
        yield overlay(raster, (320, 120))


def backing_calls(report, out):
    """Analyze an already completed passive trace; no guest rerun is required."""
    from sio_transaction_trace import read_events
    foreign=json.loads((out/'c-image.json').read_text())['symbols']
    marks={name:foreign[name] for name in (
        'GemDrawingText','GemDrawingTextClip','GemDrawingBackingText','GemDrawingCopyStart')}
    entries=[(tick % (1<<32),int(event[4],16)) for tick,event in read_events(out/'emulator.log')
             if event[0]=='cpu']
    for row in report['observations']:
        start,end=row['begin_cycle'],row['end_cycle']
        row['drawing_calls']={name:sum(pc==address and (tick-start)%(1<<32)<(end-start)%(1<<32)
            for tick,pc in entries) for name,address in marks.items()}
        if row['stage'] in (8,9,10,11,12,13,14,15):
            # Screen text includes caret removal and native content/title work;
            # it is not a Shell-restoration counter. Idle exposure must not
            # rebuild any unchanged backing span.
            require(row['drawing_calls']['GemDrawingBackingText']==0,
                'Idle exposure rebuilt Shell backing: '+str(row['stage']))


def run(out, mode, replay=False, observe_moves=False, fragment_fault=False, observe_backing=False, full_coverage=False):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 8192  # Fixture records, separate from the demo's 4 KiB.
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    original = generate_tasks.policy_modules
    def instrument(*args, **kwargs):
        directory = original(*args, **kwargs)
        path = directory/'consoledriver.act'
        source = path.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE SCROLLPROBE\n', 1)
        needle = '  consumed=CONSOLECORE.Feed(instance,'
        require(source.count(needle) == 1, 'Console feed boundary changed')
        source=source.replace(needle, '  SCROLLPROBE.Feed(instance)\n'+needle)
        needle='          CONSOLEDISPLAY.Present(view,instance)'
        require(source.count(needle)==1,'Console text boundary changed')
        source=source.replace(needle,
            '          IF SCROLLPROBE.holdFragment=0 THEN\n            SCROLLPROBE.BeforePresent()\n'+needle+
            '\n            SCROLLPROBE.Presented()\n          FI')
        source=source.replace('IF batch.phase=CONSOLETYPES.BATCH_GATHER THEN\n          again=0',
            'IF batch.phase=CONSOLETYPES.BATCH_GATHER OR SCROLLPROBE.holdFragment<>0 THEN\n          again=0')
        # A backing span may already be retired while its screen copy remains
        # pending. Inject quiesced failure before accepting another prefix.
        source=source.replace('            completeWrite=WriteQuantum(instance,view,entry.unit)',
            '            SCROLLPROBE.BeforePresent()\n            completeWrite=WriteQuantum(instance,view,entry.unit)')
        path.write_text(source)
        include = ROOT/'lib/console/console-batch-display.inc'
        source = include.read_text()
        needle = '  CONSOLEBATCH.Publish(instance,reason)'
        require(source.count(needle) == 1, 'Console batch publication changed')
        target = directory/'scroll-batch.inc'
        target.write_text(source.replace(needle, needle+'\n  SCROLLPROBE.Batch(batch.rows)'))
        path = directory/'consoledisplay.act'
        path.write_text(path.read_text().replace('USE A816MEMORY\n',
            'USE A816MEMORY\nUSE SCROLLPROBE\n', 1).replace(str(include), str(target)))
        return directory
    (out/'scrollprobe.act').write_bytes((ROOT/'tests/programs/scrollprobe.act').read_bytes())
    try:
        generate_tasks.policy_modules = instrument
        p = read_build(out/'program') if replay else build_bitmap(
            ROOT/'tests/programs/desktop_presentation.act', out, mode == 'opt', desktop=True, memory_profile=memory)
    finally:
        generate_tasks.policy_modules = original
    require(p['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
    report = dict(status='running', tier='development', qualification=False, slice='DT2',
                  fragment_fault=fragment_fault, full_coverage=full_coverage,
                  build=p['build'], observations=[], move_transactions=[], bank_zero_delta=bank_zero_delta(p['build']['memory']),
                  reserved_bank_zero_delta=desktop_delta(p['build']['memory']))
    address = lambda name: next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+name+'_' in d['name'])
    if observe_moves:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        from bitmap_console_performance import native_markers
        from console_turn_profile import flat_markers
        spans=native_markers(p,[('CONSOLEBITMAP_COPYSTART','copy'),('CONSOLEBITMAP_POLL','poll'),
            ('CONSOLEDISPLAY_CELLS','cells'),('CONSOLEBITMAP_DESKTOPDRAW','desktop_draw'),
            ('DESKPAINT_PAINTSTRIP','paint_strip')])
        points={name:p['labels'][name] for name in ('native_irq','native_nmi','interrupt_schedule')}
        restore=p['labels']['context_restore']
        code=(p['output']/'hosted.bin').read_bytes()
        require(code[restore-adapter.RESIDENT_BASE:restore-adapter.RESIDENT_BASE+8]==bytes.fromhex('c230ab2b7afa6840'),'Unknown context restore')
        points.update(turn=spans['copy']['entry'],selected=restore+4,worker_retire=p['labels']['done'])
        definition=dict(points=points,spans=spans,task_dps=[pool['dp'] for pool in p['build']['memory']['task_pools']])
        pcs=set(flat_markers(definition).values())
        pcs.update(p['labels'][n] for n in ('blitter_launched','blitter_irq_complete','blitter_irq_posted'))
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in pcs)
    if observe_backing:
        foreign=json.loads((out/'c-image.json').read_text())['symbols']
        backing_marks={name:foreign[name] for name in (
            'GemDrawingText','GemDrawingTextClip','GemDrawingBackingText','GemDrawingCopyStart')}
        os.environ.update(EXEC816_LATENCY_TRACE='1',
            EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in backing_marks.values()))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned emulator')
            report['machine'] = verify_machine(bridge, ROM, PIN)
            def before(b):
                b.memload(address('FRAGMENTFAULT'),bytes([fragment_fault]))
                if full_coverage: b.memload(address('FULLCOVERAGE'),b'\x01')
                if observe_moves or observe_backing: b.profile_start()
                previous_clock = b.eval_expr('@clk') & 0xffffffff
                for stage, expected in enumerate(scenes(font_bytes(out/'selected/src/vdi/font8x8.c'),full_coverage=full_coverage), 1):
                    marker = p['labels']['native_nmi']
                    condition = f'dw(${address("CHECKPOINT"):x})={stage}'
                    b.bp_clear_all()
                    b.bp_set(marker, condition=condition)
                    b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                    original = b.regs
                    def registers():
                        value = original()
                        if int(value['PC'].lstrip('$'), 16) == p['labels']['done']:
                            require(b.peek16(adapter.STATE) == 65535, 'Desktop stopped: '+str(b.peek16(adapter.STATE)))
                        return value
                    b.regs = registers
                    try:
                        run_to(b, marker, frame_limit=12000, timeout=600 if (observe_moves or observe_backing) else 120, condition=condition)
                    except Exception:
                        print('Desktop stage/status/checks', stage, b.peek16(adapter.STATE), data(b,p['image'],'checks',True),original(), flush=True)
                        raise
                    finally:
                        b.regs = original
                    folder = out/f'stage-{stage}'
                    folder.mkdir(exist_ok=True)
                    if expected is None:
                        accepted=data(b,p['image'],'cutBytes',True)[0]
                        require(0<accepted<512,'Missing partial-fragment cancellation')
                        expected=list(scenes(font_bytes(out/'selected/src/vdi/font8x8.c'),accepted,full_coverage=full_coverage))[-1]
                        report['fragment_accepted_prefix']=accepted
                    clock = b.eval_expr('@clk') & 0xffffffff
                    report['observations'].append(dict(stage=stage,
                        begin_cycle=previous_clock,end_cycle=clock,
                        stimulus_to_settled_cycles=(clock-previous_clock) & 0xffffffff,
                        timing_scope='Includes request, all repair, caret and two PAL settling frames; not DMA duration',
                        pixels='quiesced drawing failure' if fragment_fault and stage==19
                               else pixels(b,folder,expected,palette=DESKTOP_PALETTE)))
                    previous_clock = clock
                    b.memload(address('GATE'), stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(bridge,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(bridge,p,p['output'])
            if observe_moves or observe_backing: bridge.profile_stop()
            report['stack_usage'] = stack_usage(bridge, p['build']['memory'])
            report['checks'] = data(bridge,p['image'],'checks',True)[0]
            report['continuous_scroll'] = {name: data(bridge,p['image'],name,True)[0]
                                           for name in ('feeds', 'overtakes', 'batches', 'multirow', 'maxRows')}
            require(report['continuous_scroll']['feeds'] >= 25, 'No continuous short-write coverage')
            require(report['continuous_scroll']['overtakes'] == 0,
                    'New console output overtook unfinished scroll repaint')
            require(report['continuous_scroll']['multirow'] > 0 and
                    1 < report['continuous_scroll']['maxRows'] <= 4,
                    'No bounded multirow repaint behind the overlapping panel')
            report['status'] = 'pass'
        if observe_backing:
            backing_calls(report,out)
        if observe_moves:
            from sio_transaction_trace import read_events,BASE_HZ
            from console_turn_profile import analyze_events
            events=list(read_events(out/'emulator.log'))
            profile=analyze_events(events,definition)['routine_spans']
            completions=[tick for tick,event in events if event[0]=='cpu' and int(event[4],16)==p['labels']['blitter_irq_complete']]
            launches = [tick for tick,event in events
                        if event[0]=='cpu' and int(event[4],16)==p['labels']['blitter_launched']]
            require(launches, 'Missing actual asynchronous launches')
            for row in report['observations']:
                align = lambda t:t+round((launches[0]-t)/(1<<32))*(1<<32)
                row['text_work'] = {}
                for kind in ('cells','desktop_draw','paint_strip'):
                    calls = [s for s in profile if s['kind']==kind
                             and align(row['begin_cycle'])<=s['start']<s['end']<=align(row['end_cycle'])]
                    row['text_work'][kind] = dict(calls=len(calls),
                        total_cpu_ms=sum(s['charged_cpu_ms'] for s in calls),
                        max_cpu_ms=max((s['charged_cpu_ms'] for s in calls),default=0))
                if row['stage'] in (16,17):
                    require(row['text_work']['cells']['max_cpu_ms']<=20,
                            'Overlapping console fragments exceeded 20 ms CPU')
                if row['stage'] not in (3,8,9,10,11,12,13,14): continue
                selected = [t for t in launches if align(row['begin_cycle'])<t<align(row['end_cycle'])]
                # A move stage can now submit both window and backing copies.
                # Attribute the first submission; do not call all stage time DMA.
                require(selected, 'Copied move did not launch a list: '+str(row['stage']))
                launch=selected[0]
                calls=[span for span in profile if span['kind']=='copy' and span['start']<=launch<span['end']]
                require(len(calls)==1,'Missing copy submission span')
                call=calls[0]
                irq=next(t for t in completions if launch<=t<align(row['end_cycle']))
                polls=[span for span in profile if span['kind']=='poll' and irq<=span['start']<align(row['end_cycle'])]
                require(polls,'Missing owner completion service')
                report['move_transactions'].append(dict(stage=row['stage'],launches=selected,
                    submission=call,setup_to_launch_elapsed_ms=(launch-call['start'])/BASE_HZ*1000,
                    launch_to_irq_idle_observation_ms=(irq-launch)/BASE_HZ*1000,
                    irq_to_owner_poll_ms=(polls[0]['start']-irq)/BASE_HZ*1000,completion_poll=polls[0],
                    scope='First copy submission in this move/repair stage. Copy bridge charged CPU includes prepare/upload/launch and return. Launch-to-IRQ includes DMA and IRQ latency, an upper bound rather than exact DMA duration. Owner poll follows recorded IRQ idle acknowledgement.'))
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (out/'presentation-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Desktop presentation passed', mode, report['checks'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw','opt'),default='opt')
    parser.add_argument('--observe-backing', action='store_true')
    parser.add_argument('--full-coverage', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--observe-moves', action='store_true')
    parser.add_argument('--fragment-fault', action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.mode,args.replay,args.observe_moves,args.fragment_fault,args.observe_backing,args.full_coverage)
