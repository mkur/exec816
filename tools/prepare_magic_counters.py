#!/usr/bin/env python3
"""Build and launch two copies of the shared Counter source on MagiC/Hatari."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from prepare_st_reference import ROOT, PIN, ADAPTER, run, sha256, checked_download


def parse_counter(source, instance):
    lines = source.splitlines()
    if not lines or lines[0] != f'instance={instance}':
        raise ValueError('Wrong or missing Counter instance header')
    pattern = re.compile(r'count=(\d+) paints=(\d+) id=(\d+) window=(\d+) top=(\d+) '
        r'work=(-?\d+),(-?\d+),(\d+),(\d+)')
    records = []
    for line in lines[1:]:
        match = pattern.fullmatch(line)
        if not match:
            raise ValueError('Malformed Counter observation or premature application exit')
        count, paints, app, window, top, x, y, w, h = map(int, match.groups())
        if records and (count != records[-1]['count']+1 or paints <= records[-1]['paints']):
            raise ValueError('Counter or repaint progress stopped')
        records.append(dict(count=count, paints=paints, app=app, window=window,
            top=top, work=[x,y,w,h]))
    if len(records)<6 or records[0]['count']!=0:
        raise ValueError('Insufficient Counter progress')
    if len({(row['app'],row['window']) for row in records}) != 1:
        raise ValueError('Counter identity changed')
    work = records[-1]['work']
    if any(row['work'] != work for row in records if row['paints']>0):
        raise ValueError('Counter geometry changed during the stationary capture')
    return records


def digit_pixels(framebuffer, work):
    if len(framebuffer)!=32000:
        raise ValueError('Expected the complete 640x400 monochrome framebuffer')
    x,y,w,h = work
    x+=64; y+=8
    if w<112 or h<16 or x<0 or x+48>640 or y<0 or y+8>400:
        raise ValueError('Counter digits are clipped or outside the screen')
    return bytes((framebuffer[row*80+col//8] >> (7-col%8))&1
        for row in range(y,y+8) for col in range(x,x+48))


def verify_capture(output):
    directory = output/'capture'
    launch = (directory/'LAUNCH.LOG').read_text().splitlines()
    if len(launch)!=2 or not re.fullmatch(r'magic=1 launcher=\d+',launch[0]):
        raise ValueError('MagiC did not start the demo launcher')
    match = re.fullmatch(r'first=(\d+) second=(\d+)',launch[1])
    if not match or int(match[1])<=0 or match[1]==match[2]:
        raise ValueError('MagiC did not launch two independent Counter processes')
    rows = [parse_counter((directory/f'COUNT{i}.LOG').read_text(),i) for i in (1,2)]
    if [row[-1]['app'] for row in rows] != [int(match[1]),int(match[2])]:
        raise ValueError('Counter application identities do not match the launched processes')
    if rows[0][-1]['window']==rows[1][-1]['window']:
        raise ValueError('Expected two different Counter windows')
    frames = [(directory/(name+'.bin')).read_bytes() for name in ('first','second')]
    cases = []
    for index, observations in enumerate(rows,1):
        a,b = (digit_pixels(frame,observations[-1]['work']) for frame in frames)
        changes = sum(x!=y for x,y in zip(a,b))
        if not changes:
            raise ValueError(f'Counter {index} displayed digits did not change between captures')
        inactive = [row['count'] for row in observations if row['paints']>0 and row['top']!=row['window']]
        cases.append(dict(instance=index, app=observations[-1]['app'],
            window=observations[-1]['window'], observations=observations,
            digit_pixels_changed=changes, inactive_counts=inactive))
    if not any(len(case['inactive_counts'])>=5 for case in cases):
        raise ValueError('Missing repeated painting by an inactive Counter')
    artifacts = [directory/'LAUNCH.LOG',directory/'COUNT1.LOG',directory/'COUNT2.LOG',
        *(directory/(name+suffix) for name in ('first','second') for suffix in ('.png','.bin'))]
    result = dict(status='pass',tier='development',qualification=False,counters=cases,
        artifacts={str(p.relative_to(output)):sha256(p) for p in artifacts})
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def clear_reports(output):
    for name in ('LAUNCH.LOG','COUNT1.LOG','COUNT2.LOG'):
        (output/'drive-c'/name).unlink(missing_ok=True)


def launch(output, record):
    """Fast-forward boot, then show both counters at their normal guest speed."""
    clear_reports(output)
    with tempfile.TemporaryDirectory(prefix='exec816-counters-',dir='/tmp') as directory:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
            address = str(Path(directory)/'control.sock')
            server.bind(address)
            server.listen(1)
            server.settimeout(10)
            with (output/'interactive-hatari.log').open('w') as log:
                process = subprocess.Popen([*record['command'],'--fast-forward','true',
                    '--control-socket',address],stdout=log,stderr=subprocess.STDOUT)
                try:
                    control,_ = server.accept()
                    with control:
                        deadline = time.monotonic()+30
                        while True:
                            if process.poll() is not None:
                                raise RuntimeError('Hatari exited during boot; see interactive-hatari.log')
                            if all((output/'drive-c'/f'COUNT{i}.LOG').exists() and
                                    'count=1 ' in (output/'drive-c'/f'COUNT{i}.LOG').read_text()
                                    for i in (1,2)):
                                break
                            if time.monotonic()>deadline:
                                raise RuntimeError('Counter startup timed out; see interactive-hatari.log')
                            time.sleep(.05)
                        control.sendall(b'hatari-option --fast-forward false\n')
                        print('Both counters are running. Cmd+Q quits Hatari on macOS.',flush=True)
                        process.wait()
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)


def prepare(args):
    output, cache = args.output.resolve(), args.cache.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pins = json.loads(PIN.read_text())
    sdk = cache/'sdk'
    cc, ld = sdk/'bin/m68k-atari-tos-gnu-gcc', sdk/'bin/m68k-atari-tos-gnu-ld'
    if not cc.exists() or not ld.exists():
        command = [sys.executable, ROOT/'tools/prepare_st_reference.py', '--output', cache,
            '--hatari', args.hatari]
        if args.offline:
            command.append('--offline')
        if args.rom:
            command += ['--rom', args.rom]
        run(command, output/'bootstrap.log')
    if run(['git', '-C', cache/'toslibc', 'rev-parse', 'HEAD']) != pins['toslibc']['revision']:
        raise RuntimeError('SDK source differs from the pinned revision')
    if run(['git', '-C', cache/'toslibc', 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('SDK source has tracked modifications')
    hatari = Path(shutil.which(args.hatari) or args.hatari).resolve()
    version = subprocess.run([hatari, '--version'], capture_output=True, text=True,
        timeout=10).stdout.strip().splitlines()[0]
    if not version.startswith('Hatari v'+pins['hatari_version']+' '):
        raise RuntimeError(f'Unexpected emulator: {version}')
    rom = Path(args.rom).resolve() if args.rom else hatari.parent.parent/'share/hatari/tos.img'
    if sha256(rom) != pins['rom']['sha256']:
        raise RuntimeError('EmuTOS ROM checksum differs from the pin')
    archive = cache/pins['magic']['release']
    checked_download(pins['magic']['url'], archive, pins['magic']['sha256'], args.offline)
    extracted = output/'inputs'
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (extracted/item.filename).resolve().is_relative_to(extracted):
                raise RuntimeError('Unsafe release archive path')
        z.extractall(extracted)
    drive = output/'drive-c'
    shutil.copytree(extracted/'MAGIC.A', drive, dirs_exist_ok=True)
    shutil.copytree(extracted/'MAGIC.A/LANG/EN', drive, dirs_exist_ok=True)
    (drive/'AUTO/MAGXBOOT.TOS').rename(drive/'AUTO/MAGXBOOT.PRG')
    objects = output/'objects'
    objects.mkdir(exist_ok=True)
    sources = dict(counter=ROOT/'examples/gem-counter/counter.c',
        bindings=ADAPTER/'bindings.c', main=ADAPTER/'counter-main.c',
        launcher=ADAPTER/'counter-launcher.c')
    for name, source in sources.items():
        run([cc, '-O2', '-Wall', '-ffunction-sections', '-fdata-sections',
            '-I'+str(ADAPTER/'include'), '-I'+str(ROOT/'c/include'), '-I'+str(ROOT),
            '-c', source, '-o', objects/(name+'.o')], objects/(name+'.log'))
    libgcc = run(['m68k-elf-gcc', '-m68000', '-print-libgcc-file-name'])
    libraries = [libgcc, '-L'+str(sdk/'lib'), '-lc', libgcc]
    counter = drive/'COUNTER.PRG'
    launcher = drive/'GEMSYS/GEMDESK/MAGXDESK.APP'
    run([ld, '-o', counter, '--wrap=evnt_multi', objects/'main.o', objects/'counter.o',
        objects/'bindings.o', *libraries], objects/'counter-link.log')
    run([ld, '-o', launcher, objects/'launcher.o', *libraries], objects/'launcher-link.log')
    command = [str(hatari), '--tos', str(rom), '--machine', 'st', '--memsize', '4',
        '--cpulevel', '0', '--cpuclock', '8', '--cpu-exact', 'true', '--monitor', 'mono',
        '--sound', 'off', '--confirm-quit', 'false', '--harddrive', str(drive),
        '--gemdos-case', 'upper', '--configfile', '/dev/null', '--statusbar', 'false',
        '--borders', 'false', '--log-level', 'warn']
    script = output/'launch-hatari.command'
    script.write_text('#!/bin/sh\nexec '+shlex.join([sys.executable,str(Path(__file__).resolve()),
        '--output',str(output),'--launch'])+' "$@"\n')
    script.chmod(0o755)
    (output/'README.txt').write_text(
        'Two Counter applications on MagiC in Hatari\n\n'
        'Run launch-hatari.command. Boot is fast-forwarded; normal speed resumes\n'
        'when both counters are running. Each window updates about once a second,\n'
        'including the inactive window. Click either title bar to change focus.\n'
        'Use the close box to close a counter. Cmd+Q quits Hatari on macOS;\n'
        'AltGr+Q quits elsewhere. F12 (possibly Fn+F12) opens Hatari settings.\n\n'
        'Close the demo before starting another instance. The original MagiC\n'
        'kernel and drivers run over pinned EmuTOS in ST monochrome mode. A small\n'
        'launcher occupies the desktop slot because Hatari host-folder drives\n'
        'lack the extended file API required by MagxDesk. It launches the same\n'
        'COUNTER.PRG twice using MagiC parallel execution, with arguments 1/2.\n\n'
        'Counter uses the unchanged examples/gem-counter/counter.c event loop.\n'
        'A test observer logs progress outside UPDATE to drive-c/COUNT1.LOG and\n'
        'COUNT2.LOG. This is a functional demo, not a performance benchmark.\n'
        'Automated captures and logs remain under capture/ across launches.\n')
    inputs = [Path(__file__).resolve(), PIN, *sources.values(),
        ROOT/'examples/gem-counter/counter.h', ADAPTER/'include/exec/types.h',
        ADAPTER/'include/string.h',
        ROOT/'c/include/gem.h', ROOT/'c/include/gem/objects.h',
        ROOT/'c/include/exec816/gem-constants.h']
    record = dict(pins=pins, hatari_version=version, hatari_sha256=sha256(hatari),
        rom_sha256=sha256(rom), compiler=run(['m68k-elf-gcc', '--version']).splitlines()[0],
        inputs={str(p.relative_to(ROOT)): sha256(p) for p in inputs}, command=command,
        binaries={str(p.relative_to(output)): sha256(p) for p in
            (counter, launcher, drive/'MAGIC.RAM', drive/'AUTO/MAGXBOOT.PRG')})
    (output/'build.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def capture(output, record):
    clear_reports(output)
    directory = output/'capture'
    directory.mkdir(exist_ok=True)
    (output/'results.json').unlink(missing_ok=True)
    scripts = []
    for frame, name in ((2400, 'first'), (3300, 'second')):
        for suffix in ('.png','.bin'):
            (directory/(name+suffix)).unlink(missing_ok=True)
        script = directory/(name+'.ini')
        script.write_text(f'screenshot {directory/name}.png\n'
            f'savebin {directory/name}.bin "($44e)" #32000\n'+('quit\n' if name=='second' else ''))
        scripts.append(f'b VBL = {frame} :once :trace :file {script}\n')
    boot = directory/'capture.ini'
    boot.write_text(''.join(scripts))
    run([*record['command'], '--fast-forward', 'true', '--parse', boot],
        directory/'hatari.log', timeout=90)
    for name in ('LAUNCH.LOG','COUNT1.LOG','COUNT2.LOG'):
        shutil.copy2(output/'drive-c'/name,directory/name)
    return verify_capture(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/magic-counters')
    parser.add_argument('--cache', type=Path, default=ROOT/'build/atari-st-reference')
    parser.add_argument('--hatari', default='hatari')
    parser.add_argument('--rom')
    parser.add_argument('--offline', action='store_true')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--run', action='store_true')
    action.add_argument('--launch', action='store_true',help='Launch an already prepared demo')
    args = parser.parse_args()
    output = args.output.resolve()
    if any(c.isspace() for c in str(output)):
        parser.error('Hatari debugger paths require an output path without whitespace')
    if args.launch:
        return launch(output,json.loads((output/'build.json').read_text()))
    record = prepare(args)
    if args.run:
        result = capture(output, record)
        for case in result['counters']:
            print(f"Counter {case['instance']}: count {case['observations'][-1]['count']}, "
                f"{case['digit_pixels_changed']} changed digit pixels")
    print(f'Launch: {output}/launch-hatari.command')


if __name__ == '__main__':
    main()
