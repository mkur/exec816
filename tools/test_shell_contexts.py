#!/usr/bin/env python3
"""Native context layout and concurrent resident shell isolation gates."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, verify_machine
from filesystem_formats import RAM
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out, mode, group, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    isolated = group == 'isolation'
    source = ROOT/'tests/programs'/('shell_contexts.act' if isolated
                                   else 'shell_context_layout.act')
    program = read_build(out) if reuse else build(
        compiler(ROOT/'build/actionc', release=True), source, out,
        optimize=mode == 'opt', tasks=True, task_capacity=8,
        console=isolated, console_deferred=not isolated,
        dos_mounts=[dict(alias='RAM', format=RAM, access='readwrite')] if isolated else [],
        memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        for key, value in PIN['configuration'].items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(bridge, program, timeout=240, frame_limit=12000)
        except Exception:
            print('Context checks', data(bridge, program['image'], 'checks', True), flush=True)
            raise
        require(data(bridge, program['image'], 'finished') == [1], 'Unfinished context fixture')
        if isolated:
            for slot in (0, 3):
                require(runtime['stack_observations'][slot]['untouched_above_floor'] >= 128,
                        'Resident shell missed the stack headroom gate')
        ownership(bridge, program, out)
        checks = data(bridge, program['image'], 'checks', True)[0]
    return dict(status='pass', tier='development', group=group, mode=mode,
                checks=checks, build=program['build'], runtime=runtime, machine=machine)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--group', choices=('layout', 'isolation'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.case, args.group, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell context checks passed', args.group, args.case, flush=True)
