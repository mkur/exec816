#!/usr/bin/env python3
"""Prepare and run a pinned Hatari/EmuTOS/MagiC shared-source GEM reference."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import statistics
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / 'toolchain/atari-st-reference.json'
SOURCE = ROOT / 'tests/programs/magic_aes_baseline.c'
ADAPTER = ROOT / 'tests/reference/atari-st'
COUNTS = (5, 33, 9)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log=None, timeout=300):
    result = subprocess.run([str(x) for x in command], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    if log:
        Path(log).write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f'{shlex.join([str(x) for x in command])}\n{result.stdout[-4000:]}')
    return result.stdout.strip()


def extract_workload(source):
    # read_text() normalizes CRLF before this newline-sensitive extraction.
    functions = []
    for name in ('work', 'draw_objects', 'object_tree'):
        matches = list(re.finditer(r'^static [^\n]+ '+name+r'\([^\n]*\)\n\{', source, re.M))
        if len(matches) != 1:
            raise ValueError(f'Expected one baseline function {name}')
        start = matches[0].start()
        end = source.index('\n}', matches[0].end()) + 2
        functions.append(source[start:end])
    return '\n\n'.join(functions) + '\n'


def parse_report(source, expected_magic=None):
    lines = source.splitlines()
    header = re.fullmatch(r'AES id=\d+ screen=640,400 colours=2 font=\d+,\d+,8,8 '
        r'clock=200 magic=([01])', lines[0]) if lines else None
    if len(lines) != 31 or not header:
        raise ValueError('Expected the complete 640x400 monochrome, 8x8-cell report')
    magic_cookie = bool(int(header[1]))
    if expected_magic is not None and magic_cookie != expected_magic:
        raise ValueError('MagiC cookie does not match the requested operating system')
    cases = []
    pattern = re.compile(r'case=(\d+) sample=(\d+) count=(\d+) visible=(\d+) okay=(\d+) '
        r'ticks=(\d+) work=(-?\d+),(-?\d+),(\d+),(\d+)')
    for kind, count in enumerate(COUNTS):
        ticks, rectangles = [], []
        for iteration in range(10):
            match = pattern.fullmatch(lines[1 + kind*10 + iteration])
            if not match:
                raise ValueError('Malformed reference sample')
            case, sample, objects, visible, okay, tick, x, y, w, h = map(int, match.groups())
            if (case, sample, objects, visible, okay) != (kind, iteration, count, 1, 1):
                raise ValueError('Failed, missing, repeated or reordered reference sample')
            if w < 336 or h < 144:
                raise ValueError('Work rectangle clips the sample canvas')
            ticks.append(tick)
            rectangles.append([x, y, w, h])
        if any(rect != rectangles[0] for rect in rectangles):
            raise ValueError('Work rectangle changed during the measured case')
        cases.append(dict(kind=kind, objects=count, samples=10, warmups=2,
            ticks=ticks, work=rectangles[0],
            elapsed_ms_median=statistics.median(ticks[2:])*5))
    return dict(clock_hz=200, timing_resolution_ms=5, magic_cookie=magic_cookie, cases=cases)


def checked_download(url, path, expected, offline):
    if not path.exists():
        if offline:
            raise RuntimeError(f'Missing cached download: {path}')
        temporary = path.with_suffix('.download')
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                temporary.write_bytes(response.read())
            if sha256(temporary) != expected:
                raise RuntimeError(f'Download checksum mismatch: {url}')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if sha256(path) != expected:
        raise RuntimeError(f'Cached input checksum mismatch: {path}')


def prepare(args, pins, output):
    hatari = Path(shutil.which(args.hatari) or args.hatari).resolve()
    # Hatari's --version reports success text with exit status 1.
    version = subprocess.run([str(hatari), '--version'], capture_output=True,
        text=True, timeout=10).stdout.strip().splitlines()[0]
    if not version.startswith('Hatari v'+pins['hatari_version']+' '):
        raise RuntimeError(f'Unexpected emulator: {version}')
    rom = Path(args.rom).resolve() if args.rom else hatari.parent.parent/'share/hatari/tos.img'
    if sha256(rom) != pins['rom']['sha256']:
        raise RuntimeError(f'Expected the pinned EmuTOS ROM: {rom}')
    for command in ('gcc-16', 'm68k-elf-gcc', 'make', 'git'):
        if not shutil.which(command):
            raise RuntimeError(f'Missing prerequisite: {command}; see docs/guides/atari-st-reference.md')
    output.mkdir(parents=True, exist_ok=True)
    sdk_source = output/'toslibc'
    if not sdk_source.exists():
        if args.offline:
            raise RuntimeError(f'Missing SDK checkout: {sdk_source}')
        run(['git', 'clone', pins['toslibc']['repository'], sdk_source])
        run(['git', '-C', sdk_source, 'checkout', '--detach', pins['toslibc']['revision']])
    if run(['git', '-C', sdk_source, 'rev-parse', 'HEAD']) != pins['toslibc']['revision']:
        raise RuntimeError('SDK checkout differs from the pinned revision')
    if run(['git', '-C', sdk_source, 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('SDK checkout has modified tracked inputs')
    sdk = output/'sdk'
    run(['make', '-C', sdk_source, 'CC=gcc-16', 'TARGET_COMPILE=m68k-elf-',
        f'prefix={sdk}', '-j8', 'install-lib', 'install-binutils', 'install-compiler'],
        output/'sdk-build.log')
    release = output/pins['magic']['release']
    checked_download(pins['magic']['url'], release, pins['magic']['sha256'], args.offline)
    for key, relative in (('license', 'MagiC-LICENSE.txt'), ('object_source', 'magic-source/AESOBJ.S')):
        path = output/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        item = pins['magic'][key]
        checked_download(item['url'], path, item['sha256'], args.offline)
    # Preserve upstream names, notices and the original archive. No ROM or
    # upstream binary is copied into the tracked repository or demo package.
    extracted = output/'magic-release'
    with zipfile.ZipFile(release) as archive:
        for entry in archive.infolist():
            path = extracted/entry.filename
            if not path.resolve().is_relative_to(extracted.resolve()):
                raise RuntimeError('Unsafe release archive path')
        archive.extractall(extracted)
    sample = output/'shared-sample'
    sample.mkdir(exist_ok=True)
    workload = sample/'workload.inc'
    workload.write_text(extract_workload(SOURCE.read_text()))
    cc = sdk/'bin/m68k-atari-tos-gnu-gcc'
    ld = sdk/'bin/m68k-atari-tos-gnu-ld'
    objects = []
    for name in ('main', 'bindings'):
        obj = sample/(name+'.o')
        run([cc, '-O2', '-Wall', '-ffunction-sections', '-fdata-sections',
            '-I'+str(ADAPTER/'include'), '-I'+str(ROOT/'c/include'),
            '-I'+str(ROOT), '-I'+str(sample), '-c', ADAPTER/(name+'.c'), '-o', obj],
            sample/(name+'-build.log'))
        objects.append(obj)
    libgcc = run(['m68k-elf-gcc', '-m68000', '-print-libgcc-file-name'])
    program = sample/'SAMPLE.PRG'
    # libgcc before libc avoids duplicate division helpers; repeat it for the
    # compiler helper dependencies introduced by libc, in standard link order.
    run([ld, '-o', program, *objects, libgcc, '-L'+str(sdk/'lib'), '-lc', libgcc],
        sample/'link.log')
    commands = {}
    for system in ('emutos', 'magic'):
        drive = output/'runtime'/('reference-'+system)/'drive-c'
        drive.mkdir(parents=True, exist_ok=True)
        if system == 'magic':
            upstream = extracted/'MAGIC.A'
            shutil.copytree(upstream, drive, dirs_exist_ok=True)
            shutil.copytree(upstream/'LANG/EN', drive, dirs_exist_ok=True)
            (drive/'AUTO/MAGXBOOT.TOS').rename(drive/'AUTO/MAGXBOOT.PRG')
            # Hatari lacks the Fxattr API needed by MagxDesk. Start this
            # resource-free sample in its desktop slot, leaving the kernel,
            # AES, VDI and drivers untouched. See upstream INSTALL.TXT.
            shutil.copy2(program, drive/'GEMSYS/GEMDESK/MAGXDESK.APP')
        shutil.copy2(program, drive/'SAMPLE.PRG')
        command = [str(hatari), '--tos', str(rom), '--machine', 'st', '--memsize', '4',
            '--cpulevel', '0', '--cpuclock', '8', '--cpu-exact', 'true',
            '--monitor', 'mono', '--sound', 'off', '--confirm-quit', 'false',
            '--harddrive', str(drive), '--gemdos-case', 'upper',
            '--configfile', '/dev/null', '--statusbar', 'false', '--borders', 'false',
            '--log-level', 'warn']
        if system == 'emutos':
            command += ['--auto', 'C:\\SAMPLE.PRG']
        commands[system] = command
        launcher = output/('launch-'+system+'.command')
        launcher.write_text('#!/bin/sh\nexec '+shlex.join(command)+' "$@"\n')
        launcher.chmod(0o755)
    inputs = [Path(__file__).resolve(), PIN, SOURCE, ROOT/'examples/gem-counter/counter.c',
        ROOT/'examples/gem-counter/counter.h', ROOT/'c/include/gem.h',
        ROOT/'c/include/gem/objects.h', ROOT/'c/include/exec816/gem-constants.h',
        *sorted(ADAPTER.rglob('*.c')),
        *sorted(ADAPTER.rglob('*.h'))]
    record = dict(pins=pins, hatari=dict(version=version, executable=str(hatari),
        sha256=sha256(hatari)), rom=dict(path=str(rom), sha256=sha256(rom)),
        compiler=run(['m68k-elf-gcc', '--version']).splitlines()[0],
        host_compiler=run(['gcc-16', '--version']).splitlines()[0],
        inputs={str(p.relative_to(ROOT)): sha256(p) for p in inputs},
        workload_sha256=sha256(workload), program_sha256=sha256(program), commands=commands)
    magic_drive = output/'runtime/reference-magic/drive-c'
    record['magic_runtime'] = {name: sha256(magic_drive/name) for name in
        ('MAGIC.RAM', 'MAGX.INF', 'AUTO/MAGXBOOT.PRG', 'GEMSYS/GEMDESK/MAGXDESK.APP')}
    (output/'installation.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def capture(output, record, system):
    directory = output/'runtime'/('reference-'+system)
    report = directory/'drive-c/REPORT.TXT'
    report.unlink(missing_ok=True)  # A previous successful run cannot mask a failed boot.
    screenshot = directory/'screen.png'
    framebuffer = directory/'screen.bin'
    screenshot.unlink(missing_ok=True)
    framebuffer.unlink(missing_ok=True)
    snapshot = directory/'snapshot.ini'
    snapshot.write_text(f'screenshot {screenshot}\nsavebin {framebuffer} "($44e)" #32000\nquit\n')
    boot = directory/'boot.ini'
    boot.write_text(f'b VBL = 1500 :once :trace :file {snapshot}\n')
    run([*record['commands'][system], '--fast-forward', 'true', '--parse', boot],
        directory/'hatari.log', timeout=90)
    parsed = parse_report(report.read_text(), expected_magic=(system == 'magic'))
    if framebuffer.stat().st_size != 32000 or not screenshot.exists():
        raise RuntimeError('Missing final monochrome screen capture')
    parsed.update(report_sha256=sha256(report), screen_sha256=sha256(screenshot),
        framebuffer_sha256=sha256(framebuffer))
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/atari-st-reference')
    parser.add_argument('--hatari', default='hatari')
    parser.add_argument('--rom', help='Exact pinned EmuTOS ROM, if not beside the Hatari installation')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--run', choices=('emutos', 'magic', 'both'))
    args = parser.parse_args()
    output = args.output.resolve()
    if any(c.isspace() for c in str(output)):
        parser.error('Hatari debugger script paths require an output path without whitespace')
    record = prepare(args, json.loads(PIN.read_text()), output)
    if args.run:
        systems = ('emutos', 'magic') if args.run == 'both' else (args.run,)
        results = {system: capture(output, record, system) for system in systems}
        (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
        for system, result in results.items():
            print(system, 'elapsed medians (ms):',
                [case['elapsed_ms_median'] for case in result['cases']])
    print(f'Reference ready: {output}/launch-magic.command')


if __name__ == '__main__':
    main()
