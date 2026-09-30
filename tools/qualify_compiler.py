#!/usr/bin/env python3
"""Run existing hosted oracles with an explicit clean compiler candidate.

The production pin and existing qualification records are never changed here.
Each invocation saves one independent result tree; run serial emulator cases
sequentially and use the established workload/timing limits unchanged.
"""
import argparse
import json
from pathlib import Path
import time

from native_program import ROOT, command, compiler, require, sha256


def run(t, args, out):
    mode, optimize = args.case, args.case == 'opt'
    if args.suite == 'boundary':
        from test_hosted import main
        return main(['--compiler-dir', str(t['directory']), '--bridge-dir',
                     str(ROOT / 'build/altirra-irq-bridge')],
                    toolchain=t, output=out, modes=(optimize,))
    if args.suite == 'core':
        from test_dos_regressions import run
        return run(t, out, mode, ['heap', 'ports', 'io', 'signals', 'tasks',
                                  'lists-named', 'lists-shared', 'loader3'])
    if args.suite == 'dos':
        from test_dos_files import run as files
        from test_dos_directories import run as directories
        from test_dos_lifetime import run as lifetime
        cases = []
        for name, action in (
            ('files', lambda dest: files(t, dest, mode, 128, capacity=8, concurrent=True)),
            ('directories', lambda dest: directories(t, dest, mode, 128)),
            ('lifetime', lambda dest: lifetime(t, dest, mode)),
            ('retry', lambda dest: lifetime(t, dest, mode, retry=True)),
        ):
            dest = out / name; dest.mkdir(parents=True, exist_ok=True)
            result = action(dest); result['name'] = name
            (dest / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
            cases.append(result)
        return dict(status='pass', cases=cases)
    if args.suite == 'console':
        from test_console_lifetime import run as lifetime
        from test_console_services import run as services
        cases = []
        for name, function, modes in (('lifetime', lifetime, (0, 6, 9)),
                                      ('services', services, (0, 1, 4, 5))):
            for case in modes:
                dest = out / f'{name}-{case}'; dest.mkdir(parents=True, exist_ok=True)
                result = function(t, dest, case, optimize)
                (dest / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
                cases.append(result)
        return dict(status='pass', cases=cases)
    if args.suite == 'concurrent':
        from test_console_concurrent import run
        return run(out, mode, args.sector_size, args.speed, args.bank, args.trace, toolchain=t)
    if args.suite == 'tx':
        from test_console_tx import run
        return run(out, optimize, toolchain=t)
    if args.suite == 'recovery':
        from test_console_recovery import run
        return run(out, optimize, toolchain=t)
    raise ValueError(args.suite)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, required=True)
    parser.add_argument('--compiler-pin', type=Path, required=True)
    parser.add_argument('--suite', choices=('boundary', 'core', 'dos', 'console', 'concurrent', 'tx', 'recovery'), required=True)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--sector-size', type=int, choices=(128, 256), default=128)
    parser.add_argument('--speed', type=int, choices=(0, 1), default=0)
    parser.add_argument('--bank', type=int, choices=(1, 3), default=1)
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'results.json').exists(), 'Use a new artifact path; do not overwrite evidence')
    pin = json.loads(args.compiler_pin.read_text())
    require(command(['git', '-C', args.compiler_dir, 'rev-parse', 'HEAD']).strip() == pin['revision'],
            'Candidate revision differs from its explicit contract')
    require(not command(['git', '-C', args.compiler_dir, 'status', '--porcelain']).strip(),
            'Compiler qualification requires a clean checkout')
    started = time.monotonic()
    result = dict(status='running', candidate=pin, candidate_pin_sha256=sha256(args.compiler_pin),
                  driver_sha256=sha256(Path(__file__)),
                  invocation={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()})
    try:
        t = compiler(args.compiler_dir, allow_override=True, pin=pin)
        result['compiler'] = {k: v for k, v in t.items() if k not in ('directory', 'binary')}
        result['result'] = run(t, args, out)
        require(result['result']['status'] == 'pass', 'Hosted candidate gate failed')
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Compiler qualification passed:', args.suite, args.case, flush=True)


if __name__ == '__main__':
    main()
