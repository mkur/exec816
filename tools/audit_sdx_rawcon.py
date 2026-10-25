#!/usr/bin/env python3
"""Bound emitted uninterrupted RAWCON paths; asynchronous paths have VM probes.

Counts instructions and physical stack bytes, not elapsed CPU time. Serial/pointer
trace and replay measure the actual bus and interrupt effects separately.
"""
import argparse
import json
from pathlib import Path

from native_program import read_build, require


def bound(program):
    labels = program['labels']
    memory = {}
    for segment in program['image']['segments']:
        memory.update((segment['address'] + i, byte)
                      for i, byte in enumerate(segment['bytes']))
    # The synthetic SIO fixture supplies the production nineteen-byte veneers.
    start = 0x30f681
    require(memory.get(start) == 0x78, 'Missing production veneer SEI')
    reject = labels['sdx_probe_detach']
    restore = labels['sdx_probe_guest_restore']
    require(memory[restore] == 0xaf, 'Changed pending-work restore boundary')
    pending_branch = restore + 4
    require(memory[pending_branch] == 0xd0, 'Changed pending-work branch')
    best = {}; active = set(); completed = []

    def visit(pc, m8, x8, emulation, carry, depth, count, peak):
        if pc == reject:
            return
        state = pc, m8, x8, emulation, carry, depth
        require(state not in active, 'Unbounded control cycle in fast cell')
        if best.get(state, -1) >= count:
            return
        best[state] = count
        active.add(state)
        opcode = memory[pc]
        size = 1
        if opcode in (0xc2, 0xe2):
            size = 2
            mask = memory[pc + 1]
            if mask & 0x20: m8 = opcode == 0xe2
            if mask & 0x10: x8 = opcode == 0xe2
        elif opcode in (0xa9, 0xc9, 0x29, 0x69, 0x09):
            size = 2 if m8 else 3
        elif opcode in (0xa2, 0xa0, 0xe0, 0xc0):
            size = 2 if x8 else 3
        elif opcode in (0xaf, 0xbf, 0x8f, 0x9f, 0xcf, 0xdf, 0x6f, 0x7f):
            size = 4
        elif opcode in (0xad, 0xbd, 0x8d, 0x9d):
            size = 3
        elif opcode in (0xa5, 0x85, 0xa6, 0xc5, 0x05, 0xa3, 0x83):
            size = 2
        elif opcode == 0xf4:
            size = 3
            depth += 2
        elif opcode in (0x48, 0xda, 0x5a, 0x0b, 0x8b, 0x08):
            depth += {0x48: 1 if m8 else 2, 0xda: 1 if x8 else 2,
                      0x5a: 1 if x8 else 2, 0x0b: 2, 0x8b: 1, 0x08: 1}[opcode]
        elif opcode in (0x68, 0xfa, 0x7a, 0x2b, 0xab, 0x28):
            depth -= {0x68: 1 if m8 else 2, 0xfa: 1 if x8 else 2,
                      0x7a: 1 if x8 else 2, 0x2b: 2, 0xab: 1, 0x28: 1}[opcode]
            if opcode == 0x28:
                require(emulation, 'Unreviewed native PLP mode change')
        elif opcode == 0x18:
            carry = False
        elif opcode == 0x38:
            carry = True
        elif opcode == 0xfb:
            require(carry is not None, 'Unreviewed XCE mode')
            emulation, carry = carry, emulation
            if emulation: m8 = x8 = True
        elif opcode in (0x78, 0xd8, 0xa8, 0xaa, 0x8a, 0x98, 0xeb,
                        0x1a, 0xea, 0x5b, 0x3b):
            pass
        elif opcode in (0x0a, 0x4a):
            carry = None
        elif opcode == 0x40:
            require(emulation and depth == 3, 'Guest frame did not retire exactly')
            completed.append(dict(instructions=count + 1, peak_bytes=peak,
                                  temporary_below_complete_frame=peak - 13))
            active.remove(state)
            return
        elif opcode not in (0x4c, 0x5c, 0x10, 0x30, 0x50, 0x70,
                            0x90, 0xb0, 0xd0, 0xf0, 0x80):
            raise RuntimeError(f'Unreviewed emitted opcode ${opcode:02x} at ${pc:06x}')
        peak = max(peak, depth)
        require(depth >= 0, 'Unbalanced physical frame')
        if opcode in (0x4c, 0x5c):
            size = 3 if opcode == 0x4c else 4
            target = sum(memory[pc + i] << (8 * (i - 1)) for i in range(1, size))
            if opcode == 0x4c: target |= pc & 0xff0000
            targets = [target]
        elif opcode in (0x10, 0x30, 0x50, 0x70, 0x90, 0xb0, 0xd0, 0xf0, 0x80):
            size = 2
            delta = memory[pc + 1]
            if delta >= 128: delta -= 256
            target = (pc & 0xff0000) | ((pc + 2 + delta) & 65535)
            targets = [pc + 2] if pc == pending_branch else [target] if opcode == 0x80 else [pc + 2, target]
        else:
            targets = [pc + size]
        for target in targets:
            visit(target, m8, x8, emulation, carry, depth, count + 1, peak)
        active.remove(state)

    # JSR return + first PHP already exist when SEI is observed.
    visit(start, True, True, True, None, 3, 0, 3)
    require(completed, 'No successful production cell path')
    result = dict(status='bounded', tier='development', qualification=False,
                  maximum_instructions=max(v['instructions'] for v in completed),
                  maximum_temporary_bytes=max(v['temporary_below_complete_frame'] for v in completed),
                  complete_frame_bytes=13, acknowledge_nmi_bytes=13,
                  scope='Uninterrupted successful get/put; pending-work detachment and failures excluded; both conditional successors otherwise traversed',
                  states=len(best), image_sha256=program['build']['image_sha256'])
    require(result['maximum_temporary_bytes'] == 4, 'Changed leaf temporary depth')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = bound(read_build(args.program.resolve()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], result['maximum_instructions'], 'instructions;',
          result['maximum_temporary_bytes'], 'temporary bytes')
