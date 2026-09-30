#!/usr/bin/env python3
"""Passive instruction-boundary trace of HELLO's filesystem/SIO pipeline."""
import argparse
import json
import os
from pathlib import Path

from native_program import ROOT, read_build, require, sha256
from measure_command_loading import run
from sio_transaction_trace import read_events, BASE_HZ


def markers(program):
    names = {
        'fs_worker': 'FSWORKER_WORKER', 'fs_begin': 'FSIO_BEGIN',
        'fs_complete': 'FSIO_COMPLETE', 'fs_checkpoint': 'FSABORT_CHECKPOINT',
        'fs_pump': 'FSOPERATION_PUMP', 'fs_file_step': 'FSHANDLER_FILESTEP',
        'sdfs_consume': 'SDFSFILE_CONSUME', 'sdfs_drive': 'SDFSFILE_DRIVE',
        'sdfs_continue': 'SDFSFILE_CONTINUEOPERATION', 'fs_reply': 'FSPACKET_REPLY',
        'blockwire': 'BLOCKWIRE_TRANSFER', 'block_begin': 'BLOCKIO_BEGINFETCH',
        'block_finish': 'BLOCKIO_FINISHFETCH', 'block_prepare': 'BLOCKIO_PREPARE',
        'driver_worker': 'SIODRIVER_WORKER',
        'driver_request': 'SIODRIVER_RUNREQUEST', 'driver_validate': 'SIODRIVER_SIOVALIDATE',
        'driver_prepare': 'SIODRIVER_PREPARE', 'driver_deadline': 'SIODRIVER_DEADLINETICKS',
        'io_wait': 'IOCORE_WAITIO', 'driver_finish': 'SIODRIVER_FINISH',
        'driver_claim': 'SIODRIVER_CLAIM', 'driver_begin': 'SIODRIVER_BEGINIO',
        'driver_activate': 'SIODRIVER_ACTIVATE', 'driver_stopping': 'SIODRIVER_STOPPING',
        'io_submit': 'IOCORE_SUBMIT',
        'io_complete_policy': 'TASKPOLICY_IOCOMPLETE', 'dos_call': 'DOSCLIENT_CALL',
    }
    routines = {}
    for name, prefix in names.items():
        matches = [r for r in program['image']['routines'] if r['name'].startswith('M_'+prefix+'_')]
        require(len(matches) == 1, 'Missing/ambiguous trace routine: '+prefix)
        routines[name] = matches[0]
    marks = {name:r['address'] for name,r in routines.items()}
    marks.update({name:program['labels'][name] for name in
                  ('sio_start', 'sio_terminal', 'signal_post', 'sio_retire', 'sio_recovered',
                   'io_send_io', 'io_wait_io', 'io_check_io', 'io_collect',
                   'tasks_wait')})
    marks.update({name:program['labels'][name] for name in ('tasks_forbid','tasks_permit')})
    marks.update({name:program['labels'][name] for name in ('fast_entry','fast_complete','fast_general','dispatch_call')})
    from dos_concurrent_trace import packet_marks
    marks.update(packet_marks(program))
    # Observe call-site returns without adding guest instructions. The opcode
    # bytes and containing routine are checked against the retained image.
    for caller, callees in {
        'fs_worker': ('blockwire','fs_begin','fs_complete','fs_pump','fs_checkpoint'),
        'driver_worker': ('driver_request','driver_claim','driver_stopping','tasks_wait'),
        'driver_request': ('driver_validate','driver_prepare','sio_start','sio_retire','sio_recovered','driver_activate','driver_finish','tasks_wait'),
        'sdfs_continue': ('sdfs_consume','sdfs_drive'),
        'driver_prepare': ('driver_deadline',),
        'blockwire': ('io_collect','io_send_io','tasks_wait','fs_pump'),
        'io_wait': ('io_collect','tasks_wait'),
        'fs_pump': ('tasks_forbid','tasks_permit'),
        'driver_claim': ('tasks_forbid','tasks_permit'),
        'driver_activate': ('tasks_forbid','tasks_permit'),
        'driver_finish': ('tasks_forbid','tasks_permit'),
        'driver_stopping': ('tasks_forbid','tasks_permit'),
        'io_submit': ('tasks_forbid','tasks_permit'),
    }.items():
        routine = routines[caller]; start = routine['address']
        raw = bytearray(routine['size'])
        for segment in program['image']['segments']:
            lo = max(start,segment['address']); hi = min(start+len(raw),segment['address']+len(segment['bytes']))
            if lo < hi:
                raw[lo-start:hi-start] = bytes(segment['bytes'][lo-segment['address']:hi-segment['address']])
        for callee in callees:
            needle = b'\x22'+marks[callee].to_bytes(3,'little')
            hits = [i for i in range(len(raw)-3) if raw[i:i+4] == needle]
            require(hits, 'Missing trace call: '+caller+' -> '+callee)
            for index, offset in enumerate(hits):
                suffix = str(index) if len(hits)>1 else ''
                marks[caller+'_before_'+callee+suffix] = start+offset
                marks[caller+'_after_'+callee+suffix] = start+offset+4
    return marks


def stats(values):
    return dict(count=len(values),mean_ms=sum(values)/len(values) if values else None,
                min_ms=min(values) if values else None,max_ms=max(values) if values else None,
                sum_ms=sum(values))


def call_intervals(cpus, marks):
    """Pair exact call sites in the caller's DP, including suspended calls.

    Entry/return times are elapsed times, not exclusive CPU costs. Pairing by
    DP prevents another task's use of the same library from ending a call.
    """
    entries = {pc:name for name,pc in marks.items() if '_before_' in name}
    returns = {marks[name.replace('_before_', '_after_')]:name for name in entries.values()}
    pending = {}; intervals = []
    for tick, event in cpus:
        pc = int(event[4],16); dp = event[9]
        if pc in returns:
            name = returns[pc]; key = (dp,name)
            if key in pending:
                begin = pending.pop(key)
                intervals.append(dict(site=name,dp=int(dp,16),begin=begin,end=tick))
        if pc in entries:
            name = entries[pc]; key = (dp,name)
            require(key not in pending, 'Overlapping trace calls: '+name)
            pending[key] = tick
    # Profiling starts/stops at the command boundary, potentially while other
    # workers are suspended in Wait. Those unmatched edge calls are excluded.
    return intervals


def trace(bundle, output, prime_worker='stopped'):
    program = read_build(bundle)
    marks = markers(program)
    output.mkdir(parents=True,exist_ok=True)
    (output/'markers.json').write_text(json.dumps(marks,indent=2)+'\n')
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in marks.values())
    os.environ.pop('EXEC816_MASK_TRACE',None)
    run(bundle,output,prime_worker=prime_worker,cpu_trace=True)
    return analyze(output)


def exclusion_intervals(cpus, marks):
    """Measure completed Forbid return to Permit entry in the same caller DP.

    These five nonblocking regions do not suspend. Interrupt time is included;
    the final Permit's possible reschedule is excluded.
    """
    sites=('driver_claim','driver_activate','driver_finish','driver_stopping','io_submit')
    starts={marks[s+'_after_tasks_forbid']:s for s in sites}
    ends={marks[s+'_before_tasks_permit']:s for s in sites}
    pending={};result={s:[] for s in sites}
    for tick,event in cpus:
        pc=int(event[4],16);dp=event[9]
        if pc in starts:
            key=(dp,starts[pc]);require(key not in pending,'Overlapping exclusion region')
            pending[key]=tick
        if pc in ends:
            site=ends[pc];key=(dp,site)
            if key in pending:result[site].append((tick-pending.pop(key))/BASE_HZ*1000)
    return {site:stats(values) for site,values in result.items()}


def analyze(output):
    marks = json.loads((output/'markers.json').read_text())
    events = read_events(output/'emulator.log')
    cpus = [(t,e) for t,e in events if e[0]=='cpu']
    calls = call_intervals(cpus,marks)
    packets = []; packet = None
    for tick, event in events:
        if event[0]=='command' and event[2]=='1':
            packet = dict(start=tick,tx=[],rx=[]); packets.append(packet)
        if packet is None: continue
        if event[0]=='ready': packet['tx'].append(int(event[2]))
        if event[0]=='rxstart': packet['rx'].append((tick,int(event[2]),int(event[3])))
    reads = [p for p in packets if len(p['tx'])==5 and p['tx'][:2]==[49,82]]
    sector = lambda p: p['tx'][2]+256*p['tx'][3]
    first = next(i for i,p in enumerate(reads) if sector(p)==70)
    reads = reads[first:first+19]
    require([sector(p) for p in reads]==list(range(70,89)), 'Changed HELLO data-sector layout')
    require(all(len(p['rx'])==131 for p in reads), 'Incomplete sector trace')
    end = lambda p: p['rx'][-1][0]+10*p['rx'][-1][2]
    phases = (
        ('completion_to_worker','sio_retire'),
        ('retire_reply_collect','fs_worker_after_blockwire'),
        ('finish_cache_and_first_checkpoint','sdfs_consume'),
        ('consume_inclusive','sdfs_continue_after_sdfs_consume'),
        ('next_step_or_dos_packet_roundtrip','sdfs_drive'),
        ('map_lookup_and_block_prepare','blockwire'),
        ('blockwire_before_send','io_send_io'),
        ('send_to_driver_request','driver_request'),
    )
    gaps = []; pumps = []
    for previous,following in zip(reads,reads[1:]):
        begin = end(previous); finish = following['start']
        points = [(t,e) for t,e in cpus if begin<=t<finish]
        row = dict(after_sector=sector(previous),next_sector=sector(following),
                   read_boundary=any(int(e[4],16)==marks['dos_submit'] for t,e in points),
                   begin=begin,end=finish,phases_ms={})
        cursor = begin
        for name,marker in phases:
            hits = [t for t,e in points if t>=cursor and int(e[4],16)==marks[marker]]
            require(hits, f'Missing {marker} after sector {sector(previous)}')
            tick = hits[0]; row['phases_ms'][name]=(tick-cursor)/BASE_HZ*1000; cursor=tick
        row['phases_ms']['driver_validate_prepare_start']=(finish-cursor)/BASE_HZ*1000
        row['milliseconds']=(finish-begin)/BASE_HZ*1000
        row['cpu_markers']=[dict(offset_ms=(t-begin)/BASE_HZ*1000,
                                name=next(k for k,v in marks.items() if v==int(e[4],16)),
                                dp=int(e[9],16)) for t,e in points]
        gaps.append(row)
        for call in calls:
            if not call['site'].endswith('_before_fs_pump') or not begin<=call['begin']<call['end']<=finish:
                continue
            guarded=any(call['begin']<=t<call['end'] and int(e[9],16)==call['dp']
                        and int(e[4],16)==marks['tasks_forbid'] for t,e in points)
            require(not guarded, 'Expected no cancellation in the HELLO measurement')
            pumps.append(dict(after_sector=sector(previous),site=call['site'],
                              milliseconds=(call['end']-call['begin'])/BASE_HZ*1000))
    # Each call family can overlap another (e.g. WaitIO includes Collect), or
    # span task suspension. These diagnostics must not be summed with phases.
    by_site = {}
    for call in calls:
        overlaps = [max(0,min(call['end'],r['end'])-max(call['begin'],r['begin'])) for r in gaps]
        if not any(overlaps): continue
        row=by_site.setdefault(call['site'],dict(durations=[],gap_overlaps=[]))
        row['durations'].append((call['end']-call['begin'])/BASE_HZ*1000)
        row['gap_overlaps'].append(sum(overlaps)/BASE_HZ*1000)
    call_stats = {name:dict(elapsed=stats(row['durations']),in_gaps=stats(row['gap_overlaps']))
                  for name,row in sorted(by_site.items())}
    result = dict(status='pass',clock_hz=BASE_HZ,markers=marks,
                  gateway_paths={name:sum(int(e[4],16)==marks[name] for _,e in cpus)
                                 for name in ('fast_entry','fast_complete','fast_general','dispatch_call')},
                  task_exclusion=exclusion_intervals(cpus,marks),
                  trace_sha256=sha256(output/'emulator.log'),
                  results_sha256=sha256(output/'results.json'),
                  inputs={str(Path(__file__).relative_to(ROOT)):sha256(Path(__file__))},
                  gaps=stats([r['milliseconds'] for r in gaps]),
                  ordinary_gaps=stats([r['milliseconds'] for r in gaps if not r['read_boundary']]),
                  read_boundary_gaps=stats([r['milliseconds'] for r in gaps if r['read_boundary']]),
                  phases={name:stats([r['phases_ms'][name] for r in gaps]) for name in gaps[0]['phases_ms']},
                  empty_pumps=stats([r['milliseconds'] for r in pumps]),
                  calls_overlapping_gaps=call_stats,
                  samples=gaps,pump_samples=pumps,
                  interpretation='Wall-clock intervals include preemption and other system workers; consume is not exclusive copy CPU time. Call and Pump totals overlap phase totals; nested or suspended call durations are not additive. Read boundaries are observed DOS submissions, not inferred from sector count.')
    (output/'path-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('gaps','ordinary_gaps','read_boundary_gaps','phases','empty_pumps','calls_overlapping_gaps')},indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/development/sio-collect/measurement/bundle')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--analyze-only',action='store_true')
    parser.add_argument('--prime-worker',choices=('active','stopped'),default='stopped')
    args = parser.parse_args()
    if args.analyze_only: analyze(args.output.resolve())
    else: trace(args.bundle.resolve(),args.output.resolve(),args.prime_worker)
