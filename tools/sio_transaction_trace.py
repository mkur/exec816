"""Independent hardware/CPU observations for the disposable SIO probe."""
import hashlib

from os_boundary import require
from test_signal_concurrency import masked_intervals

BASE_HZ=1773447.5


def read_events(path):
    # Ignore all other bridge output, which may contain session credentials.
    # Text-mode iteration normalizes CRLF before parsing.
    result=[];tick=0;masked=None
    with path.open() as source:
        for line in source:
            tag=next((tag for tag in ('[SIOPOC] ','[SIOTXN] ') if tag in line),None)
            if tag is None:continue
            fields=line.split(tag,1)[1].split()
            value=int(fields[1]);fraction=0
            if fields[0] in ('cpu','mask'):
                value+=round((tick-value)/(1<<32))*(1<<32)
                require(int(fields[3])==8,'Observer CPU multiplier changed')
                fraction=int(fields[2])/8
            tick=value
            if fields[0]=='mask':masked=bool(int(fields[5],16)&4)
            elif fields[0]=='cpu' and masked is not None:
                require(bool(int(fields[11],16)&4)==masked,'CPU status disagrees with mask trace')
            result.append((value+fraction,fields))
    require(result,'No SIO observation events')
    return result


def checksum(data):
    value=0
    for byte in data:
        value+=byte
        value=(value&255)+(value>>8)
    return value


def stats(values):
    if not values:return dict(count=0,max_us=None)
    return dict(count=len(values),min_us=min(values)/BASE_HZ*1e6,
                mean_us=sum(values)/len(values)/BASE_HZ*1e6,max_us=max(values)/BASE_HZ*1e6)


def analyze(path,labels,definitions,limits):
    all_events=read_events(path)
    def marker(event,name):return event[1][0]=='cpu' and int(event[1][4],16)==labels[name]
    start=next(t for t,e in all_events if marker((t,e),'stream_start'))
    events=[(t,e) for t,e in all_events if t>=start]
    posts=[t for t,e in events if marker((t,e),'terminal_post')]
    wakes=[(t,e) for t,e in events if marker((t,e),'worker_wake')]
    waits=[(t,e) for t,e in events if marker((t,e),'wait_call')]
    require(posts and len(posts)==len(wakes)==len(waits),'Incomplete terminal Wait/wake trace')
    for (_,wait),(_,wake) in zip(waits,wakes):
        require(wait[5:]==wake[5:],'Native context changed across Wait')
    finish=wakes[-1][0]
    events=[(t,e) for t,e in events if t<=finish]
    violations=[]
    def check(ok,reason):
        if not ok:violations.append(reason)
    critic_start=None;critic=[]
    for t,e in all_events:
        if any(marker((t,e),name) for name in ('critic_enter','critic_enter_next')):
            if critic_start is None:critic_start=t
        elif any(marker((t,e),name) for name in ('critic_leave','critic_leave_next')):
            check(critic_start is not None,'CRITIC release without acquisition')
            if critic_start is not None:critic.append(t-critic_start)
            critic_start=None
    check(critic_start is None and len(critic)==len(posts),'incomplete CRITIC intervals')
    check(all(t/BASE_HZ*1e6<=limits['critic_max_us'] for t in critic),'CRITIC deferral exceeded')
    # A transmitted frame must remain a continuous physical shifter burst.
    bursts=[];ready=[];writes=[]
    for t,e in events:
        if e[0]=='ready':ready.append((t,e))
        elif e[0]=='write':writes.append((t,e))
        elif e[0]=='idle' and ready:
            bursts.append((ready,writes,t));ready=[];writes=[]
    check(not ready and not writes,'unfinished TX burst')
    scenario=definitions['SCENARIO']
    commands=[[0x31,0x53,0,0],[0x31,0x52,4,0],[0x31,0x50,4,0],[0x31,0x52,4,0]]
    if scenario==1:commands=[[0x32,0x53,0,0]]
    elif scenario==2:commands=[[0x31,0,0,0]]
    elif scenario==3:commands=[[0x31,0x51,0,0]]
    payload=[i^0xa7 for i in range(128)]
    expected=[data+[checksum(data)] for data in commands]
    if scenario==0:expected.insert(3,payload+[checksum(payload)])
    # Negative controls can terminate early; they must fail this normal oracle.
    check(len(bursts)==len(expected),'wrong TX frame count or inter-byte gap')
    refills=[];tx_gaps=[]
    period=20*(definitions['DIVISOR']+7)
    for index,(rs,ws,idle) in enumerate(bursts):
        check(len(rs)==len(ws),'TX register/shifter count mismatch')
        if index<len(expected):check([int(e[2]) for _,e in rs]==expected[index],'wrong transmitted frame bytes')
        check(all(int(e[4])==0 for _,e in ws),'SEROUT overwritten before shifter accepted byte')
        check(all(int(e[3])*10==period for _,e in rs),'unexpected TX baud')
        check(idle-rs[-1][0]==period,'final TX bit not completed')
        for (rt,_),(wt,_) in zip(rs,ws[1:]):
            delay=wt-rt;refills.append(delay)
            check(0<=delay<period,'late TX refill')
        for (a,_),(b,_) in zip(rs,rs[1:]):
            tx_gaps.append(b-a-period)
            check(b-a==period,'TX inter-byte gap')
    receives=[(t,e) for t,e in events if e[0]=='receive']
    reads=[(t,e) for t,e in events if e[0]=='read']
    starts=[(t,e) for t,e in events if e[0]=='rxstart']
    check(len(receives)==len(reads)==len(starts),'RX start/register/read count mismatch')
    rx_delays=[]
    for index,((rt,re),(ct,ce),(st,se)) in enumerate(zip(receives,reads,starts)):
        check(re[2]==ce[2]==se[2],'RX byte overwritten or corrupted')
        check(int(re[3])&0x20 and int(re[5])&0xa0==0xa0,'RX disabled or framing/overrun flag')
        rx_period=int(se[3])*10
        if definitions['DIVISOR']==0:check(int(se[3])==14,'target RX baud changed')
        rx_delays.append(ct-rt)
        check(0<=ct-rt<rx_period,'late SERIN read')
        if index+1<len(receives):check(ct<receives[index+1][0],'RX register overwritten before read')
    edges=[(t,int(e[2])) for t,e in events if e[0]=='command']
    asserts=[t for t,v in edges if v];releases=[t for t,v in edges if not v]
    check(len(asserts)==len(releases)==len(posts),'wrong COMMAND edge count')
    setups=[];holds=[];active=[]
    for a,b,post in zip(asserts,releases,posts):
        frames=[burst for burst in bursts if a<=burst[0][0][0]<b]
        check(len(frames)==1,'COMMAND did not frame exactly one burst')
        if frames:
            setups.append(frames[0][0][0][0]-a);holds.append(b-frames[0][2])
        active.append(post-a)
    write_gaps=[]
    if scenario==0 and len(bursts)>=4 and len(releases)>=3:
        ack=next(((t,e) for t,e in starts if t>=releases[2] and int(e[2])==0x41),None)
        check(ack is not None,'missing write ACK')
        if ack:write_gaps.append(bursts[3][0][0][0]-(ack[0]+int(ack[1][3])*10))
    for name,values in (('command_setup',setups),('command_hold',holds),('write_delay',write_gaps)):
        lo,hi=limits[name+'_us']
        check(all(lo<=value/BASE_HZ*1e6<=hi for value in values),name+' outside profile window')
    check(all(value/BASE_HZ*1e6<=limits['active_max_us'] for value in active),'active timeout exceeded')
    # The periodic timer must not be reset to arm a phase while serial is live.
    check(not any(e[0]=='register' and int(e[2])==9 for _,e in events),'STIMER reset during transaction')
    alarms={}
    for channel,name in ((0,'alarm_service'),(1,'watchdog_service')):
        ticks=[t for t,e in events if e[0]=='timer' and int(e[2])==channel]
        serviced=[t for t,e in events if marker((t,e),name)]
        check(len(ticks)==len(serviced),'lost/coalesced timer event')
        delays=[b-a for a,b in zip(ticks,serviced)]
        check(all(0<=d/BASE_HZ*1e6<=limits['alarm_lateness_us'] for d in delays),'late alarm service')
        alarms[name]=stats(delays)
    intervals=masked_intervals(all_events,start,finish)
    return dict(verdict='pass' if not violations else 'fail',violations=sorted(set(violations)),
        tx_bytes=sum(len(rs) for rs,_,_ in bursts),rx_bytes=len(receives),
        tx_refill=stats(refills),rx_service=stats(rx_delays),
        command_setup=stats(setups),command_hold=stats(holds),write_delay=stats(write_gaps),
        active_duration=stats(active),critic_deferral=stats(critic),alarms=alarms,
        masked_max_us=max(i['duration_us'] for i in intervals),
        post_to_worker=stats([wake[0]-post for wake,post in zip(wakes,posts)]),
        tx_byte_deadline_us=period/BASE_HZ*1e6,tx_baud=BASE_HZ*10/period,
        rx_cycles_per_bit=sorted({int(e[3]) for _,e in starts}),
        observations_sha256=hashlib.sha256('\n'.join(' '.join(e) for _,e in all_events).encode()).hexdigest())
