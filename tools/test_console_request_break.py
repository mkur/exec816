#!/usr/bin/env python3
"""Owned hidden-console cancellation, handoff, generations and exact cleanup."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    program = read_build(out) if reuse else build(
        compiler(ROOT/'build/actionc', release=True),
        ROOT/'tests/programs/console_request_break.act', out,
        optimize=True, tasks=True, task_capacity=8, console=True, dos_mounts=[],
        memory_profile=memory)
    saved = {}
    with emulator(ROOT/'build/shell-paced-bridge',
                  ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        for key, value in PIN['configuration'].items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before(b):
            saved.update(screen=b.peek16(88), cursor=b.peek(752), mask=b.peek(16))
            saved['bytes'] = b.memdump(saved['screen'], 960)

        try:
            runtime, _ = execute(bridge, program, before_run=before,
                                 timeout=240, frame_limit=12000)
        except Exception:
            print('Owner cancellation checks/phase',
                  data(bridge, program['image'], 'checks', True),
                  data(bridge, program['image'], 'phase'), flush=True)
            raise
        require(data(bridge, program['image'], 'finished') == [1], 'Unfinished owner cancellation')
        require(bridge.memdump(saved['screen'], 960) == saved['bytes']
                and bridge.peek(752) == saved['cursor'] and bridge.peek(16) == saved['mask'],
                'Owner cancellation did not restore OS display')
        ownership(bridge, program, out)
        checks = data(bridge, program['image'], 'checks', True)[0]
    return dict(status='pass', tier='development', mode='opt', checks=checks,
                build=program['build'], runtime=runtime, machine=machine, pin=PIN)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Console owner cancellation passed', result['checks'], flush=True)
