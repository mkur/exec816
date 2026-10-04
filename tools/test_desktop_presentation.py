#!/usr/bin/env python3
"""Compare the worker-hosted desktop with an independent complete raster."""
import argparse
import json
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
from desktop_budget import delta as desktop_delta
from stack_budget import bank_zero_delta


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


def frame(raster, bounds, title, focused, background=0):
    x, y, right, bottom = bounds
    rectangle(raster, bounds, 8)
    rectangle(raster, (x+2, y+2, right-2, y+14), 2 if focused else 7)
    text(raster, x+8, y+4, title, bg=2 if focused else 7)
    rectangle(raster, (x+8, y+16, right-8, bottom-8), background)


def scenes(font):
    terminal = Terminal(64, 20)
    terminal.feed(b'ABC')
    for stage in range(1, 7):
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
            frame(raster, (113, 93, 273, 173), b'Clip', False, 3)
            text(raster, 124, 112, b'XYZ', bg=3)
        yield raster.packed()


def run(out, mode, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(out/'program') if replay else build_bitmap(
        ROOT/'tests/programs/desktop_presentation.act', out, mode == 'opt', desktop=True)
    require(p['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
    report = dict(status='running', tier='development', qualification=False, slice='DT2',
                  build=p['build'], observations=[], bank_zero_delta=bank_zero_delta(p['build']['memory']),
                  reserved_bank_zero_delta=desktop_delta(p['build']['memory']))
    address = lambda name: next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+name+'_' in d['name'])
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned emulator')
            report['machine'] = verify_machine(bridge, ROM, PIN)
            def before(b):
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
                        run_to(b, marker, frame_limit=12000, timeout=120, condition=condition)
                    except Exception:
                        print('Desktop stage/status/checks', stage, b.peek16(adapter.STATE), data(b,p['image'],'checks',True),b.regs(), flush=True)
                        raise
                    finally:
                        b.regs = original
                    folder = out/f'stage-{stage}'
                    folder.mkdir(exist_ok=True)
                    report['observations'].append(dict(stage=stage, pixels=pixels(b,folder,expected)))
                    b.memload(address('GATE'), stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(bridge,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(bridge,p,p['output'])
            report['checks'] = data(bridge,p['image'],'checks',True)[0]
            report['status'] = 'pass'
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
    args=parser.parse_args()
    run(args.output.resolve(),args.mode,args.replay)
