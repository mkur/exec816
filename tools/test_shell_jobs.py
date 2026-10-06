#!/usr/bin/env python3
"""One shell-owned loaded background job, real disks and eight-slot admission."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_command import compile_command
from make_data_disk import make
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership


def run(out, compiler_dir, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    t = compiler(compiler_dir)
    commands = {}
    for name, source in [('HELLO', 'examples/commands/hello.act'),
                         ('CAT', 'examples/commands/cat.act'),
                         ('WC', 'examples/commands/wc.act'),
                         ('ECHOARGS', 'examples/commands/echoargs.act'),
                         ('WAIT', 'tests/programs/disk_delay.act'),
                         ('CONQUERY', 'tests/programs/disk_conquery.act')]:
        commands[name] = compile_command(t, ROOT/source, out/'media/C'/name)
        for suffix in ('options', 'profile'):
            (out/'media/C'/f'{name}.{suffix}.json').rename(out/f'{name}.{suffix}.json')
    make(out/'system.atr', out/'media', binary_names={f'C/{n}' for n in commands},
         filesystem='sdfs', sector_bytes=256, sectors=2880)
    work = out/'work-source'
    work.mkdir(exist_ok=True)
    (work/'INPUT.TXT').write_text('inherited streams\n')
    make(out/'work.atr', work, filesystem='sdfs', sector_bytes=256, sectors=2880)
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 4096
    (out/'memory.json').write_text(json.dumps(profile))
    source = ROOT/'tests/programs/shell_jobs.act'
    p = read_build(out) if reuse else build(t, source, out, optimize=True,
              tasks=True, task_capacity=8, console=True, memory_profile=out/'memory.json',
              system_mount='D1', dos_mounts=[
                  dict(alias='D1', unit=49, sectors=2880, sector_bytes=256, profile=4, format=2),
                  dict(alias='WORK', unit=56, sectors=2880, sector_bytes=256,
                       profile=4, format=2, access='readwrite')])
    require(p['build']['source_sha256'] == sha256(source), 'Changed replay fixture')
    for group in ('task_inputs', 'console_inputs', 'banked_inputs'):
        for name, expected in p['build'].get(group, {}).items():
            require(sha256(ROOT/name) == expected, 'Changed replay input: '+name)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    bridge, rom = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
    with emulator(bridge, rom, out, pin=pin) as b:
        for key, value in pin['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.config('diskemu', 'generic56k')
        b.mount(0, str(out/'system.atr'))
        b.mount(7, str(out/'work.atr'))
        machine = verify_machine(b, rom, pin)
        try:
            runtime, _ = execute(b, p, timeout=240, frame_limit=12000)
        except Exception:
            print('Job checks:', data(b, p['image'], 'checks', True), flush=True)
            shell = int.from_bytes(bytes(data(b, p['image'], 'shell')), 'little')
            print('Shell:', b.memdump(shell, 128).hex(), flush=True)
            print('Job:', data(b, p['image'], 'job'), flush=True)
            print('Adapter:', b.memdump(adapter.STATE,64).hex(), flush=True)
            raise
        require(data(b, p['image'], 'finished') == [1], 'Job fixture incomplete')
        ownership(b, p, out)
    return dict(status='pass', tier='development', runtime=runtime, build=p['build'],
                machine=machine, commands=commands, runner_sha256=sha256(Path(__file__)),
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.compiler_dir, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell background job checks passed', flush=True)
