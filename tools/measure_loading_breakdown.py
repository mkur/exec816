#!/usr/bin/env python3
"""Partition unchanged HELLO loading into wire, device waits and loader calls.

Passive PCs are decoded from the retained diagnostic image. All durations are
elapsed guest time, including interrupts and other Tasks, not exclusive CPU time.
"""
import argparse
import json
import os
from pathlib import Path

from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import BASE_HZ, checksum, read_events
from trace_command_io import call_intervals

ENV = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')


def markers_for(program):
    image = program['image']
    require(image['version'] in (3, 4), 'Unsupported instruction image version')
    source = ROOT/'build/actionc/tools/disassemble65816.py'
    decoder = {'__name__': 'loading_disassembler'}
    # Do not create an untracked __pycache__ in the clean compiler checkout.
    exec(compile(source.read_text(), str(source), 'exec'), decoder)
    names = {r['address']:r['name'][2:].rsplit('_', 1)[0].lower() for r in image['routines']}
    marks, listings = {}, []
    for routine in image['routines']:
        caller = names[routine['address']]
        if not caller.startswith(('o65', 'programplace_', 'programproviders_', 'program_load', 'programfile_load')):
            continue
        segments = []
        for s in image['segments']:
            lo = max(s['address'], routine['address'])
            hi = min(s['address']+len(s['bytes']), routine['address']+routine['size'])
            if lo < hi:
                segments.append(dict(address=lo, bytes=s['bytes'][lo-s['address']:hi-s['address']], executable=True))
        # v4 only adds arithmetic-fault metadata; scalar encodings match v3.
        listing = decoder['disassemble']({**image, 'version':3, 'segments':segments})
        listings.append(routine['name']+'\n'+listing)
        counts = {}
        for line in listing.splitlines():
            pc, rest = line.split('  ', 1)
            instruction = rest[12:]
            if not instruction.startswith('JSL $'):
                continue
            callee = names.get(int(instruction[5:], 16), '')
            if caller == 'programfile_load':
                selected = callee in ('loadprobe_mark', 'dos_read', 'program_load')
            else:
                selected = callee.startswith(('o65', 'programplace_', 'programproviders_', 'dosclient_seterror'))
            if selected:
                index = counts.get(callee, 0)
                counts[callee] = index+1
                site = caller+'_before_'+callee+str(index)
                marks[site] = int(pc, 16)
                marks[site.replace('_before_', '_after_')] = int(pc, 16)+4
    require(sum(k.startswith('programfile_load_before_loadprobe_mark') for k in marks) == 8,
            'Changed diagnostic phase markers')
    require('programfile_load_before_dos_read0' in marks and 'programfile_load_before_program_load0' in marks,
            'Missing Read or Load call')
    return marks, '\n'.join(listings), sha256(source)


def ms(ticks):
    return ticks/BASE_HZ*1000


def packets(events):
    result, packet = [], None
    for tick, event in events:
        if event[0] == 'command' and event[2] == '1':
            packet = dict(begin=tick, tx=[], rx=[], releases=[], idle=[])
            result.append(packet)
        if packet is None:
            continue
        if event[0] == 'command' and event[2] == '0':
            packet['releases'].append(tick)
        elif event[0] in ('ready', 'rxstart'):
            packet['tx' if event[0] == 'ready' else 'rx'].append((tick, int(event[2]), int(event[3])))
        elif event[0] == 'idle':
            packet['idle'].append(tick)
    return result


def partition_packet(packet):
    tx, rx = packet['tx'], packet['rx']
    require(len(tx) == 5 and [p[1] for p in tx[:2]] == [49, 82], 'Not a complete D1 read command')
    require(checksum([p[1] for p in tx[:4]]) == tx[4][1], 'Bad command checksum')
    require(len(rx) == 131 and [p[1] for p in rx[:2]] == [65, 67], 'Incomplete or unsuccessful sector response')
    require(checksum([p[1] for p in rx[2:-1]]) == rx[-1][1], 'Bad data checksum')
    require(len(packet['releases']) == 1 and len(packet['idle']) == 1, 'Missing or repeated command edge/TX end')
    end = lambda byte:byte[0]+10*byte[2]
    require(packet['idle'][0] == end(tx[-1]), 'TX end disagrees with baud')
    require({p[2] for p in tx} == {30} and {p[2] for p in rx} == {31}, 'Changed GENERIC57600 baud')
    tx_gaps = [b[0]-end(a) for a,b in zip(tx, tx[1:])]
    data_gaps = [b[0]-end(a) for a,b in zip(rx[2:], rx[3:])]
    require(all(g >= 0 for g in tx_gaps+data_gaps), 'Overlapping serial bytes')
    release = packet['releases'][0]
    parts = dict(
        command_setup=tx[0][0]-packet['begin'],
        command_wire=sum(10*p[2] for p in tx),
        command_byte_gaps=sum(tx_gaps),
        command_hold=release-end(tx[-1]),
        ack_turnaround=rx[0][0]-release,
        ack_wire=10*rx[0][2],
        device_wait=rx[1][0]-end(rx[0]),
        complete_wire=10*rx[1][2],
        complete_to_data=rx[2][0]-end(rx[1]),
        data_checksum_wire=sum(10*p[2] for p in rx[2:]),
        data_byte_gaps=sum(data_gaps))
    require(all(v >= 0 for v in parts.values()), 'Reversed packet boundaries')
    require(sum(parts.values()) == end(rx[-1])-packet['begin'], 'Packet partition does not reconcile')
    return dict(sector=tx[2][1]+256*tx[3][1], begin=packet['begin'], end=end(rx[-1]),
                milliseconds=ms(end(rx[-1])-packet['begin']), parts_ms={k:ms(v) for k,v in parts.items()})


def payload_partition(events, begin, end):
    selected = [p for p in packets(events) if begin <= p['begin'] < end]
    rows = [partition_packet(p) for p in selected]
    require([r['sector'] for r in rows] == [69, *range(70, 89)], 'Changed HELLO map/data sector sequence')
    require(rows[-1]['end'] <= end, 'Payload ends before checksum')
    gaps = [b['begin']-a['end'] for a,b in zip(rows, rows[1:])]
    require(all(g >= 0 for g in gaps), 'Overlapping transactions')
    parts = {k:sum(r['parts_ms'][k] for r in rows) for k in rows[0]['parts_ms']}
    parts.update(before_first_command=ms(rows[0]['begin']-begin), between_commands=ms(sum(gaps)),
                 after_last_checksum=ms(end-rows[-1]['end']))
    total = ms(end-begin)
    require(abs(sum(parts.values())-total) < 1e-8, 'Payload partition does not reconcile')
    return dict(begin=begin, end=end, milliseconds=total, parts_ms=parts, transactions=rows,
                gaps_ms=[ms(g) for g in gaps], transfers=len(rows), wire_bytes=len(rows)*136,
                useful_file_bytes=2359)


def one_call(calls, site):
    rows = [c for c in calls if c['site'] == site]
    require(len(rows) == 1, 'Expected exactly one completed call: '+site)
    return rows[0]


def direct_partition(calls, parent, caller):
    """Partition one caller into direct callees plus its remaining instructions.

    Do not mix nested call families into the additive parent partition.
    """
    selected = sorted((c for c in calls if c['site'].startswith(caller+'_before_')
                       and parent['begin'] <= c['begin'] < c['end'] <= parent['end']), key=lambda c:c['begin'])
    previous = parent['begin']
    parts, counts = {}, {}
    for call in selected:
        require(call['begin'] >= previous, 'Overlapping direct calls')
        parts[call['site']] = parts.get(call['site'], 0)+ms(call['end']-call['begin'])
        counts[call['site']] = counts.get(call['site'], 0)+1
        previous = call['end']
    total = ms(parent['end']-parent['begin'])
    parts['caller_instructions'] = total-sum(parts.values())
    require(parts['caller_instructions'] >= -1e-8, 'Negative caller remainder')
    return dict(begin=parent['begin'], end=parent['end'], milliseconds=total, parts_ms=parts, counts=counts)


def analyze(output, marks):
    events = read_events(output/'emulator.log')
    calls = call_intervals([(t,e) for t,e in events if e[0] == 'cpu'], marks)
    phases = [one_call(calls, 'programfile_load_before_loadprobe_mark'+str(i)) for i in range(8)]
    require(all(a['end'] < b['begin'] for a,b in zip(phases, phases[1:])), 'Unordered load phases')
    read = one_call(calls, 'programfile_load_before_dos_read0')
    load = one_call(calls, 'programfile_load_before_program_load0')
    require(phases[3]['end'] < read['begin'] < read['end'] < phases[4]['begin'], 'Read outside payload phase')
    require(phases[5]['end'] < load['begin'] < load['end'] < phases[6]['begin'], 'Load outside relocation phase')
    validation = one_call(calls, 'program_load_before_o65_validate0')
    descriptor = one_call(calls, 'o65_validate_before_o65_descriptor0')
    providers = one_call(calls, 'program_load_before_programproviders_resolve0')
    expected = ('o65_validate0', 'programproviders_resolve0', 'o65memory_allocate0', 'programplace_allocate0',
                'programplace_patches0', 'programplace_copy0', 'programplace_copy1', 'programplace_patches1',
                'o65_release2', 'dosclient_seterror2')
    actual = [c['site'].removeprefix('program_load_before_') for c in calls if c['site'].startswith('program_load_before_')]
    require(actual == list(expected), 'Changed or incomplete HELLO loader success path')
    # U32 calls are nonrecursive and can be summed, but they are already inside
    # validation and patching above. Never add this diagnostic to those totals.
    scalars = [c for c in calls if '_before_o65read_u32' in c['site']
               and load['begin'] <= c['begin'] < c['end'] <= load['end']]
    result = dict(status='pass', clock_hz=BASE_HZ,
        payload=payload_partition(events, phases[3]['begin'], phases[4]['begin']),
        dos_read=dict(milliseconds=ms(read['end']-read['begin'])),
        load_phase=dict(milliseconds=ms(phases[6]['begin']-phases[5]['begin'])),
        loader=direct_partition(calls, load, 'program_load'),
        validation=direct_partition(calls, validation, 'o65_validate'),
        descriptor=direct_partition(calls, descriptor, 'o65_descriptor'),
        providers=direct_partition(calls, providers, 'programproviders_resolve'),
        u32_calls=dict(count=len(scalars), inclusive_ms=sum(ms(c['end']-c['begin']) for c in scalars)),
        calls=calls, trace_sha256=sha256(output/'emulator.log'), results_sha256=sha256(output/'results.json'),
        inputs={p:sha256(ROOT/p) for p in ('tools/measure_loading_breakdown.py', 'tools/measure_command_loading.py',
                                         'tools/trace_command_io.py', 'tools/sio_transaction_trace.py')},
        interpretation='Elapsed guest time includes IRQ/NMI and other Tasks. Device wait is ACK end to COMPLETE start. '
                       'Wire intervals can overlap CPU service. Loader, validation, descriptor and U32 summaries are nested; '
                       'only parts within one partition are additive. No counterfactual speedup is inferred.')
    (output/'breakdown.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def run(bundle, output, prime_worker, analyze_only):
    from measure_command_loading import run as replay
    output.mkdir(parents=True, exist_ok=True)
    program = read_build(bundle)
    marks, listing, decoder_hash = markers_for(program)
    if analyze_only:
        require(json.loads((output/'markers.json').read_text()) == marks, 'Saved markers do not match image')
    else:
        (output/'markers.json').write_text(json.dumps(marks, indent=2)+'\n')
        (output/'loader.asm').write_text(listing)
    previous = {k:os.environ.get(k) for k in ENV}
    try:
        os.environ['EXEC816_LATENCY_TRACE'] = '1'
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in sorted(set(marks.values())))
        os.environ.pop('EXEC816_MASK_TRACE', None)
        measured = json.loads((output/'results.json').read_text()) if analyze_only else replay(
            bundle, output, prime_worker=prime_worker, cpu_trace=True)
        require(measured['status'] == 'pass' and measured['xex_sha256'] == program['build']['xex_sha256'], 'Changed HELLO image')
        require(measured['prime_worker']['mode'] == prime_worker, 'Wrong prime-worker mode')
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    result = analyze(output, marks)
    result.update(prime_worker=prime_worker, xex_sha256=measured['xex_sha256'], decoder_sha256=decoder_hash)
    (output/'breakdown.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('loader', 'validation', 'descriptor', 'u32_calls')}, indent=2))
    print(json.dumps(dict(payload_ms=result['payload']['milliseconds'], parts_ms=result['payload']['parts_ms']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prime-worker', choices=('stopped', 'active'), default='stopped')
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    run(args.bundle.resolve(), args.output.resolve(), args.prime_worker, args.analyze_only)
