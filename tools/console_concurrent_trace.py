"""Passive console/SIO oracles; retain the existing byte and phase limits."""
import json
from bisect import bisect_left
from math import ceil
from sio_adapter_trace import analyze as wire_timing,transmit_bursts
from sio_transaction_trace import read_events,checksum,stats,BASE_HZ
from sio_concurrent_trace import LIMITS,alarm_observations
from test_signal_concurrency import masked_intervals
from mydos_fixtures import Image

def shared_alarm_observations(events, marks):
    """Pair armed SIO callbacks with the physical latch their tick consumed.

    Timer 1 also services pointer-only ticks. Those are not SIO alarm deadlines;
    the mouse oracle checks their sampling gap and unique dispatch separately.
    """
    pending = acknowledged = dispatch = None
    consumed = set()
    serviced = []
    for tick, event in events:
        if event[0] == 'timer' and int(event[2]) == 0:
            pending = tick
        elif event[0] == 'register' and int(event[2]) == 14 and int(event[3]) & 1 == 0:
            if pending is not None:
                acknowledged, pending = pending, None
        elif event[0] == 'cpu':
            pc = int(event[4], 16)
            if pc == marks['timer_tick']:
                if acknowledged is None or acknowledged in consumed:
                    raise ValueError('Shared timer dispatch without a new acknowledged edge')
                consumed.add(acknowledged)
                dispatch = acknowledged
            elif pc == marks['sio_alarm']:
                if dispatch is None:
                    raise ValueError('SIO alarm without a unique shared timer dispatch')
                serviced.append(tick - dispatch)
                dispatch = None
    return serviced

def distribution(values):
    result=stats(values)
    if values:
        ordered=sorted(values)
        for name,p in [('median_us',.5),('p95_us',.95),('p99_us',.99)]:result[name]=ordered[ceil(len(ordered)*p)-1]/BASE_HZ*1e6
    return result

def analyze(path,marks,media,size,speed,file_bytes,key_count=8,keyboard_boundary=None,divisor=None,shared_timer=False,active_forbid_only=False):
    if divisor is None:divisor=40 if speed else 0
    if divisor not in (0,8,40):raise ValueError('Unqualified serial divisor')
    rx_period={0:14,8:31,40:93}[divisor]
    events=read_events(path);result=wire_timing(path,marks,divisor,events);failures=result['violations']
    def check(ok,message):
        if not ok:failures.append(message)
    times=lambda name:[t for t,e in events if e[0]=='cpu' and name in marks and int(e[4],16)==marks[name]]
    starts=times('sio_start');posts=times('signal_post');retires=times('sio_retire');stop=times('sio_shutdown')[0]
    check(len(starts)==len(posts)==len(retires),'lost/duplicate serial completion')
    check(all(a<=b<=c for a,b,c in zip(starts,posts,retires)),'serial completion order')
    disk=Image(media.read_bytes());expected=[];sectors=[]
    for frame in result['tx_frames']:
        okay=len(frame)==5 and frame[:2]==[49,0x52] and frame[-1]==checksum(frame[:-1])
        check(okay,'unexpected serial command/checksum')
        if not okay:continue
        sector=frame[2]+(frame[3]<<8);check(1<=sector<=disk.count,'sector outside media')
        if 1<=sector<=disk.count:
            payload=list(disk.sector(sector));expected.extend([0x41,0x43]+payload+[checksum(payload)]);sectors.append(sector)
    check(len(sectors)==len(starts),'incomplete serial command timeline')
    check(result['rx_bytes']==expected,'wire bytes differ from original media')
    active=[(t,e) for t,e in events if starts[0]<=t<=stop]
    rxstarts=[(t,e) for t,e in active if e[0]=='rxstart'];receives=[(t,e) for t,e in active if e[0]=='receive'];reads=[(t,e) for t,e in active if e[0]=='read'];read_times=[t for t,e in reads]
    check(len(rxstarts)==len(receives)==len(expected),'RX framing count')
    rx_misses=0
    for (arrival,event),(begin,framing) in zip(receives,rxstarts):
        index=bisect_left(read_times,arrival)
        timely=index<len(reads) and reads[index][0]-arrival<int(framing[3])*10
        rx_misses+=not timely;check(timely,'RX physical byte deadline')
        check(int(framing[3])==rx_period,'unexpected RX baud')
        check(int(event[3])&32 and int(event[5])&0xa0==0xa0,'RX disabled/framing/overrun')
    result['rx_byte_deadline_us']=rx_period*10/BASE_HZ*1e6
    bursts=transmit_bursts(active,check);period=20*(divisor+7)
    result['deadline_misses']=dict(rx=rx_misses,tx=sum(not 0<=b-a<period for ready,writes,end in bursts for (a,_),(b,_) in zip(ready,writes[1:])),tx_gaps=sum(b-a!=period for ready,writes,end in bursts for (a,_),(b,_) in zip(ready,ready[1:])))
    for name,values,bound in [('critic_deferral_bound',[b-a for a,b in zip(starts,retires)],LIMITS['critic_max_us']),('post_to_worker',[b-a for a,b in zip(posts,retires)],LIMITS['post_to_worker_max_us'])]:
        result[name]=distribution(values);check(all(0<=v/BASE_HZ*1e6<=bound for v in values),name+' deadline')
    # BLOCKWIRE serializes one request. A following sector start, completion
    # of the warm-open before the first allocator iteration, DOS.Read entry
    # after Open, and Read return are all after collection of preceding I/O.
    # This bounds collection even for the first passive probe, which did not
    # mark the BLOCKWIRE return instruction separately.
    milestones=times('allocation_cycle')[:1]+times('read_begin')+times('read_end')
    if 'sector_end'in marks:milestones+=times('sector_end')
    collection_bounds=[]
    for index,post in enumerate(posts):
        following=starts[index+1:index+2]+[t for t in milestones if t>=post]
        check(bool(following),'Unbounded serial reply collection')
        if following:collection_bounds.append(min(following)-post)
    check(all(0<=v/BASE_HZ*1e6<=LIMITS['post_to_collect_max_us'] for v in collection_bounds),'post-to-sector-collection deadline')
    result['post_to_sector_collection_upper_bound']=distribution(collection_bounds)
    if 'sector_end' in marks:
        collected=times('sector_end');check(len(collected)==len(posts),'Missing collected sector replies')
        collection=[b-a for a,b in zip(posts,collected)]
        check(all(0<=v/BASE_HZ*1e6<=LIMITS['post_to_collect_max_us'] for v in collection),'measured post-to-sector-collection deadline')
        result['post_to_sector_collection']=distribution(collection)
    result['alarms']={}
    for channel,name in ((0,'sio_alarm'),(1,'sio_watchdog')):
        if shared_timer and channel==0:
            serviced=shared_alarm_observations(active,marks)
            cancelled,unserviced=[],[]
            service='Acknowledged physical timer-1 edge to armed SIO callback; pointer-only ticks checked separately'
        else:
            service=name
            serviced,cancelled,unserviced=alarm_observations(active,times(service),posts,stop,channel)
        check(bool(serviced),'no '+name+' observations')
        check(all(0<=v/BASE_HZ*1e6<=LIMITS['alarm_lateness_us'] for v in serviced+cancelled+unserviced),'alarm deadline '+name)
        result['alarms'][name]=dict(service=distribution(serviced),cancelled_or_terminal=distribution(cancelled+unserviced),boundary=service)
    nesting={};forbids=[]
    # Public resident shutdown ends exclusion by self-removal, with no Permit.
    # These markers identify the exact NULL RemTask calls; the native fixture
    # separately requires successful retirement and empty ownership records.
    retire_sites={pc for name,pc in marks.items() if name.startswith('forbid_retire_')}
    for t,e in events:
        if e[0]!='cpu':continue
        pc=int(e[4],16);dp=e[9]
        if pc==marks['tasks_forbid']:nesting.setdefault(dp,[]).append(t)
        elif pc==marks['tasks_permit'] and nesting.get(dp):
            start=nesting[dp].pop()
            if not active_forbid_only or start>=starts[0]:forbids.append(t-start)
        elif pc in retire_sites:
            check(len(nesting.get(dp,[]))==1,'Unexpected resident retirement nesting')
            forbids.extend(t-start for start in nesting.pop(dp,[]) if not active_forbid_only or start>=starts[0])
    check(not any(nesting.values()),'unbalanced Forbid')
    check(bool(forbids) and all(v/BASE_HZ*1e6<=LIMITS['forbid_max_us'] for v in forbids),'Forbid deadline')
    result['forbid']=distribution(forbids)
    result['forbid_scope']='After first serial command; cold startup excluded' if active_forbid_only else 'Complete observed execution'
    # Clip the same I-transition oracle in one pass; a large file has hundreds
    # of transactions, so rescanning the entire trace for each is unnecessary.
    masks=masked_intervals(events,starts[0],stop);maximum=0;longest_active=None
    for item in masks:
        index=bisect_left(retires,item['start_tick'])
        while index<len(starts) and starts[index]<item['end_tick']:
            duration=min(item['end_tick'],retires[index])-max(item['start_tick'],starts[index])
            if duration>maximum:maximum=duration;longest_active=dict(item,transaction=index,overlap_us=duration/BASE_HZ*1e6)
            index+=1
    result['active_masked_max_us']=maximum/BASE_HZ*1e6
    result['longest_transaction_mask']=longest_active
    result['longest_resident_mask']=max(masks,key=lambda v:v['duration_us'])
    result['resident_masked_max_us']=result.pop('masked_max_us')
    if file_bytes is None and key_count is None:
        # Share every byte, phase, mask, alarm and collection gate with the
        # foreground/window workloads, which have their own input timelines.
        result['wire_transactions']=len(starts);result['verified_wire_bytes']=len(expected)
        result['violations']=sorted(set(failures));result['verdict']='fail' if failures else 'pass'
        result.pop('rx_bytes');result.pop('tx_frames')
        (path.parent/'timing.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    begin,end=times('read_begin'),times('read_end');check(len(begin)==len(end)==1,'Expected one large DOS.Read')
    if begin and end:
        first,last=begin[0],end[0];elapsed=(last-first)/BASE_HZ
        check(elapsed>0,'invalid file Read timeline')
        result['file_read']=dict(bytes=file_bytes,seconds=elapsed,bytes_per_second=file_bytes/elapsed,mechanical_timing=True,scope='JSL DOS.Read entry to return; excludes Open, payload verification and cleanup')
        gaps=[b-a for a,b in zip(posts,starts[1:]) if first<=a<=b<=last]
        check(bool(gaps) and all(v/BASE_HZ*1e6<=LIMITS['next_start_max_us'] for v in gaps),'next continuously requested sector deadline')
        result['post_to_next_start_during_read']=distribution(gaps)
        alloc=[t for t in times('allocation_cycle') if first<=t<=last]
        drawing=[t for t in times('display_quantum') if first<=t<=last]
        feed=[t for t in times('terminal_feed') if first<=t<=last]
        check(alloc and drawing and feed,'missing kernel/output progress during file Read')
        result['read_progress']=dict(allocator_entries=len(alloc),draw_quanta=len(drawing),terminal_feeds=len(feed))
    capture,reply,collect,visible=[times(n) for n in ('input_capture','read_reply_begin','read_collected','echo_visible')]
    check(len(capture)==len(reply)==len(collect)==len(visible)==key_count,'lost/duplicate key, read reply or visible echo')
    check(all(a<=b<=c<=d for a,b,c,d in zip(capture,reply,collect,visible)),'keyboard/echo order')
    result['keyboard']=dict(
        capture_to_reply_lower_bound=distribution([b-a for a,b in zip(capture,reply)]),
        capture_to_collected_reply_upper_bound=distribution([b-a for a,b in zip(capture,collect)]),
        capture_to_observed_visible_echo_upper_bound=distribution([b-a for a,b in zip(capture,visible)]),
        samples=[dict(capture=t,reply_call=a,collected=b,visible=c) for t,a,b,c in zip(capture,reply,collect,visible)],
        boundary=keyboard_boundary or 'Native raw-event capture entry; worker finish-read call (before publication); client after specific WaitIO collection; task after first observing its unique lowercase glyph in physical screen RAM. Reply and visibility upper bounds include scheduling/polling, not a hard real-time guarantee.')
    result['wire_transactions']=len(starts);result['verified_wire_bytes']=len(expected)
    result['violations']=sorted(set(failures));result['verdict']='fail' if failures else 'pass'
    # Exact media bytes are checked above; avoid duplicating the long payload in
    # a qualification record. The preserved trace contains the observations.
    result.pop('rx_bytes');result.pop('tx_frames')
    (path.parent/'timing.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
