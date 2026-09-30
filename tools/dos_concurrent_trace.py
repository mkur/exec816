"""Passive native packet, real media, wire and scheduling timing oracles."""
from bisect import bisect_left
import hashlib
from sio_adapter_trace import analyze as wire_timing
from sio_transaction_trace import read_events,checksum,stats,BASE_HZ
from sio_concurrent_trace import LIMITS,alarm_observations
from mydos_fixtures import Image
from os_boundary import require

def call_marker(p,prefix,label,after=False):
    routine=next(r for r in p['image']['routines'] if r['name'].startswith(prefix))
    raw=bytearray(routine['size']);start=routine['address']
    for s in p['image']['segments']:
        lo=max(start,s['address']);hi=min(start+len(raw),s['address']+len(s['bytes']))
        if lo<hi:raw[lo-start:hi-start]=bytes(s['bytes'][lo-s['address']:hi-s['address']])
    needle=b'\x22'+p['labels'][label].to_bytes(3,'little')
    hits=[i for i in range(len(raw)-3) if raw[i:i+4]==needle]
    require(len(hits)==1,'Ambiguous native JSL marker '+prefix+' '+label)
    return start+hits[0]+(4 if after else 0)

def sector_end_marker(p):
    # Collect can return pending. The worker's return from Transfer marks
    # terminal collection only, after BLOCKWIRE has translated any abort.
    routine=next(r for r in p['image']['routines'] if r['name'].startswith('M_BLOCKWIRE_TRANSFER_'))
    view=dict(p,labels={**p['labels'],'blockwire_transfer':routine['address']})
    return call_marker(view,'M_FSWORKER_WORKER_','blockwire_transfer',True)

def packet_marks(p):
    # No added instructions. Native GetMsg returns the complete Message pointer
    # in A16/X8; observe it before the caller stores/pops anything.
    from generate_ports import ABI
    require(ABI['imports']['GetMsg']['result_bytes']==3,'GetMsg result ABI changed')
    return dict(dos_submit=call_marker(p,'M_DOSCLIENT_CALL_','ports_put_msg'),
                dos_dispatch=call_marker(p,'M_FSHANDLER_TAKESTEP_','ports_get_msg',True),
                dos_collect=call_marker(p,'M_DOSCLIENT_CALL_','ports_get_msg',True))

def packet_observations(events,labels,check):
    by_dp={};dispatch={};turnaround=[];queue=[];service=[];operations=[]
    for t,e in events:
        if e[0]!='cpu':continue
        pc=int(e[4],16);dp=int(e[9],16)
        pointer=(int(e[5],16)&65535)|((int(e[6],16)&255)<<16)
        if pc==labels['dos_submit']:
            check(dp not in by_dp,'overlapping caller packets');by_dp[dp]=t
        elif pc==labels['dos_dispatch'] and pointer:
            check(pointer not in dispatch,'duplicate handler dequeue');dispatch[pointer]=t
        elif pc==labels['dos_collect'] and pointer:
            check(dp in by_dp and pointer in dispatch,'uncorrelated packet collection')
            if dp not in by_dp or pointer not in dispatch:continue
            sent=by_dp.pop(dp);taken=dispatch.pop(pointer)
            check(sent<=taken<=t,'invalid packet timeline')
            turnaround.append(t-sent);queue.append(taken-sent);service.append(t-taken)
            operations.append(dict(dp=dp,packet=pointer,submitted=sent,dispatched=taken,collected=t))
    check(not by_dp and not dispatch,'uncollected DOS packet')
    check(bool(operations),'missing DOS packet observations')
    return dict(count=len(operations),turnaround=stats(turnaround),queue_wait=stats(queue),dequeue_to_collection=stats(service),caller_dps=sorted({v['dp'] for v in operations}),
                boundary='JSL PutMsg entry -> GetMsg return in handler -> GetMsg return in caller; queue wait includes gateway/dequeue overhead, one outstanding packet per caller.'),operations

def analyze(path,labels,media,size,speed,wire_count,byte_count,guest_seconds):
    all_events=read_events(path)
    result=wire_timing(path,labels,40 if speed else 0,all_events)
    failures=result['violations']
    def check(ok,message):
        if not ok:failures.append(message)
    marker=lambda name:[t for t,e in all_events if e[0]=='cpu' and int(e[4],16)==labels[name]]
    starts=marker('sio_start');stop=marker('sio_shutdown')[0]
    events=[(t,e) for t,e in all_events if starts[0]<=t<=stop]
    times=lambda name:[t for t in marker(name) if starts[0]<=t<=stop]
    posts=times('signal_post');retires=times('sio_retire')
    check(len(starts)==len(posts)==len(retires)==wire_count,'lost/duplicate wire completion')
    images={49+i:Image(p.read_bytes()) for i,p in enumerate(media)}
    frames=result['tx_frames'];expected=[];sectors=[]
    for command in frames:
        check(len(command)==5 and command[1]==0x52 and command[-1]==checksum(command[:-1]),'unexpected write/command frame')
        if len(command)!=5 or command[0] not in images:check(False,'unknown unit');continue
        disk=images[command[0]];sector=command[2]+(command[3]<<8)
        check(1<=sector<=disk.count,'out-of-range sector')
        if not 1<=sector<=disk.count:continue
        payload=list(disk.sector(sector));expected += [0x41,0x43]+payload+[checksum(payload)]
        sectors.append((command[0],sector))
    check(len(frames)==wire_count,'incomplete wire command count')
    check({u for u,_ in sectors}=={49,50},'missing second mounted unit')
    check(result['rx_bytes']==expected,'wire bytes differ from original media')
    rxstarts=[(t,e) for t,e in events if e[0]=='rxstart'];receives=[(t,e) for t,e in events if e[0]=='receive']
    reads=[(t,e) for t,e in events if e[0]=='read'];read_times=[t for t,e in reads]
    check(len(rxstarts)==len(receives)==len(expected),'incomplete RX framing')
    for (arrival,e),(begin,framing) in zip(receives,rxstarts):
        i=bisect_left(read_times,arrival)
        check(i<len(reads) and reads[i][0]-arrival<int(framing[3])*10,'RX physical byte deadline')
        check(int(framing[3])==(14 if speed==0 else 93),'unexpected RX baud')
    result['rx_byte_deadline_us']=(14 if speed==0 else 93)*10/BASE_HZ*1e6
    for name,values,bound in [('critic_deferral_bound',[b-a for a,b in zip(starts,retires)],LIMITS['critic_max_us']),('post_to_worker',[b-a for a,b in zip(posts,retires)],LIMITS['post_to_worker_max_us'])]:
        result[name]=stats(values);check(all(0<=v/BASE_HZ*1e6<=bound for v in values),name+' deadline')
    alarms={}
    for channel,name in ((0,'sio_alarm'),(1,'sio_watchdog')):
        delay,cancelled,unserviced=alarm_observations(events,times(name),posts,stop,channel)
        check(all(0<=v/BASE_HZ*1e6<=LIMITS['alarm_lateness_us'] for v in delay+cancelled+unserviced),'alarm deadline')
        alarms[name]={**stats(delay),'cancelled':stats(cancelled)}
    result['alarms']=alarms
    nesting={};forbids=[]
    for t,e in all_events:
        if e[0]!='cpu':continue
        pc=int(e[4],16);dp=e[9]
        if pc==labels['tasks_forbid']:nesting.setdefault(dp,[]).append(t)
        elif pc==labels['tasks_permit'] and nesting.get(dp):forbids.append(t-nesting[dp].pop())
    check(not any(nesting.values()),'unbalanced Forbid')
    check(forbids and all(v/BASE_HZ*1e6<=LIMITS['forbid_max_us'] for v in forbids),'Forbid deadline')
    result['forbid']=stats(forbids)
    background=next(v for k,v in labels.items() if k.startswith('M_DOSCONCURRENT_BACKGROUND_'))
    # A binary search into non-overlapping active transactions avoids a quadratic
    # pass over the long-file trace.
    progress=0
    for t,e in events:
        if e[0]=='cpu' and int(e[4],16)==background and int(e[9],16)==labels['root_dp']:
            i=bisect_left(posts,t)
            if i<len(starts) and starts[i]<=t<=posts[i]:progress+=1
    check(progress>0,'no background CPU work during wire transfer');result['active_background_entries']=progress
    packets,_=packet_observations(all_events,labels,check);result['packets']=packets
    check(packets['turnaround']['max_us']<=guest_seconds*1e6,'DOS operation exceeded workload bound')
    elapsed=(stop-starts[0])/BASE_HZ
    result['elapsed_seconds']=elapsed;result['verified_file_bytes']=byte_count;result['file_bytes_per_second']=byte_count/elapsed
    result['wire_payload_bytes']=sum(len(images[u].sector(s)) for u,s in sectors)
    result['rx_bytes']=len(expected);result['tx_bytes']=sum(map(len,frames));result.pop('tx_frames')
    result['observations_sha256']=hashlib.sha256('\n'.join(' '.join(e) for t,e in all_events).encode()).hexdigest()
    result['violations']=sorted(set(failures));result['verdict']='fail' if failures else 'pass'
    return result
