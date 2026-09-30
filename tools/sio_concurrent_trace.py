"""Independent FIFO, byte, phase and scheduling oracles for queued SIO."""
import hashlib
from sio_adapter_trace import analyze as adapter_timing
from sio_transaction_trace import read_events, checksum, stats, BASE_HZ
from test_signal_concurrency import masked_intervals
from os_boundary import require

LIMITS = dict(forbid_max_us=50000, critic_max_us=2120000,
              post_to_worker_max_us=100000, post_to_collect_max_us=2500000,
              next_start_max_us=200000, alarm_lateness_us=100,
              write_delay_us=[1000,1800])


def negative_controls(path,labels,order,collected,output):
    """Retain real passing observations, then deliberately break one deadline.

    These are oracle controls, not claims that the guest executed the changed
    timing. Slice 7 separately executes a real IRQ-stall/overrun control.
    """
    events=read_events(path)
    start=next(t for t,e in events if e[0]=='cpu' and int(e[4],16)==labels['sio_start'])
    controls=[]
    for kind in ('rx','tx','phase'):
        rows=[(t,list(e)) for t,e in events]
        if kind=='rx':
            arrival=next(t for t,e in rows if t>=start and e[0]=='receive')
            index=next(i for i,(t,e) in enumerate(rows) if t>=arrival and e[0]=='read')
            tick=arrival+160
        elif kind=='tx':
            index=[i for i,(t,e) in enumerate(rows) if t>=start and e[0]=='write'][4]
            tick=rows[index][0]+400
        else:
            index=next(i for i,(t,e) in enumerate(rows) if t>=start and e[0]=='command' and e[2]=='1')
            tick=rows[index][0]+1200
        fields=rows[index][1];fields[1]=str(int(tick));rows[index]=(tick,fields)
        rows.sort(key=lambda v:v[0])
        control=output/(kind+'-deadline.log')
        control.write_text(''.join('[SIOTXN] '+' '.join(e)+'\n' for t,e in rows))
        observed=analyze(control,labels,order,collected,0)
        require(observed['verdict']=='fail','Missed deadline accepted: '+kind)
        controls.append(dict(name=kind,status='rejected',violations=observed['violations'],
                             observations_sha256=observed['observations_sha256']))
    return controls


def alarm_observations(events, services, posts, stop, channel):
    """Separate serviced edges from edges explicitly cancelled by IRQEN.

    ROM serial acknowledgment briefly writes all other enable bits as ones.
    A timer can assert there even though the restored enable shadow disables it.
    An acknowledge-clear immediately followed by re-enable is still a live
    alarm: its ISR deadline must not disappear merely because it was acked.
    """
    from bisect import bisect_left
    registers=[(t,int(e[3])) for t,e in events if e[0]=='register' and int(e[2])==14]
    times=[t for t,_ in registers];bit=1<<channel
    ticks=[t for t,e in events if e[0]=='timer' and int(e[2])==channel]
    delays=[];cancelled=[];unserviced=[]
    for t in ticks:
        i=bisect_left(services,t);service=services[i] if i<len(services) else None
        i=bisect_left(posts,t);terminal=posts[i] if i<len(posts) else stop
        limit=min(terminal,service) if service is not None else terminal
        cancellation=None
        for j in range(bisect_left(times,t),len(registers)):
            q,value=registers[j]
            if q>limit:break
            if value&bit:continue
            if j+1<len(registers) and registers[j+1][1]&bit:continue
            cancellation=q;break
        if cancellation is not None:cancelled.append(cancellation-t)
        elif service is not None and service<=terminal:delays.append(service-t)
        else:unserviced.append(terminal-t)
    return delays,cancelled,unserviced


def analyze(path, labels, order, collected, speed,sector_size=128):
    result=adapter_timing(path,labels,40 if speed else 0)
    all_events=read_events(path)
    def marks(name):
        return [(t,e) for t,e in all_events if e[0]=='cpu' and int(e[4],16)==labels[name]]
    starts=[t for t,e in marks('sio_start')]
    stop=marks('sio_shutdown')[0][0]
    events=[(t,e) for t,e in all_events if starts[0]<=t<=stop]
    def times(name):return [t for t,e in marks(name) if starts[0]<=t<=stop]
    failures=result['violations']
    def check(ok,message):
        if not ok:failures.append(message)
    count=len(order)
    posts=times('signal_post'); retires=times('sio_retire')
    check(len(starts)==len(posts)==len(retires)==count,'incomplete completion timeline')
    check(all(a<=b<=c for a,b,c in zip(starts,posts,retires)),'completion order')
    expected_tx=[];expected_rx=[]
    for identity in order:
        slot=(identity&15)>>1;round_=identity>>4
        writing=round_==1 and sector_size==128
        command=[49+(slot&1),0x51 if speed==2 else 0x50 if writing else 0x52,slot+4,0]
        expected_tx.append(command+[checksum(command)])
        payload=[i ^ (slot ^ 0xa7 if round_ and sector_size==128 else (slot+4)*15) for i in range(sector_size)]
        if speed==2:expected_rx += [0x41,0x43]
        elif writing:
            expected_tx.append(payload+[checksum(payload)])
            expected_rx += [0x41,0x41,0x43]
        else:expected_rx += [0x41,0x43]+payload+[checksum(payload)]
    check(result['tx_frames']==expected_tx,'wire FIFO/command/payload identity')
    check(result['rx_bytes']==expected_rx,'wire response/payload identity')
    rxstarts=[(t,e) for t,e in events if e[0]=='rxstart']
    receives=[(t,e) for t,e in events if e[0]=='receive']
    reads=[(t,e) for t,e in events if e[0]=='read']
    # Task retirement deliberately discards SERIN once; match real receives
    # independently and do not interpret that discard as a second data byte.
    check(len(rxstarts)==len(receives)==len(expected_rx),'RX framing count')
    check(all(int(e[3])==(14,93,91)[speed] for t,e in rxstarts),'RX baud')
    check(all(int(e[3])&32 and int(e[5])&0xa0==0xa0 for t,e in receives),'RX disabled/framing/overrun')
    for (arrival,e),(begin,framing) in zip(receives,rxstarts):
        read=next((q for q,r in reads if q>=arrival),None)
        check(read is not None and read-arrival<int(framing[3])*10,'RX physical byte deadline')
    result['rx_byte_deadline_us']=(14,93,91)[speed]*10/BASE_HZ*1e6
    root_calls={v for k,v in labels.items() if k.startswith('M_SIOCONCURRENT_')}
    progress=sum(e[0]=='cpu' and int(e[4],16) in root_calls and int(e[9],16)==labels['root_dp'] and any(a<=t<=b for a,b in zip(starts,posts)) for t,e in events)
    check(progress>0,'no background execution during active transactions')
    result['active_background_entries']=progress
    windows=list(zip(starts,retires))
    active_masks=[]
    for a,b in windows:active_masks += masked_intervals(all_events,a,b)
    result['active_masked_max_us']=max(v['duration_us'] for v in active_masks)
    result['resident_masked_max_us']=result.pop('masked_max_us')
    critic=[b-a for a,b in windows]  # Conservative superset of actual CRITIC interval.
    post_worker=[b-a for a,b in zip(posts,retires)]
    next_start=[b-a for a,b in zip(posts,starts[1:])]
    batches=times('collected')
    check(len(batches)*2==count and len(collected)==count,'incomplete collection timeline')
    posting=dict(zip(order,posts));collection=[]
    for t,ids in zip(batches,zip(collected[::2],collected[1::2])):
        for identity in ids:
            check(identity in posting,'unknown collection identity')
            if identity in posting:collection.append(t-posting[identity])
    for name,values,limit in [('critic_deferral_bound',critic,LIMITS['critic_max_us']),
                            ('post_to_worker',post_worker,LIMITS['post_to_worker_max_us']),
                            ('post_to_next_start',next_start,LIMITS['next_start_max_us']),
                            ('post_to_client_collection',collection,LIMITS['post_to_collect_max_us'])]:
        result[name]=stats(values)
        check(all(0<=v/BASE_HZ*1e6<=limit for v in values),name+' deadline')
    # Record task-side Forbid/Permit pairs by direct-page ownership. Startup
    # precedes the timed interval; only balanced workload/worker sections count.
    nesting={};forbids=[]
    for t,e in all_events:
        if t<starts[0] or e[0]!='cpu':continue
        pc=int(e[4],16);dp=e[9]
        if pc==labels['tasks_forbid']:
            nesting.setdefault(dp,[]).append(t)
        elif pc==labels['tasks_permit'] and nesting.get(dp):
            forbids.append(t-nesting[dp].pop())
    check(not any(nesting.values()),'unbalanced workload Forbid')
    check(forbids and all(v/BASE_HZ*1e6<=LIMITS['forbid_max_us'] for v in forbids),'Forbid duration')
    result['forbid']=stats(forbids)
    # A timer edge may be retired by the simultaneous terminal byte. Only an
    # edge before a later edge or terminal is required to reach its ISR body.
    alarms={}
    for channel,name in [(0,'sio_alarm'),(1,'sio_watchdog')]:
        delays,cancelled,unserviced=alarm_observations(events,times(name),posts,stop,channel)
        check(all(0<=v/BASE_HZ*1e6<=LIMITS['alarm_lateness_us'] for v in delays),'alarm lateness')
        check(all(0<=v/BASE_HZ*1e6<=LIMITS['alarm_lateness_us'] for v in cancelled+unserviced),'unserviced alarm')
        alarms[name]=stats(delays)
        alarms[name]['cancelled']=stats(cancelled)
    result['alarms']=alarms
    # The write payload must wait after a physically complete command ACK.
    ready=[(t,e) for t,e in events if e[0]=='ready'];gaps=[]
    for i,identity in enumerate(order):
        if speed==2 or sector_size!=128 or identity>>4!=1:continue
        finish=posts[i];begin=starts[i]
        ack=next(((t,e) for t,e in rxstarts if begin<=t<=finish),None)
        if ack:
            payload=next((t for t,e in ready if t>ack[0]),None)
            check(payload is not None,'missing write payload')
            if payload is not None:gaps.append(payload-(ack[0]+int(ack[1][3])*10))
        else:check(False,'missing write ACK')
    lo,hi=LIMITS['write_delay_us']
    check(all(lo<=v/BASE_HZ*1e6<=hi for v in gaps),'write delay window')
    result['write_delay']=stats(gaps)
    result['tx_bytes']=sum(map(len,expected_tx));result['rx_bytes']=len(expected_rx)
    result.pop('tx_frames')
    result['tx_baud']=BASE_HZ/(94 if speed else 14)
    result['rx_cycles_per_bit']=sorted({int(e[3]) for t,e in rxstarts})
    result['observations_sha256']=hashlib.sha256('\n'.join(' '.join(e) for t,e in all_events).encode()).hexdigest()
    result['violations']=sorted(set(failures));result['verdict']='fail' if failures else 'pass'
    return result
