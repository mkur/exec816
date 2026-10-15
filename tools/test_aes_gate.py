#!/usr/bin/env python3
"""Focused emitted caller/presenter handoff, wake and preemption checks."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    program = build(compiler(ROOT/'build/actionc', release=True),
                    ROOT/'tests/programs/aes_gate.act', out/'program',
                    tasks=True, task_capacity=8, optimize=True)
    with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROM, PIN)
        runtime, _ = execute(bridge, program, frame_limit=600, timeout=120)
        ownership(bridge, program, program['output'])
        checks = data(bridge, program['image'], 'checks', True)[0]
        require(checks == 24, 'Incomplete gate fixture: '+str(checks))
        require(runtime['native_nmi_count'] >= 3, 'Missing natural preemption')
    report = dict(status='pass', tier='development', qualification=False,
                  checks=checks, machine=machine, runtime=runtime,
                  build=program['build'])
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES gate checks passed:', checks, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
