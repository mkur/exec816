#!/usr/bin/env python3
"""Bounded native-v2 workspace preservation and domain-reuse regression."""
import argparse
import adapter_state as adapter
import json
import struct
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_heap_api import clean_ownership

PIN = json.loads((ROOT / 'toolchain/altirra-shell-paced.json').read_text())


def run(output, mode, capacity=4, from_build=None, nmi=0):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'program').mkdir(exist_ok=True)
    source = output / 'program/probe.act'
    source.write_text(read_source(ROOT / 'tests/programs/dp_partition.act'))
    if from_build:
        program = read_build(from_build)
        require(program['build']['source_sha256'] == sha256(source) and
                program['build']['optimize'] == (mode == 'opt') and
                program['build']['task_storage']['CAPACITY'] == capacity and
                program['build']['probe_nmi'] == nmi,
                'Reused DP fixture differs')
    else:
        toolchain = compiler(ROOT / 'build/actionc')
        program = build(toolchain, source, output / 'program', tasks=True,
                        optimize=mode == 'opt', task_capacity=capacity, probe_nmi=nmi)
    kernel_pattern = bytes((index * 37 + 17) & 255 for index in range(128))
    bridge_dir = ROOT / 'build/shell-paced-bridge'
    rom = ROOT / 'build/firmware/altirraos-816.rom'
    with emulator(bridge_dir, rom, output, pin=PIN) as bridge:
        machine = verify_machine(bridge, rom, PIN)

        pools = program['build']['memory']['task_pools']
        c = program['build']['task_storage']
        routine = next(r for r in program['image']['routines']
                       if r['name'].startswith('M_TASKPOLICY_PREPAREDOMAIN_'))
        entry, end = routine['address'], routine['address']+routine['size']-5
        segment = next(s for s in program['image']['segments']
                       if s['address'] <= end < s['address']+len(s['bytes']))
        entry_bytes = bytes(segment['bytes'][entry-segment['address']:entry-segment['address']+4])
        exit_bytes = bytes(segment['bytes'][end-segment['address']:end-segment['address']+5])
        require(entry_bytes == bytes([0x3b,0xaa,0xc5,0xc6]) and
                exit_bytes == bytes([0x69,routine['fixed_frame'],0,0x1b,0x6b]),
                'PrepareDomain prologue/epilogue shape changed')
        # The pinned bridge supports bank-zero breakpoints only. Relocate whole
        # prologue/epilogue instructions to two temporary bank-zero rendezvous.
        # JML preserves flags and adds no stack bytes; the body is unmodified.
        probe = 0x2e00
        require(all(probe+32 <= r['address'] or probe >= r['address']+r['size']
                    for r in program['build']['memory']['runtime_reservations']),
                'DP observer overlaps runtime storage')
        jump = lambda address: bytes([0x5c])+address.to_bytes(3,'little')
        saved = {}
        observations = []
        idle_pattern = bytes(index ^ 0x3d for index in range(128))
        tail = pools[-1]['dp']+256

        def stop(b, address):
            b.bp_clear_all()
            b.bp_set(address)
            try:
                run_to(b, address, frame_limit=1500, timeout=30)
            except Exception:
                print(dict(initialization=observations,status=b.peek16(adapter.STATUS),
                           checks=data(b,program['image'],'checks',True),
                           ready=data(b,program['image'],'readyCount'),
                           finished=data(b,program['image'],'finished')),flush=True)
                raise
            b.bp_clear_all()

        def observe(b, initial):
            stop(b, probe+4)
            stack = b.peek16(probe+30)
            owner = int.from_bytes(b.memdump(stack+4,3),'little')
            slot = (owner-c['BASE'])//c['SIZE']
            require(owner == c['BASE']+slot*c['SIZE'] and 0 <= slot <= capacity,
                    'Unknown initialization owner')
            if not observations:
                # Only inactive Task pages are poisoned. The kernel is already
                # executing and retains valid metadata and reserved-zero bytes.
                for i,pool in enumerate(pools):
                    b.memload(pool['dp'],bytes(((index*17+i*31+1) % 255)+1 for index in range(256)))
                saved['tail'] = b.memdump(tail,256)
                b.memload(tail,bytes([0x6d])*256)
            previous = None
            if initial and slot:
                # Earlier Task pages are initialized but still inactive. Poison
                # the preceding page, including its last byte, for this one
                # call; restore its valid domain before any Task can execute.
                previous = b.memdump(pools[slot-1]['dp'],256)
                b.memload(pools[slot-1]['dp'],bytes([0xa7])*256)
            before = [b.memdump(p['dp'],256) for p in pools]
            kernel = b.memdump(adapter.KERNEL_DP,256)
            stop(b, probe+16)
            pool = pools[slot]
            expected = bytearray(256)
            expected[0xc0:0xc8] = owner.to_bytes(3,'little')+struct.pack('<BHH',0,
                pool['stack_base']+256,pool['stack_base']+pool['stack_bytes']-1)
            require(b.memdump(pool['dp'],256) == expected,
                    f'DP initialization extent/metadata differs: slot {slot}')
            for other,p in enumerate(pools):
                if other != slot:
                    require(b.memdump(p['dp'],256) == before[other],
                            f'Initializing slot {slot} changed neighbour {other}')
            after = b.memdump(adapter.KERNEL_DP,256)
            require(after[:128] == kernel[:128] and after[192:] == kernel[192:],
                    'Task initialization changed the kernel domain')
            require(b.memdump(tail,256) == bytes([0x6d])*256,
                    'Initialization exceeded the last DP')
            if previous is not None:
                b.memload(pools[slot-1]['dp'],previous)
            observations.append(dict(slot=slot,phase='startup' if initial else 'admission',
                                     exact_page=True,neighbours_intact=True))

        def seed_kernel(b):
            saved['probe'] = b.memdump(probe,32)
            b.memload(probe,bytes([0x3b,0x8d])+(probe+30).to_bytes(2,'little')+entry_bytes+jump(entry+4))
            b.memload(probe+16,exit_bytes)
            b.memload(entry,jump(probe))
            b.memload(end,jump(probe+16)+bytes([0xea]))
            stop(b, program['labels']['general_domains'])
            neighbours = (adapter.KERNEL_DP-256,adapter.KERNEL_DP+256)
            originals = [b.memdump(address,256) for address in neighbours]
            for address in (adapter.KERNEL_DP,*neighbours):
                b.memload(address,bytes([0x79])*256)
            stop(b, program['labels']['general_domains_done'])
            expected = bytearray(256)
            expected[0xc0:0xc8] = adapter.KERNEL_OWNER.to_bytes(3,'little')+struct.pack('<BHH',1,0x4b00,0x4fff)
            require(b.memdump(adapter.KERNEL_DP,256) == expected,
                    'Kernel bootstrap did not initialize exactly its DP')
            for address,original in zip(neighbours,originals):
                require(b.memdump(address,256) == bytes([0x79])*256,
                        'Kernel bootstrap changed a neighbouring page')
                b.memload(address,original)
            for _ in range(capacity+1):
                observe(b, True)
            require([o['slot'] for o in observations] == list(range(capacity+1)),
                    'Startup did not initialize every domain')
            stop(b, program['labels']['startup_complete'])
            b.memload(adapter.KERNEL_DP, kernel_pattern)
            b.memload(pools[-1]['dp'], idle_pattern)
            for _ in range(capacity):
                observe(b, False)
            require([o['slot'] for o in observations[capacity+1:]] ==
                    list(range(1,capacity))+[2], 'Missing interior-slot reuse')
            b.memload(tail,saved['tail'])

        runtime, _ = execute(bridge, program, before_run=seed_kernel,
                             frame_limit=3000, timeout=180)
        bridge.memload(entry,entry_bytes)
        bridge.memload(end,exit_bytes)
        bridge.memload(probe,saved['probe'])
        require(data(bridge, program['image'], 'finished') == [1], 'Fixture did not finish')
        require(runtime['created'] == capacity and runtime['vbi_dispatches'] > 0,
                'Missing task reuse or VBI preemption')
        require(bridge.memdump(adapter.KERNEL_DP, 128) == kernel_pattern, 'Kernel workspace changed')
        require(bridge.memdump(pools[-1]['dp'],128) == idle_pattern, 'Idle workspace changed')
        clean_ownership(bridge, program, program["output"])
        checks = int.from_bytes(bytes(data(bridge, program['image'], 'checks')), 'little')
    return dict(status='pass', tier='development', mode=mode, capacity=capacity, nmi_checkpoint=nmi, build=program['build'],
                runtime=runtime, checks=checks, kernel_initialization='exact page; neighbours intact', initialization=observations, machine=machine, platform=PIN,
                emulator_sha256=sha256(bridge_dir / 'AltirraBridgeServer'),
                bank_zero_delta=dict(fixed=0, per_task=0),
                observer=dict(temporary_bank_zero_bytes=288,code_and_state_bytes=32,boundary_sentinel_bytes=256,
                              address=probe,boundary_address=tail,restored=True,
                              entry=entry,exit=end,entry_bytes=entry_bytes.hex(),exit_bytes=exit_bytes.hex()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--nmi', type=int, choices=(0,15), default=0)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--capacity', type=int, choices=(4,8), default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(output, args.mode, args.capacity, args.from_build, args.nmi)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('DP partition passed:', args.mode, result['checks'], 'checks')
