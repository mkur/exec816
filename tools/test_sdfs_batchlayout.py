#!/usr/bin/env python3
"""Focused emitted layout/access probe, with no filesystem walkthrough."""
import argparse
import json
from pathlib import Path

from banked_test_memory import read
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(out, optimize):
    program = build(compiler(ROOT/'build/actionc'),
                    ROOT/'tests/programs/sdfs_batchlayout.act', out,
                    optimize=optimize, tasks=True, task_capacity=8, dos_test=True,
                    image_data=[(0x30ffd0, bytes([0xa5])*(1264+64))])
    with emulator(ROOT/'build/altirra-sio-multi',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, program)
        ownership(b, program, out)
        observed = data(b, program['image'], 'results', True)
        require(observed == [1190, 0x31, 0x42, 0x53, 1, 8193, 0x1234, 0x64],
                f'Record access/layout differs: {observed}')
        guard = read(b, 0x30ffd0, 1264+64, out)
        require(guard[:32] == guard[-32:] == bytes([0xa5])*32,
                'Record guard changed')
    return dict(status='pass', tier='development', build=program['build'],
                machine=machine, runtime=runtime, observed=observed,
                scope='Shared record size/access and copied fields across a bank boundary')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=('raw', 'opt'), required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.case == 'opt')
        print('SDFS layout passed', args.case, flush=True)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
