#!/usr/bin/env python3
"""Real quiesced/reset-required drawing faults during partial cell vectors."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, require, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import PIN, BRIDGE, ROM


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    p = build_bitmap(ROOT / 'tests/programs/console_span_fault.act', out,
                     release_compiler=True, fault=True)
    symbols = json.loads((out / 'c-image.json').read_text())['symbols']
    at = lambda name: next(d['address'] for d in p['image']['data']
                           if '_CONSOLESPANFAULT_' + name + '_' in d['name'])
    cases = []
    for mode in (5, 6):
        for variant in (0, 1):
            folder = out / f'{mode}-{variant}'
            with emulator(BRIDGE, ROM, folder, pin=PIN) as b:
                machine = verify_machine(b, ROM, PIN)
                def before(b):
                    b.memload(at('VARIANT'), bytes([variant]))
                    marker = p['labels']['native_nmi']
                    condition = f'dw(${at("CHECKPOINT"):x})=1'
                    b.bp_set(marker, condition=condition)
                    run_to(b, marker, condition=condition, frame_limit=9000, timeout=180)
                    b.bp_clear_all()
                    b.memload(symbols['ConsoleFaultMode'], mode.to_bytes(2, 'little'))
                    b.memload(at('GATE'), b'\1\0')
                runtime, _ = execute(b, p, before_run=before,
                                     expected_status=0 if mode == 5 else 0xff93,
                                     frame_limit=9000, timeout=180)
                require(b.peek16(symbols['ConsoleStopCount']) == 1, 'STOP not exact-once')
                require(b.peek16(symbols['ConsoleTextChunks']) == 1, 'Fault missed first text batch')
                if mode == 5:
                    ownership(b, p, p['output'])
                else:
                    request = int.from_bytes(bytes(data(b, p['image'], 'writer')), 'little')
                    require(b.memdump(request + 6, 1) == bytes([5]), 'Unsafe DMA replied to vector')
                    require(int.from_bytes(b.memdump(request + 26, 4), 'little') == variant * 10,
                            'Reset-required vector lost its whole-descriptor prefix')
                cases.append(dict(mode=mode, variant=variant, runtime=runtime,
                                  checks=int.from_bytes(bytes(data(b, p['image'], 'checks')), 'little'),
                                  machine=machine))
    return dict(status='pass', tier='development', qualification=False,
                cases=cases, build=p['build'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Cell-vector drawing faults passed')
