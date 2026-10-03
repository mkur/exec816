#!/usr/bin/env python3
"""Small emitted registration contract fixture in either diagnostic setting."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from stack_budget import stack_usage
from test_cooperative import data
from test_heap_api import clean_ownership
from test_mouse_observe import PIN, BRIDGE, ROM


def run(output, mode, input_diagnostics=False, replay=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', mode=mode, cases=[])
    try:
        (output/'program').mkdir(exist_ok=True)
        source = output/'program/input_registration.act'
        source.write_bytes((ROOT/'tests/programs/input_registration.act').read_bytes())
        p = read_build(output/'program') if replay else build(
            compiler(ROOT/'build/actionc'), source,
            output/'program', optimize=mode == 'opt', tasks=True, task_capacity=8,
            console=False, input_diagnostics=input_diagnostics)
        require(p['build']['input_diagnostics'] == input_diagnostics, 'Wrong diagnostics')
        require(p['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                'Unpinned emulator')
        report.update(build=p['build'], pin=PIN, xex_sha256=sha256(p['xex']))
        with emulator(BRIDGE, ROM, output, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                runtime, _ = execute(bridge, p, frame_limit=3000, timeout=90)
            finally:
                report['checks'] = data(bridge, p['image'], 'checks', True)
                report['pending'] = data(bridge, p['image'], 'pending', True)
            require(data(bridge, p['image'], 'finished') == [1], 'Contract fixture incomplete')
            clean_ownership(bridge, p, p['output'])
            report['cases'].append(dict(name='contract', checks=data(bridge, p['image'], 'checks', True),
                runtime=runtime, stack_usage=stack_usage(bridge, p['build']['memory'])))
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Input registration passed', mode, 'diagnostics', input_diagnostics, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--input-diagnostics', action='store_true')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output, args.mode, args.input_diagnostics, args.replay)
