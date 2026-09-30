#!/usr/bin/env python3
"""Bounded native-v2 workspace preservation and domain-reuse regression."""
import argparse
import json
from pathlib import Path

from library_paths import read_source
from native_abi import FIELDS
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_heap_api import clean_ownership

PIN = json.loads((ROOT / 'toolchain/altirra-shell-paced.json').read_text())


def run(output, mode):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'program').mkdir(exist_ok=True)
    source = output / 'program/probe.act'
    source.write_text(read_source(ROOT / 'tests/programs/dp_partition.act'))
    toolchain = compiler(ROOT / 'build/actionc')
    program = build(toolchain, source, output / 'program', tasks=True,
                    optimize=mode == 'opt')
    kernel_pattern = bytes((index * 37 + 17) & 255 for index in range(128))
    bridge_dir = ROOT / 'build/shell-paced-bridge'
    rom = ROOT / 'build/firmware/altirraos-816.rom'
    with emulator(bridge_dir, rom, output, pin=PIN) as bridge:
        machine = verify_machine(bridge, rom, PIN)

        def seed_kernel(b):
            # The first user entry follows kernel/domain initialization.
            entry = program['labels']['general_task_start']
            b.bp_set(entry)
            run_to(b, entry, timeout=90)
            b.bp_clear_all()
            b.memload(0x2600 + FIELDS['caller_workspace']['offset'], kernel_pattern)

        runtime, _ = execute(bridge, program, before_run=seed_kernel,
                             frame_limit=3000, timeout=180)
        require(data(bridge, program['image'], 'finished') == [1], 'Fixture did not finish')
        require(runtime['created'] == 2 and runtime['vbi_dispatches'] > 0,
                'Missing task reuse or VBI preemption')
        require(bridge.memdump(0x2600, 128) == kernel_pattern, 'Kernel workspace changed')
        clean_ownership(bridge, program, program["output"])
        checks = int.from_bytes(bytes(data(bridge, program['image'], 'checks')), 'little')
    return dict(status='pass', tier='development', mode=mode, build=program['build'],
                runtime=runtime, checks=checks, machine=machine, platform=PIN,
                emulator_sha256=sha256(bridge_dir / 'AltirraBridgeServer'),
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(output, args.mode)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('DP partition passed:', args.mode, result['checks'], 'checks')
