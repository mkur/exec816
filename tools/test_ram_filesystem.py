#!/usr/bin/env python3
"""Public RAM-only DOS operations, far binary bytes and complete heap retirement."""
import argparse
import json
import struct
from pathlib import Path

from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(toolchain, output, mode='opt', layout_only=False):
    output.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 4096
    memory_profile = output/'memory-profile.json'
    memory_profile.write_text(json.dumps(profile, indent=2)+'\n')
    program = build(toolchain, ROOT/'tests/programs/ram_filesystem.act', output,
                    tasks=True, task_capacity=8, console_deferred=True,
                    memory_profile=memory_profile, optimize=mode == 'opt',
                    dos_mounts=[dict(alias='RAM', format=3)])
    def words(bridge, name):
        symbol = next(d for d in program['image']['data']
                      if '_RAMTEST_'+name.upper()+'_' in d['name'])
        raw = bridge.memdump(symbol['address'], symbol['size'])
        return list(struct.unpack('<'+'H'*(len(raw)//2), raw))

    with emulator(ROOT/'build/altirra-sio-multi',
                  ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)

        def before_run(bridge):
            if layout_only:
                address = next(d['address'] for d in program['image']['data']
                               if '_RAMTEST_LAYOUTONLY_' in d['name'])
                bridge.poke(address, 1)

        try:
            runtime, _ = execute(bridge, program, timeout=600, frame_limit=12000,
                                 before_run=before_run)
        except Exception:
            print('RAM failure phase/checks:', words(bridge, 'phase'),
                  words(bridge, 'checks'), flush=True)
            raise
        ownership(bridge, program, output)
        observed = {name: words(bridge, name)
                    for name in ('checks', 'phase', 'layouts')}
        address = next(d['address'] for d in program['image']['data']
                       if '_RAMTEST_PARTIAL_' in d['name'])
        observed['partial_write_bytes'] = int.from_bytes(bridge.memdump(address, 4), 'little')
        require(observed['phase'] == [6], 'Incomplete RAM fixture')
        require(observed['layouts'][:4] == [52, 14, 3, 42]
                and observed['layouts'][5] == 3, 'Changed RAM record layout')
        require(runtime['created'] == 2, 'RAM volume started an additional device Task')
        return dict(status='pass', mode=mode, layout_only=layout_only,
                    build=program['build'], runtime=runtime, machine=machine,
                    observed=observed,
                    bank_zero_reservation_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--layout-only', action='store_true')
    parser.add_argument('--compiler-bin', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    toolchain = compiler(ROOT/'build/actionc')
    if args.compiler_bin:
        toolchain['binary'] = args.compiler_bin.resolve()
        toolchain['binary_sha256'] = sha256(toolchain['binary'])
    result = run(toolchain, args.output.resolve(), args.case, args.layout_only)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('RAM filesystem passed', args.case, result['observed'], flush=True)
