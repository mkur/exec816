#!/usr/bin/env python3
"""Build the standalone Calypsi C message example with the pinned Exec kernel."""
import argparse
import json
import shutil
from pathlib import Path

from calypsi_image import read_image, check_layout
from generate_calypsi import files, expected_layout
from library_paths import read_source
from native_program import ROOT, build, command, compiler, require, sha256


def build_example(output, optimize=True, context=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    tools = {}
    for name in ('cc65816', 'as65816', 'ln65816'):
        path = shutil.which(name)
        require(path is not None, 'Calypsi tool not installed: ' + name)
        path = Path(path).resolve()
        version = command([path, '--version']).strip()
        require(version.endswith('version 5.18'), 'This C binding is checked with Calypsi 5.18')
        tools[name] = dict(path=str(path), version=version, sha256=sha256(path))
    for path, content in files().items():
        require(path.read_text() == content, 'Stale C binding: ' + str(path))
    runtime = Path(tools['cc65816']['path']).parent.parent/'lib/clib-lc-hd.a'
    require(runtime.is_file(), 'Missing Calypsi large-code/huge-data runtime')
    flags = ['--code-model=large', '--data-model=huge', '-O2' if optimize else '-O0']
    layout_object = output/'layout-check.o'
    command([tools['cc65816']['path'], *flags, '-c', '-I', ROOT/'c/include',
             '-o', layout_object, ROOT/'c/calypsi/layout-check.c'])
    layouts = check_layout(layout_object, expected_layout())
    objects = []
    example = ROOT/('tests/programs/calypsi_context.c' if context else 'c/examples/messages.c')
    for source in (ROOT/'c/calypsi/exec.c', ROOT/'c/calypsi/dos.c', example):
        obj = output/(source.stem+'.o')
        command([tools['cc65816']['path'], *flags, '-c', '-I', ROOT/'c/include', '-I', output,
                 '--list-file', output/(source.stem+'.lst'), '-o', obj, source])
        objects.append(obj)
    for source in (ROOT/'c/calypsi/gateway.s', ROOT/'c/calypsi/dos.s', ROOT/'c/calypsi/image-info.s'):
        obj = output/(source.stem+'-asm.o')
        command([tools['as65816']['path'], '-I', ROOT/'c/calypsi', '-o', obj, source])
        objects.append(obj)
    elf = output/'program.elf'
    command([tools['ln65816']['path'], '--hosted', '--program-root', 'main', '--program-start', 'main',
             '--root-symbol', 'Receiver', '--root-symbol', '__exec_image_info',
             '--root-symbol', 'ExecDosEntries',
             '--no-data-init-table-section', '--no-automatic-placement-rules',
             '--list-file', output/'link.lst', '-o', elf, *objects, ROOT/'c/calypsi/layout.scm'])
    foreign = read_image(elf, ['Receiver'])
    include = output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
                               for name in ('main', 'ExecDosEntries')))
    source = output/'launcher.act'
    source.write_text(read_source(ROOT/'c/calypsi/launcher.act', {'c-image.inc': include}))
    source_inputs = {str(p.relative_to(ROOT)): sha256(p) for p in
                     sorted((ROOT/'c').rglob('*')) if p.is_file()}
    source_inputs[str(example.relative_to(ROOT))] = sha256(example)
    foreign['provenance'].update(tools=tools, runtime=dict(path=str(runtime), sha256=sha256(runtime)),
                                 compiler_flags=flags, source_inputs=source_inputs,
                                 checked_layout=layouts, context_probe=context)
    (output/'c-image.json').write_text(json.dumps(foreign, indent=2)+'\n')
    program = build(compiler(ROOT/'build/actionc'), source, output/'program', optimize=optimize,
                    tasks=True, task_capacity=4, console=True, foreign_image=foreign)
    return program, foreign


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/calypsi/messages')
    parser.add_argument('--no-opt', action='store_true')
    args = parser.parse_args()
    program, _ = build_example(args.output, not args.no_opt)
    print('C example ready:', program['xex'])
