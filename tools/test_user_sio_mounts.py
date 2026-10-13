#!/usr/bin/env python3
"""Focused emitted user-mount lifecycle checks on the pinned SIO setup."""
import argparse
import json
import shutil
from pathlib import Path

from generate_memory import PROFILE
from generate_dos_mounts import encode
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN
from mydos_fixtures import Image
import adapter_state as adapter


def run(output, scenario, reuse=None):
    output.mkdir(parents=True, exist_ok=True)
    media = output / 'volume.atr'
    shutil.copyfile(ROOT / 'tests/fixtures/mydos/mydos450-128.atr', media)
    if scenario in ('lazy-failure', 'recovery'):
        image = Image(media.read_bytes())
        image.data[image.offset(360)] = 0
        media.write_bytes(image.data)
    digest = sha256(media)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 4096
    memory = output / 'memory.json'
    memory.write_text(json.dumps(profile, indent=2) + '\n')
    mounts = [dict(alias='RAM', format=3),
              dict(alias='D2', format=1, unit=50, profile=1,
                   sectors=720, sector_bytes=128)]
    if scenario == 'empty':
        mounts = []
    elif scenario.startswith('lazy'):
        mounts = mounts[:1]
    program = read_build(reuse) if reuse else build(compiler(ROOT / 'build/actionc', release=True),
                    ROOT / 'tests/programs/user_sio_mounts.act', output,
                    optimize=True, tasks=True, task_capacity=8,
                    console_deferred=True, memory_profile=memory, dos_mounts=mounts)
    if reuse:
        for name, expected_hash in program['build'].get('task_inputs', {}).items():
            require(sha256(ROOT / name) == expected_hash, 'Stale reused mount build: ' + name)
        shutil.copyfile(reuse / 'manifest.bin', output / 'manifest.bin')
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        bridge.config('diskemu', 'fastest')
        bridge.mount(1, str(media))
        try:
            def before(bridge):
                base = program['build']['task_storage']['BASE']
                bridge.memload(base + 0x883, bytes([len(mounts)]))
                if mounts:
                    bridge.memload(base + 0x900, encode(mounts))
                values = dict(scenario=3 if scenario == 'recovery' else 1 if scenario == 'empty' else 2 if scenario.startswith('lazy') else 0,
                              expected=225 if scenario == 'lazy-failure' else 0)
                for name, value in values.items():
                    symbol = next(d for d in program['image']['data']
                                  if '_USERMOUNTS_' + name.upper() + '_' in d['name'])
                    bridge.memload(symbol['address'], value.to_bytes(symbol['size'], 'little'))
            runtime, _ = execute(bridge, program, before_run=before, timeout=180, frame_limit=9000)
        except Exception:
            print('User mount checks:', data(bridge, program['image'], 'checks', True), flush=True)
            raw = bridge.memdump(adapter.STATE, 128)
            (output / 'failure-state.bin').write_bytes(raw)
            print('Native adapter state:', raw.hex(), flush=True)
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
    parser.add_argument('--scenario', choices=('registry', 'empty', 'lazy', 'lazy-failure', 'recovery'), default='registry')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    run(args.output.resolve(), args.scenario, args.from_build.resolve() if args.from_build else None)
