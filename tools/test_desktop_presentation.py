#!/usr/bin/env python3
"""Compare the worker-hosted desktop with an independent complete raster."""
import argparse
import json
import os
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data
from gem_render_oracle import Raster, font_bytes
from bitmap_console_oracle import Terminal
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


def frame(raster, bounds, title, focused, background=0, close=False):
    x, y, right, bottom = bounds
    rectangle(raster, bounds, 8)
    rectangle(raster, (x+2, y+2, right-2, y+14), 2 if focused else 7)
    text(raster, x+8, y+4, title, bg=2 if focused else 7)
    if close:
        rectangle(raster, (right-14, y+2, right-2, y+14), 8)
        text(raster, right-12, y+4, b'X', bg=8)
    rectangle(raster, (x+8, y+16, right-8, bottom-8), background)


def scenes(font):
    terminal = Terminal(64, 20)
    terminal.feed(b'ABC')
    for stage in range(1, 16):
        if stage == 2:
            for row in range(25):
                terminal.feed(bytes(33+(row*7+col) % 90 for col in range(64)))
        if stage == 5:
            terminal.feed(b'\x0cHello')
        raster = Raster(font)
        rectangle(raster, (0, 0, 640, 240), 8)
        left, top = (32, 24) if stage < 3 else (80, 48)
        frame(raster, (left, top, left+528, top+184), b'Exec816 Shell', True)
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
        yield overlay(raster, (320, 120))


def run(out, mode, replay=False, observe_moves=False):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 8192  # Fixture records, separate from the demo's 4 KiB.
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    p = read_build(out/'program') if replay else build_bitmap(
        ROOT/'tests/programs/desktop_presentation.act', out, mode == 'opt', desktop=True, memory_profile=memory)
    require(p['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
    report = dict(status='running', tier='development', qualification=False, slice='DT2',
                  build=p['build'], observations=[], move_transactions=[], bank_zero_delta=bank_zero_delta(p['build']['memory']),
                  reserved_bank_zero_delta=desktop_delta(p['build']['memory']))
    address = lambda name: next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+name+'_' in d['name'])
    if observe_moves:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        os.environ['EXEC816_LATENCY_PCS']=f'{p["labels"]["blitter_launched"]:x}'
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned emulator')
            report['machine'] = verify_machine(bridge, ROM, PIN)
            def before(b):
                if observe_moves: b.profile_start()
                previous_clock = b.eval_expr('@clk') & 0xffffffff
                for stage, expected in enumerate(scenes(font_bytes(out/'selected/src/vdi/font8x8.c')), 1):
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
                        run_to(b, marker, frame_limit=12000, timeout=600 if observe_moves else 120, condition=condition)
                    except Exception:
                        print('Desktop stage/status/checks', stage, b.peek16(adapter.STATE), data(b,p['image'],'checks',True),b.regs(), flush=True)
                        raise
                    finally:
                        b.regs = original
                    folder = out/f'stage-{stage}'
                    folder.mkdir(exist_ok=True)
                    clock = b.eval_expr('@clk') & 0xffffffff
                    report['observations'].append(dict(stage=stage,
                        begin_cycle=previous_clock,end_cycle=clock,
                        stimulus_to_settled_cycles=(clock-previous_clock) & 0xffffffff,
                        timing_scope='Includes request, all repair, caret and two PAL settling frames; not DMA duration',
                        pixels=pixels(b,folder,expected)))
                    previous_clock = clock
                    b.memload(address('GATE'), stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(bridge,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(bridge,p,p['output'])
            if observe_moves: bridge.profile_stop()
            report['stack_usage'] = stack_usage(bridge, p['build']['memory'])
            report['checks'] = data(bridge,p['image'],'checks',True)[0]
            report['status'] = 'pass'
        if observe_moves:
            from sio_transaction_trace import read_events
            launches = [tick for tick,event in read_events(out/'emulator.log')
                        if event[0]=='cpu' and int(event[4],16)==p['labels']['blitter_launched']]
            require(launches, 'Missing actual asynchronous launches')
            for row in report['observations']:
                if row['stage'] not in (3,8,9,10,11,12,13,14): continue
                align = lambda t:t+round((launches[0]-t)/(1<<32))*(1<<32)
                selected = [t for t in launches if align(row['begin_cycle'])<t<align(row['end_cycle'])]
                require(len(selected)==1, 'Copied move must launch one list: '+str(row['stage']))
                report['move_transactions'].append(dict(stage=row['stage'], launches=selected))
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (out/'presentation-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Desktop presentation passed', mode, report['checks'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw','opt'),default='opt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--observe-moves', action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.mode,args.replay,args.observe_moves)
