#!/usr/bin/env python3
"""Focused COP coordination checks and complete public-call timing at PAL 8x."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import statistics
import shutil

from native_program import ROOT, build, command, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from sio_latency import BASE_HZ
from test_cooperative import data
from test_heap_api import clean_ownership
from test_signal_concurrency import read_events
from test_signals_irq import PIN
from test_banked import changed_image


def native_context_cases(program, output, bridge_dir, rom):
    """One assembly overlay, nine runtime selections, no compiler rebuilds."""
    shutil.copytree(program['output'], output/'program', dirs_exist_ok=True)
    probe = read_build(output/'program')
    entry = probe['image']['entry']
    address = lambda name: next(d['address'] for d in probe['image']['data'] if '_'+name+'_' in d['name'])
    defines = dict(RESULT=address('PORT'), VARIANT=address('SCENARIO'), REACHED=address('CHECKS'),
                   PERMIT=probe['labels']['tasks_permit'])
    base = probe['output']
    (base/'context.cfg').write_text(f'MEMORY {{ RAM: start=${entry:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65', '-I', base, *[v for k,a in defines.items() for v in ('-D',f'{k}={a}')],
             '-o', base/'context.o', ROOT/'tests/programs/kernel_fast_context.s'])
    command(['ld65', '-C', base/'context.cfg', '-o', base/'context.bin', base/'context.o'])
    blob = (base/'context.bin').read_bytes()
    segment = next(s for s in probe['image']['segments'] if s['address'] == entry)
    require(len(blob) <= len(segment['bytes']), 'Native context overlay exceeds Main')
    segment['bytes'][:len(blob)] = blob
    changed_image(probe)
    results = []
    with emulator(bridge_dir.resolve(), rom.resolve(), output, pin=PIN) as bridge:
        for variant in range(9):
            fault = variant not in (0, 8)
            runtime, _ = execute(bridge, probe, expected_status=4 if fault else 0,
                                 before_run=lambda b: b.memload(defines['VARIANT'],bytes([variant])), timeout=180)
            reached = int.from_bytes(bytes(data(bridge, probe['image'], 'checks')), 'little')
            require(reached == (0 if fault else 1), 'Native context returned unexpectedly')
            snapshot = bytes(data(bridge, probe['image'], 'port'))
            if not fault:
                word = lambda offset: int.from_bytes(snapshot[offset:offset+2], 'little')
                require((word(0),word(2),word(4),word(6),word(8),snapshot[10],snapshot[11]) ==
                        (0x15,0x1234,probe['build']['task_storage']['PROFILE_TAG']|0xab,
                         word(16),word(14)-1,0x12,9+(4 if variant==8 else 0)),
                        'Fast native register/flag restoration: '+snapshot.hex())
            results.append(dict(variant=variant,runtime=runtime,snapshot=snapshot.hex()))
        # Reuse the same emitted kernel and clone for invalid dequeue packets.
        command(['ca65', '-I', base, *[v for k,a in defines.items() for v in ('-D',f'{k}={a}')],
                 '-o', base/'get-fault.o', ROOT/'tests/programs/kernel_fast_get_fault.s'])
        command(['ld65', '-C', base/'context.cfg', '-o', base/'get-fault.bin', base/'get-fault.o'])
        blob = (base/'get-fault.bin').read_bytes()
        require(len(blob) <= len(segment['bytes']), 'GetMsg fault overlay exceeds Main')
        segment['bytes'][:len(blob)] = blob
        changed_image(probe)
        for variant in range(10):
            runtime, _ = execute(bridge, probe, expected_status=4,
                                 before_run=lambda b: b.memload(defines['VARIANT'],bytes([variant])), timeout=180)
            require(data(bridge, probe['image'], 'checks') == [0,0], 'Invalid GetMsg returned')
            snapshot = bytes(data(bridge, probe['image'], 'port'))
            require(snapshot[16:24] == bytes(8), 'Invalid GetMsg changed queue links')
            results.append(dict(family='getmsg-fault',variant=variant,runtime=runtime))
    return results


def markers_for(program):
    labels = program['labels']
    markers = {}
    for name in ('tasks_forbid', 'tasks_permit', 'ports_get_msg'):
        markers[name] = labels[name]
        markers[name + '_return'] = labels[name + '_end'] - 1  # RTL instruction
    for name in ('dispatch_call', 'fast_complete', 'fast_general'):
        if name in labels:
            markers[name] = labels[name]
    for name in ('MEASURE', 'MEASURED'):
        matches = [r['address'] for r in program['image']['routines']
                   if r['name'].startswith('M_KERNELFAST_' + name + '_')]
        require(len(matches) == 1, 'Missing measurement boundary: ' + name)
        markers[name] = matches[0]
    return markers


def timing(events, markers):
    reverse = {pc: name for name, pc in markers.items()}
    pending, samples, paths = {}, defaultdict(list), Counter()
    depth, sequence_start, sequences = Counter(), {}, []
    measuring = False
    for tick, fields in events:
        if fields[0] != 'cpu':
            continue
        name = reverse.get(int(fields[4], 16))
        if name == 'MEASURE':
            measuring = True
        if name == 'MEASURED':
            break
        if not measuring or name is None:
            continue
        # Public stubs preserve their entry S until their final RTL. Pair by
        # stack, so a suspended caller cannot consume another Task's return.
        stack = int(fields[8], 16)
        if name.endswith('_return'):
            call = name.removesuffix('_return')
            begin = pending.pop((call, stack), None)
            require(begin is not None, 'Unmatched public-call return')
            samples[call].append((tick - begin) * 8 + 6)  # include RTL's six CPU cycles
            if call == 'tasks_permit':
                depth[stack] -= 1
                require(depth[stack] >= 0, 'Unmatched measured Permit')
                if depth[stack] == 0:
                    sequences.append((tick-sequence_start.pop(stack))*8+6)
        elif name in ('tasks_forbid', 'tasks_permit', 'ports_get_msg'):
            require((name, stack) not in pending, 'Overlapping public call')
            pending[name, stack] = tick
            if name == 'tasks_forbid':
                if depth[stack] == 0:
                    sequence_start[stack] = tick
                depth[stack] += 1
        elif name in ('dispatch_call', 'fast_complete', 'fast_general'):
            paths[name] += 1
    require(not pending, 'Incomplete public call')
    require({n: len(v) for n, v in samples.items()} ==
            dict(tasks_forbid=32, tasks_permit=32, ports_get_msg=48), 'Missing measured calls')
    require(len(sequences) == 16 and not sequence_start, 'Incomplete claim/exclusion sequence')
    return dict(paths=dict(paths), nested_claim_sequence=dict(count=len(sequences),
                median_us=statistics.median(sequences)/(8*BASE_HZ)*1e6,
                scope='Two Forbid, three GetMsg, active-pointer publication/clear, two Permit and fixture assertions'),
                calls={name: dict(count=len(values),
                min_cpu_cycles=min(values), median_cpu_cycles=statistics.median(values),
                max_cpu_cycles=max(values), median_us=statistics.median(values) / (8 * BASE_HZ) * 1e6)
                for name, values in samples.items()})


def run(program, output, bridge_dir, rom, scenario, observed):
    markers = markers_for(program)
    previous = {key: os.environ.get(key) for key in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    try:
        if observed:
            os.environ['EXEC816_LATENCY_TRACE'] = '1'
            os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in markers.values())
        else:
            for key in previous:
                os.environ.pop(key, None)
        with emulator(bridge_dir.resolve(), rom.resolve(), output, pin=PIN) as bridge:
            machine = verify_machine(bridge, rom, PIN)
            def before(b):
                at = next(d['address'] for d in program['image']['data'] if '_SCENARIO_' in d['name'])
                b.memload(at, bytes([scenario]))
                if observed:
                    b.profile_start()
            runtime, _ = execute(bridge, program, before_run=before, frame_limit=3000, timeout=180)
            checks = int.from_bytes(bytes(data(bridge, program['image'], 'checks')), 'little')
            require(checks == 81 + 6 * bool(scenario), 'Coordination checks: ' + str(checks))
            clean_ownership(bridge, program, program['output'])
            result = dict(runtime=runtime, checks=checks, machine=machine)
        if observed:
            result['timing'] = timing(read_events(output/'emulator.log'), markers)
        return result
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    p.add_argument('--bridge-dir', type=Path, default=ROOT/'build/shell-paced-bridge')
    p.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mode', choices=('raw', 'opt'), required=True)
    p.add_argument('--from-build', type=Path)
    p.add_argument('--probe-nmi', type=int, default=0, choices=(0, 19, 20, 21, 22, 23, 24))
    p.add_argument('--native-context', action='store_true')
    args = p.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    program = read_build(args.from_build) if args.from_build else build(
        compiler(args.compiler_dir), ROOT/'tests/programs/kernel_fast_paths.act',
        output/'program', tasks=True, optimize=args.mode == 'opt', probe_nmi=args.probe_nmi)
    require(program['build']['optimize'] == (args.mode == 'opt'), 'Build mode mismatch')
    report = dict(status='running', mode=args.mode, build=program['build'], platform=PIN,
                  emulator_sha256=sha256(args.bridge_dir/'AltirraBridgeServer'), cases=[])
    try:
        for scenario in (0, 1):
            observed = run(program, output/f'{scenario}-observed', args.bridge_dir, args.rom, scenario, True)
            replay = run(program, output/f'{scenario}-replay', args.bridge_dir, args.rom, scenario, False)
            require(observed['runtime'] == replay['runtime'] and observed['checks'] == replay['checks'],
                    'Identical-image replay differs')
            report['cases'].append(dict(scenario=scenario, observed=observed, replay=replay))
        if args.native_context:
            report['native_context'] = native_context_cases(program, output/'native-context', args.bridge_dir, args.rom)
        report['status'] = 'pass'
        print(args.mode + ': two scenarios and identical-image replays passed', flush=True)
        print(json.dumps(report['cases'][0]['observed']['timing'], indent=2), flush=True)
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
