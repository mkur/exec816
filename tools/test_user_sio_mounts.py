#!/usr/bin/env python3
"""Focused emitted user-mount lifecycle checks on the pinned SIO setup."""
import argparse
import json
import shutil
import os
from pathlib import Path

from generate_memory import PROFILE
from generate_dos_mounts import encode
from sio_transaction_trace import read_events,checksum
from sio_adapter_trace import transmit_bursts
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN
from mydos_fixtures import Image
import adapter_state as adapter


def run(output, scenario, reuse=None, trace=True):
    output.mkdir(parents=True, exist_ok=True)
    media = output / 'volume.atr'
    if scenario == 'discover-sparta':
        from make_data_disk import make
        contents = output / 'contents'
        contents.mkdir(exist_ok=True)
        make(media, contents, filesystem='sdfs', sectors=720, sector_bytes=128)
    else:
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
              dict(alias='D2', format=1, unit=50, profile=4,
                   sectors=720, sector_bytes=128)]
    if scenario == 'empty':
        mounts = []
    elif scenario.startswith('lazy') or scenario.startswith('discover') or scenario in ('geometry', 'public', 'bounds', 'no-sio'):
        mounts = mounts[:1]
    program = read_build(reuse) if reuse else build(compiler(ROOT / 'build/actionc', release=True),
                    ROOT / 'tests/programs/user_sio_mounts.act', output,
                    optimize=True, tasks=True, task_capacity=8,
                    console_deferred=True, memory_profile=memory, dos_mounts=mounts,
                    sio_enabled=scenario != 'no-sio')
    if reuse:
        for name, expected_hash in program['build'].get('task_inputs', {}).items():
            require(sha256(ROOT / name) == expected_hash, 'Stale reused mount build: ' + name)
        shutil.copyfile(reuse / 'manifest.bin', output / 'manifest.bin')
    discovering = scenario.startswith('discover')
    tracing = discovering and trace
    if tracing:
        os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='1',
                          EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in program['labels'].items()
                                                    if k.startswith(('sio_', 'native_'))))
    binary = 'build/altirra-sio-multi-observer' if tracing else 'build/altirra-sio-multi'
    with emulator(ROOT / binary,
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        for key, value in PIN['configuration'].items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        bridge.config('diskemu', '810' if scenario == 'discover-fallback' else 'generic56k')
        bridge.mount(1, str(media))
        try:
            def before(bridge):
                if tracing:
                    bridge.profile_start()
                base = program['build']['task_storage']['BASE']
                bridge.memload(base + 0x883, bytes([len(mounts)]))
                if mounts:
                    bridge.memload(base + 0x900, encode(mounts))
                values = dict(scenario=9 if scenario == 'no-sio' else 8 if scenario == 'bounds' else 7 if scenario == 'replacement' else 6 if scenario == 'public' else 5 if discovering else 4 if scenario == 'geometry' else 3 if scenario == 'recovery' else 1 if scenario == 'empty' else 2 if scenario.startswith('lazy') else 0,
                              expected=225 if scenario == 'lazy-failure' else 0,
                              fallback=int(scenario == 'discover-fallback'),
                              format=2 if scenario == 'discover-sparta' else 1)
                for name, value in values.items():
                    symbol = next(d for d in program['image']['data']
                                  if '_USERMOUNTS_' + name.upper() + '_' in d['name'])
                    bridge.memload(symbol['address'], value.to_bytes(symbol['size'], 'little'))
            runtime, _ = execute(bridge, program, before_run=before, timeout=180, frame_limit=9000)
            if tracing:
                bridge.profile_stop()
        except Exception:
            print('User mount checks:', data(bridge, program['image'], 'checks', True), flush=True)
            from banked_test_memory import read
            storage = program['build']['memory']['dos_storage']
            print('DOS caller slots:', read(bridge, storage['BASE'], storage['BYTES'], output).hex(), flush=True)
            raw = bridge.memdump(adapter.STATE, 128)
            (output / 'failure-state.bin').write_bytes(raw)
            print('Native adapter state:', raw.hex(), flush=True)
            raise
        ownership(bridge, program, output)
        require(data(bridge, program['image'], 'finished') == [1], 'Incomplete user mount checks')
        checks = data(bridge, program['image'], 'checks', True)
        sizes = {name: data(bridge, program['image'], name, True)
                 for name in ('serviceBytes','mountBytes')}
    require(sha256(media) == digest, 'Mount checks modified media')
    wire = None
    if tracing:
        events = read_events(output / 'emulator.log')
        start = next(t for t, e in events if e[0] == 'cpu' and
                     int(e[4], 16) == program['labels']['sio_start'])
        events = [(t, e) for t, e in events if t >= start]
        frames = [[int(e[2]) for _,e in ready] for ready,_,_ in
                  transmit_bursts(events, require)]
        wire = [frame for frame in frames if len(frame)==5 and frame[0]==50]
        expected_frames = [[50,0x52,1,0],[50,0x53,0,0],[50,0x4e,0,0]]
        if scenario != 'discover-sparta':
            expected_frames.append([50,0x52,0x68,1])
        require(wire == [frame+[checksum(frame)] for frame in expected_frames],
                'Wrong discovery wire order or additional disk I/O: ' + str(wire))
    report = dict(status='pass', tier='development', scenario=scenario, machine=machine,
                  build=program['build'], runtime=runtime, checks=checks, media_sha256=digest,
                  sizes=sizes, wire_frames=wire,
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('User mount checks passed:', scenario, checks, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('registry', 'empty', 'lazy', 'lazy-failure', 'recovery', 'geometry', 'discover-mydos', 'discover-sparta', 'discover-fallback', 'public', 'replacement', 'bounds', 'no-sio'), default='registry')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--no-trace', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.scenario, args.from_build.resolve() if args.from_build else None, not args.no_trace)
