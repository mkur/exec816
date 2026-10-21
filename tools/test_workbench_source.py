#!/usr/bin/env python3
"""Clean, offline rebuild of the workbench corresponding-source ZIP."""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from native_program import ROOT, require, sha256


def check(archive, output, application):
    output.mkdir(parents=True, exist_ok=False)
    extracted = output/'source'
    with zipfile.ZipFile(archive) as source:
        names = set(source.namelist())
        verified = {'SHA256SUMS'}
        for line in source.read('SHA256SUMS').decode().splitlines():
            digest, name = line.split('  ', 1)
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                    'Unsafe source member: '+name)
            require(hashlib.sha256(source.read(name)).hexdigest() == digest,
                    'Source checksum: '+name)
            verified.add(name)
        require(names == verified, 'Incomplete source checksums')
        source.extractall(extracted)
    donor, native = extracted/'fastbasic', extracted/'exec816'
    commands = []
    with (output/'rebuild.log').open('w') as log:
        def run(arguments, cwd):
            commands.append([str(a) for a in arguments])
            subprocess.run(arguments, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                           check=True)
        run(['make', '-j4', 'build/bin/fastbasic', 'build/bin/ca65',
             'build/bin/ld65', 'build/bin/ar65', 'build/gen/syntp'], donor)
        run(['make', '-j4'], donor/'testsuite/mini65')
        run(['make', '-j4', 'build/bin/fbci.xex', 'build/bin/fbc.xex',
             'build/compiler/fastbasic-int.lib', 'build/compiler/fastbasic-fp.lib'], donor)
        sources = ['examples/gem-basic/'+name for name in
                   ('main.c', 'basic.c', 'editor.c', 'editor-paint.c', 'document.c',
                    'files.c', 'file-ui.c', 'assist.c', 'assist-ui.c', 'build.c')]
        sources += ['c/calypsi/file-list.c', 'c/calypsi/fastbasic-diagnostic.c']
        arguments = [sys.executable, 'tools/build_c_program.py', '--output',
                     str(output/'application'), '--minimum-stack', '1312']
        for name in sources:
            arguments += ['--source', name]
        run(arguments, native)
        # Import the extracted helper in a fresh interpreter. This path does
        # not call prepare(), fetch archives, or use the development caches.
        run([sys.executable, '-c',
             'import sys;from pathlib import Path;sys.path.insert(0,"tools");'
             'from build_fastbasic import compile_program;'
             'compile_program(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),floating=True)',
             str(donor), str(native/'examples/fastbasic/HELLO.BAS'),
             str(output/'HELLO.COM')], native)
    expected = output/'expected.COM'
    from build_fastbasic import compile_program
    compile_program(ROOT/'build/fastbasic/source', ROOT/'examples/fastbasic/HELLO.BAS',
                    expected, floating=True)
    pairs = {'FBCI.COM': (donor/'build/bin/fbci.xex', ROOT/'build/fastbasic/FBCI.COM'),
             'FBC.COM': (donor/'build/bin/fbc.xex', ROOT/'build/fastbasic/FBC.COM'),
             'BASIC.APP': (output/'application/program.app', application),
             'HELLO.COM': (output/'HELLO.COM', expected)}
    products = {}
    for name, (rebuilt, original) in pairs.items():
        require(sha256(rebuilt) == sha256(original), 'Rebuilt bytes differ: '+name)
        products[name] = dict(bytes=rebuilt.stat().st_size, sha256=sha256(rebuilt))
    result = dict(status='pass', tier='development', qualification=False,
                  archive_sha256=sha256(archive), products=products, commands=commands,
                  network='No downloads; bundled donor/cc65 source and installed Calypsi 5.18',
                  application_inputs={name: sha256(native/name) for name in sources})
    (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--application', type=Path, required=True)
    args = parser.parse_args()
    check(args.archive.resolve(), args.output.resolve(), args.application.resolve())
