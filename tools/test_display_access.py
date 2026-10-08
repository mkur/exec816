#!/usr/bin/env python3
"""Focused Task-side DISPLAY arbitration through emitted native code."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_mouse_observe import BRIDGE, ROM, PIN
from os_boundary import emulator


def run(out, mode='opt', replay=False):
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', qualification=False,
                  slice='WA3', mode=mode,
                  reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8, idle=0))
    try:
        p = read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),
            ROOT/'tests/programs/native_display_access.act', out/'program',
            optimize=mode == 'opt', tasks=True, task_capacity=8, console=False)
        report['build'] = p['build']
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROM, PIN)
            try:
                report['runtime'], _ = execute(b, p, timeout=120, frame_limit=6000)
            finally:
                report['checks'] = data(b, p['image'], 'checks', True)[0]
            ownership(b, p, p['output'])
            require(report['checks'] >= 50, 'Incomplete arbitration fixture')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error)); raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('DISPLAY arbitration', mode, 'passed', report['checks'], flush=True)
    return report


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output', type=Path, required=True)
    a.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    a.add_argument('--replay', action='store_true')
    args = a.parse_args(); run(args.output.resolve(), args.mode, args.replay)
