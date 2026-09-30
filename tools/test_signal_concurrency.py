#!/usr/bin/env python3
"""Measure IRQ byte deadlines with concurrent kernel work; retain failing baselines.

Default success means measurement/functional integrity, NOT a baud qualification.
Use --require-deadline to make any serial deadline miss fail the command as well.
Every observed run replays the identical XEX on the uninstrumented emulator.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
import os
from pathlib import Path

from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator
from sio_latency import BASE_HZ
from test_cooperative import data
from test_signal_stream import stats
from test_signals_irq import PIN

WORKLOADS = ('compute', 'yield', 'signals', 'sleep', 'mixed', 'allocate', 'fragment', 'clear', 'ports')
COUNTERS = ('sent', 'waits', 'background', 'yields', 'requests', 'replies', 'sleeps', 'blocked')
ENVIRONMENT = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')


def read_events(path):
    """Only parse the observer records: bridge logs also contain credentials."""
    result = []
    tick = 0
    masked = None
    with path.open() as source:
        for line in source:
            if '[SIOPOC] ' not in line:
                continue
            fields = line.split('[SIOPOC] ', 1)[1].split()
            value = int(fields[1])
            fraction = 0
            if fields[0] in ('cpu', 'mask'):
                value += round((tick - value) / (1 << 32)) * (1 << 32)
                require(int(fields[3]) == 8, 'Unexpected observer clock multiplier')
                fraction = int(fields[2]) / int(fields[3])
            tick = value
            if fields[0] == 'mask':
                masked = bool(int(fields[5], 16) & 4)
            elif fields[0] == 'cpu' and masked is not None:
                require(bool(int(fields[11], 16) & 4) == masked,
                        'CPU status disagrees with I-transition trace')
            result.append((value + fraction, fields))
    return result


def masked_intervals(trace, start, end):
    """Clip alternating CPU-microstate I transitions to the hardware stream."""
    transitions = [(t, e) for t, e in trace if e[0] == 'mask']
    require(transitions and transitions[0][0] <= start and transitions[-1][0] >= end,
            'Mask trace does not cover the stream')
    intervals = []
    for (a, entry), (b, leave) in zip(transitions, transitions[1:]):
        masked = bool(int(entry[5], 16) & 4)
        require(masked != bool(int(leave[5], 16) & 4), 'Duplicate I state in mask trace')
        require(b >= a, 'Nonmonotonic mask trace')
        if masked and a < end and b > start:
            intervals.append(dict(start_tick=max(a, start), end_tick=min(b, end),
                                  duration_us=(min(b, end)-max(a, start))/BASE_HZ*1e6,
                                  entry_pc=int(entry[4], 16), instruction_pc=int(entry[7], 16),
                                  opcode=int(entry[8], 16), exit_pc=int(leave[4], 16),
                                  irq=bool(int(entry[9])), nmi=bool(int(entry[10])),
                                  clipped=a < start or b > end))
    require(intervals, 'No masked intervals observed')
    return intervals


def markers_for(program):
    markers = {n: program['labels'][n] for n in (
        'native_irq', 'native_nmi', 'signal_route_begin', 'signal_route_return',
        'signal_post', 'signal_post_return', 'signal_irq_window', 'heap_clear_begin', 'heap_clear_end')}
    for name in ('fast_complete', 'fast_general'):
        if name in program['labels']:
            markers[name] = program['labels'][name]
    for name in ('tasks_forbid', 'tasks_permit', 'ports_get_msg'):
        markers[name] = program['labels'][name]
        markers[name+'_return'] = program['labels'][name+'_end']-1
    for routine in program['image']['routines']:
        for prefix in ('M_TASKPOLICY_', 'M_SIGNALCONCURRENT_', 'M_HEAPCORE_', 'M_HEAPPOLICY_'):
            if routine['name'].startswith(prefix):
                name = prefix[2:-1] + '.' + routine['name'][len(prefix):].split('_')[0]
                require(name not in markers, 'Ambiguous routine marker: ' + name)
                markers[name] = routine['address']
    return markers


def public_call_latencies(trace, markers, start, end):
    """Complete public calls within the wire interval, paired by native stack.

    Values include IRQ/NMI and time spent descheduled; they are elapsed latency,
    not exclusive execution costs. Discard calls crossing the interval edges.
    """
    entries = {markers[n]: n for n in ('tasks_forbid', 'tasks_permit', 'ports_get_msg')}
    returns = {markers[n+'_return']: n for n in entries.values()}
    pending, samples = {}, defaultdict(list)
    for tick, fields in trace:
        if fields[0] != 'cpu' or not start <= tick <= end:
            continue
        pc, stack = int(fields[4], 16), int(fields[8], 16)
        if pc in entries:
            pending[entries[pc], stack] = tick
        elif pc in returns:
            name = returns[pc]
            begin = pending.pop((name, stack), None)
            if begin is not None and tick + 6/8 <= end:
                samples[name].append(tick - begin + 6/8)
    return {name: stats(values) for name, values in samples.items()}


def serial_timing(trace, count):
    ready = [(t, e) for t, e in trace if e[0] == 'ready']
    writes = [(t, e) for t, e in trace if e[0] == 'write']
    require(len(ready) == len(writes) == count, 'Missing/extra POKEY byte events')
    expected = [i & 255 for i in range(count)]
    require([int(e[2]) for _, e in ready] == expected, 'Incorrect transmitted bytes')
    require([int(e[2]) for _, e in writes] == expected, 'Incorrect SEROUT bytes')
    require(all(int(e[3]) == 14 for _, e in ready), 'Incorrect POKEY divisor')
    require(all(int(e[4]) == 0 for _, e in writes), 'SEROUT overwritten')
    idle = [t for t, e in trace if e[0] == 'idle']
    end = ready[-1][0] + 140
    require(idle and idle[-1] == end, 'Last byte did not finish')
    latency = [w[0]-r[0] for r, w in zip(ready, writes[1:])]
    gaps = [b[0]-a[0]-140 for a, b in zip(ready, ready[1:])]
    require(min(latency) >= 0 and min(gaps) >= 0, 'Nonmonotonic serial timestamps')
    misses = sum(x >= 140 for x in latency)
    timing = dict(target_baud=125000, actual_baud=BASE_HZ/14, deadline_us=140/BASE_HZ*1e6,
                  ready_to_refill=stats(latency), deadline_misses=misses,
                  gaps=sum(x > 0 for x in gaps), max_gap_us=max(gaps)/BASE_HZ*1e6,
                  verdict='pass' if misses == 0 and max(gaps) == 0 else 'fail',
                  start_tick=writes[0][0], end_tick=end,
                  duration_us=(end-writes[0][0])/BASE_HZ*1e6)
    rows = [dict(byte=i, ready_tick=r[0], write_tick=w[0], latency_base_cycles=l, gap_cycles=g)
            for i, (r, w, l, g) in enumerate(zip(ready, writes[1:], latency, gaps))]
    return timing, rows


def write_csv(path, rows):
    with path.open('w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(trace, program, markers, count, out):
    # Discard unrelated boot I/O. The pump's first write follows this marker.
    begin = next(i for i, (_, e) in enumerate(trace)
                 if e[0] == 'cpu' and int(e[4], 16) == markers['SIGNALCONCURRENT.STREAMSTART'])
    timing, refills = serial_timing(trace[begin:], count)
    start, end = timing['start_tick'], timing['end_tick']
    intervals = masked_intervals(trace, start, end)
    reverse = {pc: name for name, pc in markers.items()}
    calls = [(t, reverse[int(e[4], 16)]) for t, e in trace
             if e[0] == 'cpu' and start <= t <= end and int(e[4], 16) in reverse]
    # Join in linear time; an IRQ/NMI can run inside a larger masked activation.
    call_index = 0
    for interval in intervals:
        entered = Counter()
        while call_index < len(calls) and calls[call_index][0] < interval['start_tick']:
            call_index += 1
        while call_index < len(calls) and calls[call_index][0] < interval['end_tick']:
            entered[calls[call_index][1]] += 1
            call_index += 1
        interval['entered_routines'] = dict(entered)
    worst_byte = max(refills, key=lambda r: r['latency_base_cycles'])
    timing['worst_byte'] = worst_byte
    timing['worst_refill_masked_intervals'] = [i for i in intervals
        if i['start_tick'] < worst_byte['write_tick'] and i['end_tick'] > worst_byte['ready_tick']]
    timing['masked'] = dict(
        scope='CPU I=1 intervals during first SEROUT write through final byte completion',
        resolution='Observed between emulator microstates, including RTI-to-immediate-IRQ transitions; 1/8 base-cycle timestamps. Includes NMI/ROM/DMA time, not a hardware worst-case guarantee.',
        intervals=stats([(i['end_tick']-i['start_tick']) for i in intervals]),
        total_us=sum(i['duration_us'] for i in intervals),
        longest=sorted(intervals, key=lambda i: i['duration_us'], reverse=True)[:10])
    timing['routine_entries_during_transfer'] = dict(Counter(name for _, name in calls))
    timing['public_call_elapsed_latency'] = public_call_latencies(trace, markers, start, end)
    posts=[t for t,e in trace if e[0]=='cpu' and int(e[4],16)==markers['signal_post'] and t>=start]
    resumed=[t for t,e in trace if e[0]=='cpu' and int(e[4],16)==markers['SIGNALCONCURRENT.STREAMRESUME'] and t>=start]
    require(len(posts)==len(resumed)==1 and resumed[0]>=posts[0],'Missing unique IRQ completion/resumption')
    timing['completion_post_to_worker_resume_us']=(resumed[0]-posts[0])/BASE_HZ*1e6
    if 'SIGNALCONCURRENT.CLIENTRESUME' in markers:
        clients=[t for t,e in trace if e[0]=='cpu' and int(e[4],16)==markers['SIGNALCONCURRENT.CLIENTRESUME'] and t>=start]
        if clients:
            require(len(clients)==1 and clients[0]>=resumed[0],'Invalid client reply marker')
            timing['completion_post_to_client_reply_us']=(clients[0]-posts[0])/BASE_HZ*1e6
    # Each interval retains attribution in the full CSV; the JSON keeps top ten.
    csv_intervals = [dict(i, entered_routines=json.dumps(i['entered_routines'], sort_keys=True)) for i in intervals]
    write_csv(out/'masked.csv', csv_intervals)
    write_csv(out/'refills.csv', refills)
    timing['artifacts'] = {name: sha256(out/name) for name in ('masked.csv', 'refills.csv')}
    return timing


def run_program(program, bridge_dir, rom, out, workload, count, observed):
    out.mkdir(parents=True, exist_ok=True)
    with emulator(bridge_dir.resolve(), rom.resolve(), out, pin=PIN) as bridge:
        bridge.config('siopatch', 'off')
        bridge.config('burstio', 'false')
        bridge.config('randdelay', 'false')
        machine = verify_machine(bridge, rom, PIN)
        ownership = {}

        def before(b):
            for name, value, size in (('WORKLOAD', WORKLOADS.index(workload), 1), ('BYTECOUNT', count, 2)):
                at = next(d['address'] for d in program['image']['data'] if '_'+name+'_' in d['name'])
                b.memload(at, value.to_bytes(size, 'little'))
            for address, size in ((0x10, 1), (0x42, 1), (0x20c, 2), (0x232, 1)):
                ownership[address] = b.memdump(address, size)
            if observed:
                b.profile_start()

        runtime, _ = execute(bridge, program, before_run=before, timeout=600, frame_limit=30000)
        counters = {name: int.from_bytes(bytes(data(bridge, program['image'], name)), 'little')
                    for name in COUNTERS}
        require(counters['sent'] == count and counters['waits'] == 1, 'Block completion mismatch')
        require(data(bridge, program['image'], 'badResult') == [0]*4, 'Incorrect signal result')
        require(counters['background'] > 0, 'Root made no progress')
        for name in ('yields', 'requests', 'replies', 'sleeps', 'blocked'):
            active = (name == 'yields' and workload in ('yield', 'mixed','allocate','fragment','clear','ports') or
                      name in ('requests', 'replies', 'blocked') and workload in ('signals', 'mixed','allocate','fragment','clear','ports') or
                      name == 'sleeps' and workload in ('sleep', 'mixed','allocate','fragment','clear','ports'))
            require((counters[name] > 0) if active else (counters[name] == 0),
                    f'Missing/unexpected {name} progress before final refill: {counters}')
        require(runtime['created'] == 3 and runtime['vbi_count'] > 0,
                'Missing three admitted workers plus root/VBI')
        if workload in ('allocate','fragment','clear','ports'):
            for name in ('heapBefore','heapAfter','heapAllocations','heapQueries','heapClears','fragmentCount'):
                counters[name]=int.from_bytes(bytes(data(bridge,program['image'],name)),'little')
            require(counters['heapBefore']==counters['heapAfter'],'Allocator workload leaked memory')
            key={'allocate':'heapAllocations','fragment':'heapQueries','clear':'heapClears','ports':'heapClears'}[workload]
            require(counters[key]>0,'No complete allocator iteration during transfer')
        if workload=='ports':
            for name in ('portBursts','portReplies','registryRounds','completionReplies','maxOutstanding'):
                counters[name]=int.from_bytes(bytes(data(bridge,program['image'],name)),'little')
            require(all(counters[n]>0 for n in ('portBursts','portReplies','registryRounds','heapAllocations','heapClears')), 'Missing port workload progress')
            require(counters['completionReplies']==1 and counters['maxOutstanding']==8,'Port completion/depth mismatch')
        for address, previous in ownership.items():
            current = bridge.memdump(address, len(previous))
            # Non-serial IRQEN bits belong to ROM and may change during a VBI.
            require((current[0] & 0x38) == (previous[0] & 0x38) if address == 0x10 else current == previous,
                    f'Serial ownership not restored at ${address:04x}')
    return dict(runtime=runtime, counters=counters, machine=machine,
                serial_ownership='restored', trace_sha256=sha256(out/'emulator.log'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, required=True)
    parser.add_argument('--bridge-dir', type=Path, default=ROOT/'build/altirra-concurrency-bridge')
    parser.add_argument('--replay-bridge-dir', type=Path, default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/signals-concurrency')
    parser.add_argument('--mode', choices=('raw', 'opt'), action='append')
    parser.add_argument('--workload', choices=WORKLOADS, action='append')
    parser.add_argument('--count', type=int, default=4096)
    parser.add_argument('--require-deadline', action='store_true')
    args = parser.parse_args()
    require(512 <= args.count <= 65535, 'Use 512..65535 bytes so kernel interference makes progress')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    observer = json.loads((ROOT/'toolchain/altirra-concurrency-observer.json').read_text())
    require(sha256(args.bridge_dir/'AltirraBridgeServer') == observer['binary_sha256'], 'Incorrect observer')
    require(sha256(ROOT/observer['patch']) == observer['patch_sha256'], 'Observer patch mismatch')
    require(sha256(args.replay_bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Incorrect replay emulator')
    require(sha256(args.rom) == PIN['rom']['sha256'], 'Incorrect ROM')
    previous = {k: os.environ.get(k) for k in ENVIRONMENT}
    report = dict(schema_version=1, status='running', platform=PIN, observer=observer, count=args.count,
                  scope='Four-task diagnostic TX pump under concurrent kernel work; no production driver or RX',
                  bank_zero_reservation_delta=dict(fixed=0, per_task=0, diagnostic=0), cases=[])
    report['allocator_workloads']={'allocate':{'bytes':257},
        'fragment':{'preallocated_blocks':24,'block_request':257,'initial_free_chunks':13,
                    'iteration_requests':[513,65537],'queries':['LARGEST','LARGEST|LINEAR']},
        'clear':{'vector_payload_bytes':131073,'backing_bytes':131088,'flags':['LINEAR','CLEAR']}}
    report['inputs']={p:sha256(ROOT/p) for p in ('tests/programs/signals_concurrent.act',
        'tests/programs/heap_concurrent.inc','tests/programs/ports_concurrent.inc','tools/test_signal_concurrency.py')}
    report['port_workload']=dict(tasks=4,burst_messages=8,maximum_outstanding=8,shared_signal_reply_ports=2,
        public_registry_ports=8,name_bytes=33,shared_prefix_bytes=32,completion_requests=1,
        allocator_requests=[257,4097],clear_flags=['CLEAR'])
    try:
        for mode in args.mode or ('raw', 'opt'):
            program = build(toolchain, ROOT/'tests/programs/signals_concurrent.act', out/mode/'program',
                            tasks=True, optimize=mode == 'opt', irq_probe=8, pump_count=args.count)
            markers = markers_for(program)
            for workload in args.workload or ('mixed',):
                case_out = out/(workload+'-'+mode)
                case_out.mkdir(parents=True, exist_ok=True)
                case = dict(name=workload+'-'+mode, status='running', build=program['build'], markers=markers)
                report['cases'].append(case)
                print('Measuring '+case['name'], flush=True)
                os.environ['EXEC816_LATENCY_TRACE'] = '1'
                os.environ['EXEC816_MASK_TRACE'] = '1'
                os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in sorted(set(markers.values())))
                case['observed'] = run_program(program, args.bridge_dir, args.rom, case_out/'observed', workload, args.count, True)
                trace = read_events(case_out/'observed/emulator.log')
                case['timing'] = analyze(trace, program, markers, args.count, case_out)
                if workload=='ports':
                    require('completion_post_to_client_reply_us' in case['timing'],
                            'Missing port client completion marker')
                for key in ENVIRONMENT:
                    os.environ.pop(key, None)
                print('Replaying '+case['name'], flush=True)
                case['replay'] = run_program(program, args.replay_bridge_dir, args.rom, case_out/'replay', workload, args.count, False)
                for key in ('runtime', 'counters', 'serial_ownership'):
                    require(case['observed'][key] == case['replay'][key], 'Observer/replay mismatch: '+key)
                case['status'] = 'pass'
                t = case['timing']
                print(f"{case['name']}: functional pass; timing {t['verdict']}; "
                      f"{t['deadline_misses']}/{args.count-1} late refills; "
                      f"max refill {t['ready_to_refill']['max_us']:.3f} us; "
                      f"max I=1 {t['masked']['intervals']['max_us']:.3f} us", flush=True)
        report['status'] = 'pass'
        report['timing_verdict'] = 'pass' if all(c['timing']['verdict'] == 'pass' for c in report['cases']) else 'fail'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    if args.require_deadline and report['timing_verdict'] != 'pass':
        raise SystemExit('Serial timing failed; see timing_verdict (functional integrity passed)')


if __name__ == '__main__':
    main()
