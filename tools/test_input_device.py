#!/usr/bin/env python3
"""Focused emitted input.device development checks; no desktop/demo build."""
import argparse
import json
from pathlib import Path
import shutil

from native_program import ROOT, build, compiler, command, execute, verify_machine, require
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage

PIN = json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())


def c_layout(output, optimize):
    from generate_input_device import ABI
    from calypsi_image import check_layout
    expected = []
    expressions = []
    for name, record in ABI['records'].items():
        expected.append((name+' size', record['bytes']))
        expressions.append(f'sizeof(struct InputDevice{name})')
        for field, _, offset in record['fields']:
            expected.append((name+' '+field, offset))
            expressions.append(f'offsetof(struct InputDevice{name}, {field})')
    source = output/'layout.c'
    source.write_text('#include <devices/input.h>\n'
        '__attribute__((section("exec_layout")))\n'
        'const unsigned short __exec_layout[] = {\n'+',\n'.join(expressions)+'\n};\n')
    obj = output/'layout.o'
    command([shutil.which('cc65816'), '--code-model=large', '--data-model=huge',
             '-O2' if optimize else '-O0', '-I', ROOT/'c/include', '-c', '-o', obj, source])
    return check_layout(obj, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--suite', choices=('abi',), default='abi')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    layout = c_layout(output, args.mode == 'opt')
    program = build(compiler(args.compiler_dir, release=True),
                    ROOT/'tests/programs/input_device_abi.act', output/'program',
                    tasks=True, console=False, sio_enabled=False,
                    optimize=args.mode == 'opt')
    report = dict(status='running', tier='development', qualification=False,
                  suite=args.suite, mode=args.mode, build=program['build'], c_layout=layout)
    try:
        with emulator(ROOT/'build/altirra-irq-bridge',
                      ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=2400)
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            require(report['checks'] == 17, 'Incomplete input.device ABI fixture')
            clean_ownership(bridge, program, program['output'])
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            report['bank_zero_delta'] = dict(fixed=0, root=0, kernel=0, idle=0, per_task=0)
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS input.device {args.suite} {args.mode}: {report["checks"]} checks')


if __name__ == '__main__':
    main()
