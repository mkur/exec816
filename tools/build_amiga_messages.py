#!/usr/bin/env python3
"""Build the shared C example with classic Amiga headers; optionally run it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from native_program import ROOT, require, sha256

PIN = json.loads((ROOT/'toolchain/amiga-messages.json').read_text())
SUCCESS = b'PASS 60,70 same message\n' * 3


def tree_hash(directory):
    """Identify the SDK inputs actually supplied to compiler and linker."""
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode()+b'\0')
            digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def checked_tool(name):
    path = shutil.which(name)
    require(path is not None, 'Missing Amiga tool: '+name)
    path = Path(path).resolve()
    require(sha256(path) == PIN['tools'][name]['sha256'], 'Amiga tool differs from pin: '+name)
    return path


def build(output, target, ndk):
    output.mkdir(parents=True, exist_ok=True)
    target, ndk = target.resolve(), ndk.resolve()
    tools = {name: checked_tool(name) for name in ('vc', 'vbccm68k', 'vasmm68k_mot', 'vlink')}
    for name, directory in (('target_include', target/'include'), ('target_lib', target/'lib'), ('ndk_include', ndk)):
        require(directory.is_dir(), 'Missing SDK directory: '+str(directory))
        require(tree_hash(directory) == PIN['sdk_trees'][name], 'SDK differs from pin: '+name)
    # vc invokes compiler/assembler commands through its config. Quote paths
    # for that shell as well as passing the outer vc invocation as an argv list.
    import shlex
    q = lambda path: shlex.quote(str(path))
    cfg = output/'vbcc.cfg'
    cfg.write_text(
        f'-cc={q(tools["vbccm68k"])} -quiet %s -o= %s %s -O=%ld -I{q(target/"include")}\n'
        f'-as={q(tools["vasmm68k_mot"])} -quiet -Fhunk -nowarn=62 %s -o %s\n'
        '-rm=rm -f %s\n'
        f'-ld={q(tools["vlink"])} -bamigahunk -x -Bstatic -Cvbcc -nostdlib -mrel '
        f'{q(target/"lib/startup.o")} %s %s -L{q(target/"lib")} -lvc -o %s\n'
        '-ldnodb=-s -Rshort\n-ul=-l%s\n-cf=-F%s\n-ml=500\n-hunkdebug\n-amiga-softfloat\n')
    driver = [str(tools['vc']), '+'+str(cfg)]
    flags = ['-O2', '-cpu=68000', '-I'+str(ndk)]
    source = ROOT/'c/examples/messages.c'
    observer = ROOT/'c/amiga/observe.c'
    commands = [
        [*driver, *flags, '-Dmain=ExecMessageMain', '-c', str(source), '-o', str(output/'messages.o')],
        [*driver, *flags, '-c', str(observer), '-o', str(output/'observe.o')],
        [*driver, str(output/'messages.o'), str(output/'observe.o'), '-lamiga', '-lauto', '-o', str(output/'MessageDemo')],
    ]
    with (output/'build.log').open('w') as log:
        for command in commands:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    record = dict(shared_source='c/examples/messages.c', source_sha256=sha256(source),
                  observer_sha256=sha256(observer), executable_sha256=sha256(output/'MessageDemo'),
                  executable_bytes=(output/'MessageDemo').stat().st_size, compiler_flags=flags,
                  entry_rename='main=ExecMessageMain', global_addressing='absolute; no small-data/A4 model',
                  commands=commands, tools={name: dict(path=str(path), sha256=sha256(path)) for name, path in tools.items()},
                  sdk_trees=PIN['sdk_trees'])
    (output/'build.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def run(output, record, rom, exec_results=None):
    emulator = checked_tool('fs-uae')
    rom = rom.resolve()
    require(sha256(rom) == PIN['rom']['sha256'], 'Kickstart ROM differs from pin')
    system = output/'system'
    (system/'S').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(output/'MessageDemo', system/'MessageDemo')
    (system/'S/Startup-Sequence').write_text('SYS:MessageDemo\n')
    for name in ('results.txt', 'results.tmp'):
        (system/name).unlink(missing_ok=True)
    cfg = output/'amiga.fs-uae'
    cfg.write_text('[fs-uae]\n'+''.join(f'{key} = {value}\n' for key, value in PIN['settings'].items())+
                   f'kickstart_file = {rom}\nhard_drive_0 = {system}\nlogs_dir = {output/"logs"}\n')
    report = dict(status='running', build=record, pin=PIN, config_sha256=sha256(cfg),
                  bank_zero_delta=dict(fixed=0, per_task=0))
    if exec_results is not None:
        previous = json.loads(exec_results.read_text())
        require(previous['status'] == 'pass', 'Exec816 run did not pass')
        foreign = previous['build']['foreign_image']
        require(foreign['source_inputs']['c/examples/messages.c'] == record['source_sha256'],
                'Exec816 and Amiga sources differ')
        report['exec816'] = dict(results_sha256=sha256(exec_results),
                                image_sha256=previous['build']['image_sha256'],
                                c_elf_sha256=foreign['elf_sha256'], output=previous['output'])
    started = time.monotonic()
    try:
        with (output/'emulator.log').open('w') as log:
            process = subprocess.Popen([str(emulator), str(cfg)], stdout=log, stderr=subprocess.STDOUT)
            try:
                result = system/'results.txt'
                while not result.exists():
                    require(process.poll() is None, 'FS-UAE exited before publishing the result')
                    require(time.monotonic()-started < 45, 'Amiga message example timed out')
                    time.sleep(0.1)
                observed = result.read_bytes()
                require(observed == SUCCESS, 'Amiga example failed: '+repr(observed))
                # Check effective UAE settings, not just requested FS-UAE options.
                effective = (output/'logs/debug.uae').read_text()
                for setting in ('cpu_model=68000', 'chipmem_size=2', 'fastmem_size=4', 'cpu_speed=real'):
                    require(setting in effective.splitlines(), 'Unexpected runtime: '+setting)
                report.update(status='pass', output=observed.decode().splitlines(), completed_invocations=3,
                              effective_config_sha256=sha256(output/'logs/debug.uae'))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True, help='vbcc targets/m68k-amigaos directory')
    parser.add_argument('--ndk', type=Path, required=True, help='NDK Include_H directory')
    parser.add_argument('--output', type=Path, default=ROOT/'build/amiga-messages')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--rom', type=Path, help='Local licensed Kickstart 2.04 ROM, required with --run')
    parser.add_argument('--exec-results', type=Path, help='Passing test_calypsi results.json to verify the shared source hash')
    args = parser.parse_args()
    require(not args.run or args.rom is not None, '--run requires --rom')
    output = args.output.resolve()
    record = build(output, args.target, args.ndk)
    if args.run:
        run(output, record, args.rom, args.exec_results)
        print('Amiga message example passed: three invocations')
    else:
        print('Amiga executable ready:', output/'MessageDemo')


if __name__ == '__main__':
    main()
