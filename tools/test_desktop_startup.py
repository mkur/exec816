#!/usr/bin/env python3
"""Partial desktop registration unwind and successful subsequent admission."""
import argparse
import json
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, verify_machine
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data
from desktop_budget import delta


def run(out, mode, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/desktop_startup.act',
        out, mode == 'opt', desktop=True, stack_checks=True)
    report = dict(status='running', tier='development', qualification=False, mode=mode,
                  build=p['build'], reserved_bank_zero_delta=delta(p['build']['memory']))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)
            report['runtime'], _ = execute(b, p, timeout=180, frame_limit=10000)
            ownership(b, p, p['output'])
            report['checks'] = data(b, p['image'], 'checks', True)[0]
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
