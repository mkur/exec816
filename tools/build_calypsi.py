#!/usr/bin/env python3
"""Build the standalone Calypsi C message example with the pinned Exec kernel."""
import argparse
import json
from pathlib import Path

from calypsi_build import emit
from library_paths import read_source
from native_program import ROOT, build, compiler, require, sha256


def build_example(output, optimize=True, context=False, large_stacks=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not (context and large_stacks), 'Select one C context fixture')
    example = ROOT/('tests/programs/calypsi_large_stacks.c' if large_stacks else
                    'tests/programs/calypsi_context.c' if context else 'c/examples/messages.c')
    foreign = emit(output, (ROOT/'c/calypsi/exec.c', ROOT/'c/calypsi/dos.c',
                            ROOT/'c/calypsi/io.c', example),
                   (ROOT/'c/calypsi/gateway.s', ROOT/'c/calypsi/dos.s',
                    ROOT/'c/calypsi/io.s', ROOT/'c/calypsi/image-info.s'),
                   ['Receiver'], optimize=optimize, roots=['ExecDosEntries', 'ExecIOEntry'])
    include = output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
                               for name in ('main', 'ExecDosEntries', 'ExecIOEntry')))
    source = output/'launcher.act'
    source.write_text(read_source(ROOT/'c/calypsi/launcher.act', {'c-image.inc': include}))
    source_inputs = {str(p.relative_to(ROOT)): sha256(p) for p in
                     sorted((ROOT/'c').rglob('*')) if p.is_file()}
    source_inputs[str(example.relative_to(ROOT))] = sha256(example)
    foreign['provenance'].update(source_inputs=source_inputs, context_probe=context, large_stacks=large_stacks)
    (output/'c-image.json').write_text(json.dumps(foreign, indent=2)+'\n')
    program = build(compiler(ROOT/'build/actionc'), source, output/'program', optimize=optimize,
                    tasks=True, task_capacity=8 if large_stacks else 4, console=True, foreign_image=foreign)
    return program, foreign


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/calypsi/messages')
    parser.add_argument('--no-opt', action='store_true')
    args = parser.parse_args()
    program, _ = build_example(args.output, not args.no_opt)
    print('C example ready:', program['xex'])
