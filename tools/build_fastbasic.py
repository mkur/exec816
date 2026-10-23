#!/usr/bin/env python3
"""Build pinned FastBasic sources and the Exec816 6502 target reproducibly."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT/'ports/fastbasic'
ABI = json.loads((ROOT/'abi/fastbasic.json').read_text())
PIN = json.loads((PORT/'upstream.json').read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(arguments, cwd, log):
    subprocess.run([str(x) for x in arguments], cwd=cwd, check=True,
                   stdout=log, stderr=subprocess.STDOUT)


def fetch(source, path):
    if not path.exists():
        raw = urllib.request.urlopen(source['url'], timeout=60).read()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('Changed source archive: '+source['url'])
        path.write_bytes(raw)
    if sha256(path) != source['sha256']:
        raise ValueError('Changed cached source: '+str(path))
    return path.read_bytes()


def extract(raw, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for item in archive.getmembers():
            parts = Path(item.name).parts[1:]
            if not parts:
                continue
            relative = Path(*parts)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Invalid archive path')
            path = destination/relative
            if item.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(item).read())
            else:
                raise ValueError('Unsupported archive member: '+item.name)


def archive_files(raw, prefix=''):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        return {prefix+'/'.join(Path(item.name).parts[1:]):
                hashlib.sha256(archive.extractfile(item).read()).hexdigest()
                for item in archive.getmembers() if item.isfile()}


def verify_files(root, expected):
    for name, digest in expected.items():
        path = root/name
        if not path.is_file() or sha256(path) != digest:
            raise ValueError('Modified cached source: '+str(path))


def profile(raw):
    """Host-side independent structural check of the exact target envelope."""
    if len(raw) < ABI['header_bytes']:
        raise ValueError('Truncated FastBasic header')
    magic, version, target, load, end, entry, limit = struct.unpack('<4s6H', raw[:16])
    if (magic, version, target) != (b'FB65', ABI['version'], ABI['target']):
        raise ValueError('Unsupported FastBasic executable')
    if load != ABI['load'] or limit != ABI['limit'] or not load <= entry < end <= limit:
        raise ValueError('Invalid FastBasic layout')
    if len(raw) != 16+end-load:
        raise ValueError('Invalid FastBasic extent')
    return dict(load=load, end=end, entry=entry, limit=limit, bytes=len(raw))


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    original = output/'upstream'
    raw = fetch(PIN['archive'], output/'upstream.tar.gz')
    mini = fetch(PIN['mini65'], output/'mini65.tar.gz')
    if not (original/'Makefile').exists():
        extract(raw, original)
        extract(mini, original/'testsuite/mini65')
    originals = {**archive_files(raw), **archive_files(mini, 'testsuite/mini65/')}
    verify_files(original, originals)
    patch = PORT/'patches/exec6502.patch'
    session_patch = PORT/'patches/session.patch'
    identities = {str(p.relative_to(ROOT)): sha256(p) for p in
                  [Path(__file__), ROOT/'tools/generate_fastbasic_math.py', ROOT/'tools/generate_fastbasic_interpreter.py', PORT/'upstream.json', ROOT/'abi/fastbasic.json', ROOT/'abi/fastbasic-interpreter.json', patch, session_patch,
                   *sorted((PORT/'target').glob('*'))] if p.is_file()}
    stamp = output/'port-inputs.json'
    source_stamp = output/'port-source.json'
    source = output/'source'
    if not stamp.exists() or json.loads(stamp.read_text()) != identities:
        if source.exists():
            # Only this build's generated source tree is replaced.
            if (source/'.git').exists() or not stamp.exists():
                raise ValueError('Refusing to replace an unowned source tree: '+str(source))
            shutil.rmtree(source)
        # Apply outside the enclosing Exec Git worktree: donor paths are local
        # to this generated tree, independent of the caller's Git prefix.
        with tempfile.TemporaryDirectory(prefix='exec816-fastbasic-') as temporary:
            staging = Path(temporary)/'source'
            extract(raw, staging)
            extract(mini, staging/'testsuite/mini65')
            with (output/'prepare.log').open('w') as log:
                command(['git', 'apply', '--check', patch], staging, log)
                command(['git', 'apply', patch], staging, log)
                command(['git', 'apply', '--check', session_patch], staging, log)
                command(['git', 'apply', session_patch], staging, log)
            shutil.move(staging, source)
        # Only the bootstrap compiler may emit calls to port-owned assembly.
        shutil.copy2(source/'src/syntax/basic.syn', source/'src/syntax/basic-internal.syn')
        basic = source/'src/syntax/basic.syn'
        basic.write_text('\n'.join(line for line in basic.read_text().splitlines()
                                   if '"USR("' not in line)+'\n')
        added = {}
        for name in ('atari-int-compiler.tgt', 'atari-fp-compiler.tgt'):
            added['compiler/'+name] = PORT/'target'/name
        for name in ('fastbasic.inc', 'helpers.asm', 'callbacks.asm', 'mathpack.asm', 'fp_snapshot.asm'):
            added['src/'+name] = PORT/'target'/name
        for name in ('source-run.asm','source-run.inc'):
            added['src/'+name] = PORT/'target'/name
        added['source-run.mak'] = PORT/'target/source-run.mak'
        for name, path in added.items():
            shutil.copy2(path, source/name)
        shutil.copy2(PORT/'target/exec.cfg', source/'compiler/fastbasic.cfg')
        shutil.copy2(PORT/'target/header.asm', source/'src/comp_header.asm')
        shutil.copy2(PORT/'target/cmdline.bas', source/'src/cmdline.bas')
        with (source/'Makefile').open('a') as makefile:
            makefile.write('\ninclude source-run.mak\n')
        names = set(originals) | set(added) | {'src/syntax/basic-internal.syn'}
        source_stamp.write_text(json.dumps({name: sha256(source/name)
                                            for name in sorted(names)}, indent=2)+'\n')
        stamp.write_text(json.dumps(identities, indent=2)+'\n')
    verify_files(source, json.loads(source_stamp.read_text()))
    return output, original, source, identities


def build(output):
    output, original, source, identities = prepare(output)
    with (output/'build.log').open('w') as log:
        command(['make', '-j4', 'build/bin/fastbasic', 'build/bin/ca65',
                 'build/bin/ld65', 'build/bin/ar65', 'build/gen/syntp',
                 'build/bin/fbci.xex', 'build/bin/fbc.xex', 'build/compiler/fastbasic-int.lib'], original, log)
        for name in ('bin/ca65', 'bin/ld65', 'bin/ar65', 'gen/syntp'):
            target = source/'build'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original/'build'/name, target)
        command(['make', '-j4', 'build/bin/fastbasic', 'build/bin/fbci.xex',
                 'build/bin/fbc.xex', 'build/compiler/fastbasic-int.lib',
                 'build/compiler/fastbasic-fp.lib', 'build/bin/fbrun.xex',
                 'build/bin/fbirun.xex'], source, log)
    compiler = source/'build/bin/fbci.xex'
    layout = profile(compiler.read_bytes())
    shutil.copy2(compiler, output/'FBCI.COM')
    compilers = {}
    for name in ('FBCI', 'FBC'):
        path = source/f'build/bin/{name.lower()}.xex'
        shutil.copy2(path, output/(name+'.COM'))
        compilers[name] = dict(profile=profile(path.read_bytes()), sha256=sha256(path))
    engines={}
    for name,stem in (('FB','fbrun'),('FBI','fbirun')):
        path=source/f'build/bin/{stem}.xex'
        shutil.copy2(path,output/(name+'.COM'))
        engines[name]=dict(profile=profile(path.read_bytes()),sha256=sha256(path))
    record = dict(format='exec816-fastbasic-build-v1', upstream=PIN,
                  inputs=identities, compiler=layout, compiler_sha256=sha256(compiler),
                  target=ABI['target'], compilers=compilers, engines=engines,
                  source_files=json.loads((output/'port-source.json').read_text()),
                  tools={name:sha256(source/'build/bin'/name) for name in
                         ('fastbasic', 'ca65', 'ld65', 'ar65')})
    (output/'build.json').write_text(json.dumps(record, indent=2)+'\n')
    return source, record


def compile_program(source, program, output, optimize=True, floating=False):
    source = Path(source).resolve()
    program, output = Path(program).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assembly, obj = output.with_suffix('.asm'), output.with_suffix('.o')
    with output.with_suffix('.log').open('w') as log:
        options = [] if optimize else ['-n']
        command([source/'build/bin/fastbasic', '-target-path:compiler',
                 '-syntax-path:src/syntax', '-t:atari-fp' if floating else '-t:atari-int', '-c', *options,
                 '-o', assembly, program], source, log)
        command([source/'build/bin/ca65', '-tatari', '-I', source/'cc65/asminc',
                 '-I', source/'src', '-o', obj, assembly], source, log)
        command([source/'build/bin/ld65', '-C', source/'compiler/fastbasic.cfg',
                 '-Ln', output.with_suffix('.lbl'), '-m', output.with_suffix('.map'),
                 '-o', output, source/f'build/obj/{"fp" if floating else "int"}/comp_header.o', obj,
                 source/f'build/compiler/fastbasic-{"fp" if floating else "int"}.lib'], source, log)
    return profile(output.read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/fastbasic')
    parser.add_argument('--compile', type=Path)
    parser.add_argument('--program-output', type=Path)
    parser.add_argument('--float', action='store_true', dest='floating', help='Compile an FP user program')
    args = parser.parse_args()
    source, record = build(args.output)
    if args.compile:
        target = args.program_output or args.compile.with_suffix('.COM')
        record['program'] = compile_program(source, args.compile, target, floating=args.floating)
    print(json.dumps(record, indent=2))
