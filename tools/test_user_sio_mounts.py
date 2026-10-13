#!/usr/bin/env python3
"""Focused emitted user-mount lifecycle checks on the pinned SIO setup."""
import argparse
import json
import shutil
from pathlib import Path

from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(output, scenario):
    output.mkdir(parents=True, exist_ok=True)
    media = output / 'volume.atr'
    shutil.copyfile(ROOT / 'tests/fixtures/mydos/mydos450-128.atr', media)
    digest = sha256(media)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 4096
    memory = output / 'memory.json'
    memory.write_text(json.dumps(profile, indent=2) + '\n')
    mounts = [dict(alias='RAM', format=3),
              dict(alias='D2', format=1, unit=50, profile=1,
                   sectors=720, sector_bytes=128)]
    program = build(compiler(ROOT / 'build/actionc', release=True),
                    ROOT / 'tests/programs/user_sio_mounts.act', output,
                    optimize=True, tasks=True, task_capacity=8,
                    console_deferred=True, memory_profile=memory, dos_mounts=mounts)
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        bridge.config('diskemu', 'fastest')
        bridge.mount(1, str(media))
        try:
            runtime, _ = execute(bridge, program, timeout=180, frame_limit=9000)
        except Exception:
            print('User mount checks:', data(bridge, program['image'], 'checks', True), flush=True)
            raise
        ownership(bridge, program, output)
        require(data(bridge, program['image'], 'finished') == [1], 'Incomplete user mount checks')
        checks = data(bridge, program['image'], 'checks', True)
    require(sha256(media) == digest, 'Mount checks modified media')
    report = dict(status='pass', tier='development', scenario=scenario, machine=machine,
                  build=program['build'], runtime=runtime, checks=checks, media_sha256=digest,
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('User mount checks passed:', scenario, checks, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('registry',), default='registry')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.scenario)
