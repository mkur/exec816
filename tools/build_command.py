#!/usr/bin/env python3
"""Compile a relocatable Exec command against the explicit v1 provider API."""
import argparse
import json
from pathlib import Path
from generate_program import ABI, library_contracts, command_import
from library_paths import module_args
from native_program import ROOT, compiler, command, sha256


def compile_command(toolchain, source, output, optimize=True):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    args = [toolchain['binary'], *module_args(), '--entry', 'Main']
    interfaces = json.loads(command([*args,'--emit-interfaces',source]))
    libraries = library_contracts(toolchain['directory'])
    imports = [command_import(interface, libraries) for interface in interfaces]
    options = output.with_suffix('.options.json')
    options.write_text(json.dumps(dict(profile=ABI['profile'],nmi_extra_stack=0,imports=imports),indent=2)+'\n')
    command([*args,'--format','o65-experimental','--o65-options',options,'--o65-report',output.with_suffix('.profile.json'),
             *([] if optimize else ['--no-opt']),'-o',output,source])
    return dict(source=str(source),source_sha256=sha256(source),file_sha256=sha256(output),
                compiler=toolchain['revision'],compiler_sha256=toolchain['binary_sha256'],optimize=optimize,
                api_sha256=sha256(ROOT/'lib/dos/command.act'),profile_sha256=sha256(output.with_suffix('.profile.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('-o','--output',type=Path,required=True)
    parser.add_argument('--no-opt',action='store_true')
    args = parser.parse_args()
    record = compile_command(compiler(ROOT/'build/actionc'),args.source,args.output,not args.no_opt)
    args.output.with_suffix('.build.json').write_text(json.dumps(record,indent=2)+'\n')
