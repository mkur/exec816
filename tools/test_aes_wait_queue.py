#!/usr/bin/env python3
"""Emitted shared waiter ordering and private record layout."""
import argparse
import json
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data
from pathlib import Path


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    p = build(compiler(ROOT/'build/actionc', release=True),
              ROOT/'tests/programs/aes_wait_queue.act', out/'program',
              tasks=True, task_capacity=8, optimize=mode=='opt')
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        machine = verify_machine(b, ROM, PIN)
        runtime, _ = execute(b, p, frame_limit=600, timeout=120)
        ownership(b, p, p['output'])
        checks = data(b, p['image'], 'checks', True)[0]
        at = next(d['address'] for d in p['image']['data']
                  if d['name'].startswith('M_WAITERTEST_OFFSETS_'))
        raw = b.memdump(at, 48)
        offsets = [int.from_bytes(raw[i:i+4], 'little') for i in range(0, 48, 4)]
        require(checks == 19, 'Incomplete waiter ordering checks: '+str(checks))
    report = dict(status='pass', tier='development', qualification=False,
                  mode=mode, checks=checks, offsets=offsets, machine=machine,
                  runtime=runtime, build=p['build'])
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES waiter queue checks passed:', checks, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode)
