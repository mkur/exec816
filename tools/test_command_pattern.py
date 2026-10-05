#!/usr/bin/env python3
"""Run the command wildcard matcher as raw and optimized emitted code."""
import argparse
import json
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES = [
    ('*', '', 1), ('?', '', 0), ('a?c', 'abc', 1),
    ('a*c', 'ac', 1), ('a*c', 'abbbc', 1),
    ('*.TXT', 'Readme.txt', 1), ('a*B?', 'azbC', 1),
    ('*a', 'bbb', 0), ('A?', 'aB', 1),
    ('*.TXT', 'README', 0), ('?*?', 'A', 0),
    ('?*?', 'AB', 1), ('*.*', 'DOTLESS', 0),
]


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    source = 'MODULE MATCH\nUSE ASCII\nUSE EXECPOLICY\n'
    source += read_source(ROOT/'examples/commands/command-pattern.inc')
    source += f'\nBYTE ARRAY results({len(CASES)})\nBYTE finished\nPROC Main()\n'
    for index, (pattern, name, _) in enumerate(CASES):
        source += f'  results({index})=PatternMatch(c"{pattern}",c"{name}")\n'
    source += '  finished=1\nRETURN\nENDMODULE\n'
    path = out/'pattern.act'
    path.write_text(source)
    p = build(compiler(ROOT/'build/actionc'), path, out,
              optimize=mode=='opt', banked=True, console=False)
    with emulator(ROOT/'build/shell-paced-bridge',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as machine:
        for key, value in PIN['configuration'].items():
            machine.config(key, str(value).lower() if isinstance(value, bool) else value)
        configuration = verify_machine(machine, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(machine, p, timeout=90, frame_limit=4500)
        require(data(machine, p['image'], 'finished') == [1], 'Matcher did not finish')
        actual = data(machine, p['image'], 'results')
        require(actual == [result for _, _, result in CASES], f'Matcher results: {actual}')
    return dict(status='pass', tier='development', mode=mode, cases=CASES,
                build=p['build'], runtime=runtime, machine=configuration,
                bank_zero_delta=dict(fixed=0, per_task=0),
                source_inputs={str(q.relative_to(ROOT)): sha256(q) for q in
                               (ROOT/'examples/commands/command-pattern.inc', Path(__file__))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.case)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Pattern checks passed:', args.case, len(CASES))
