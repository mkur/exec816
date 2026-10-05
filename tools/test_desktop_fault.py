#!/usr/bin/env python3
"""Desktop Layers token and client lifetime across blitter watchdog outcomes."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from generate_desktop import layout
from generate_layers import layout as layers_layout


def run(out, mode, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    source = out/'desktop-fault.act'
    text = (ROOT/'tests/programs/console_bitmap_fault.act').read_text()
    # Same production fault adapter, with the desktop's 64x20 retained console.
    for before, after in (('58', '38'), ('79', '63'), ('80', '64'), ('2320', '1216'), ('2400', '1280')):
        import re
        text = re.sub(r'\b'+before+r'\b', after, text)
    text = text.replace('Require(CONSOLE.Hide(0)<>0)', 'Require(CONSOLE.Hide(0)=0)')
    source.write_text(text)
    p = read_build(out/'program') if replay else build_bitmap(source, out, mode == 'opt', desktop=True, fault=True)
    sy = json.loads((out/'c-image.json').read_text())['symbols']
    at = lambda module, name: next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    report = dict(status='running', tier='development', qualification=False, mode=mode, build=p['build'], cases=[])
    try:
        for variant in (3, 4):
            folder = out/f'fault-{variant}'
            with emulator(BRIDGE, ROM, folder, pin=PIN) as b:
                b._cmd_ok('MOUSE ST')
                report['machine'] = verify_machine(b, ROM, PIN)
                saved = {}
                def before(bridge):
                    b.poke(at('BITMAPFAULT', 'variant'), variant)
                    marker = p['labels']['native_nmi']
                    condition = f'dw(${at("BITMAPFAULT", "checkpoint"):x})=1'
                    b.bp_set(marker, condition=condition)
                    run_to(b, marker, condition=condition, frame_limit=8000, timeout=120)
                    b.bp_clear_all()
                    b.poke16(sy['ConsoleCopyChunks'], 0)
                    saved['service'] = int.from_bytes(b.memdump(at('DESKSTATE', 'service'), 3), 'little')
                    b.poke16(sy['ConsoleFaultMode'], variant)
                    b.poke16(at('BITMAPFAULT', 'gate'), 1)
                try:
                    runtime, _ = execute(b, p, before_run=before, expected_status=0 if variant == 3 else 0xff93,
                                         frame_limit=10000, timeout=180)
                except Exception:
                    print('Fault boundary', variant, 'checks', b.peek16(at('BITMAPFAULT', 'checks')),
                          {name: b.peek16(sy[name]) for name in ('ConsoleFaultMode', 'ConsoleStopCount', 'ConsoleCopyChunks')}, flush=True)
                    raise
                require(b.peek16(sy['ConsoleStopCount']) == 1, 'Missing single watchdog STOP')
                require(b.peek16(sy['ConsoleCopyChunks']) == 1, 'Fault did not follow one scroll launch')
                if variant == 3:
                    ownership(b, p, p['output'])
                    require(int.from_bytes(b.memdump(at('DESKSTATE', 'service'), 3), 'little') == 0,
                            'Quiesced failure retained service allocation')
                else:
                    scene = saved['service']+layout()['Service']['fields']['scene']
                    require(b.peek16(scene+layers_layout()['Scene']['fields']['busy']) != 0,
                            'Unquiesced failure released Layers token')
                    require(int.from_bytes(b.memdump(at('DESKBOOT', 'client'), 4), 'little') != 0,
                            'Unquiesced failure withdrew live client')
                    read = int.from_bytes(b.memdump(at('BITMAPFAULT', 'read'), 3), 'little')
                    require(b.peek(read+6) == bytes([5]), 'Unquiesced failure replied to borrowed I/O')
                report['cases'].append(dict(variant=variant, runtime=runtime))
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
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.replay)
