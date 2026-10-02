#!/usr/bin/env python3
"""Run existing emitted SIO/keyboard checks with the ST preset enabled."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

from native_program import ROOT, compiler, require, sha256
from os_boundary import emulator
from test_mouse_observe import BRIDGE, PIN


@contextmanager
def mapped_emulator(bridge_dir, rom, output_dir, pin):
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
            'Unpinned mouse test bridge')
    with emulator(BRIDGE, rom, output_dir, pin=pin) as bridge:
        bridge._cmd_ok('MOUSE ST')
        yield bridge


def run(out, mode, case):
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', slice='M0', mode=mode, case=case,
                  mouse_input=PIN['mouse_input'])
    try:
        os.environ.pop('EXEC816_MOUSE_TRACE', None)
        if case == 'keyboard':
            import test_gem_interactive as test
            test.emulator = mapped_emulator
            report['result'] = test.run(out/'keyboard', mode, ['keyboard'])
        elif case == 'deadline':
            import test_sio_deadline_ticks as test
            test.emulator = mapped_emulator
            report['result'] = test.run(compiler(ROOT/'build/actionc'), out/'deadline', mode)
        else:
            import test_sio_adapter as test
            test.emulator = mapped_emulator
            report['result'] = test.run(compiler(ROOT/'build/actionc'), out/'sio', mode == 'opt', trace=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Mouse-enabled baseline passed:', case, mode, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--case', choices=('keyboard', 'sio', 'deadline'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.case)
