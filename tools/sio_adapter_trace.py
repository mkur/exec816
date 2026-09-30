"""Wire timing for the Task SIO adapter; no private bridge output is retained."""
from sio_transaction_trace import read_events,stats,BASE_HZ
from test_signal_concurrency import masked_intervals
from os_boundary import require
from bisect import bisect_left

def transmit_bursts(events,check):
    # COMMAND bounds one frame even if a missed refill idles the shifter.
    # Splitting there used to omit the late pair from refill/gap statistics.
    bursts=[];ready=[];writes=[];command=False;idle=None
    for t,e in events:
        if e[0]=='command':
            if int(e[2]):
                check(not command and not ready and not writes,'overlapping COMMAND/TX')
                command=True;idle=None
            else:
                check(command and bool(ready) and idle is not None,'unfinished COMMAND TX')
                if ready and idle is not None:bursts.append((ready,writes,idle))
                ready=[];writes=[];command=False;idle=None
        elif e[0]=='ready':ready.append((t,e))
        elif e[0]=='write':writes.append((t,e))
        elif e[0]=='idle' and ready:
            if command:idle=t
            else:bursts.append((ready,writes,t));ready=[];writes=[]
    check(not command and not ready and not writes,'unfinished TX burst')
    return bursts

def analyze(path,labels,divisor=0,all_events=None):
    if all_events is None:all_events=read_events(path)
    marks=lambda name:[t for t,e in all_events if e[0]=='cpu' and int(e[4],16)==labels[name]]
    start=marks('sio_start')[0];finish=marks('sio_shutdown')[0]
    events=[(t,e) for t,e in all_events if start<=t<=finish]
    faults=[]
    def check(ok,message):
        if not ok:faults.append(message)
    receives=[(t,e) for t,e in events if e[0]=='receive']
    reads=[(t,e) for t,e in events if e[0]=='read']
    read_times=[t for t,e in reads]
    delays=[]
    for i,(t,e) in enumerate(receives):
        index=bisect_left(read_times,t)
        following=reads[index] if index<len(reads) else None
        check(following is not None,'missing RX read')
        if following:
            q,r=following;delays.append(q-t)
            check(e[2]==r[2] and (int(e[5])&0xa0)==0xa0,'RX corruption/overrun')
            check(q-t<20*(divisor+7),'late RX read')
            if i+1<len(receives):check(q<receives[i+1][0],'RX overwritten before read')
    bursts=transmit_bursts(events,check)
    refill=[];period=20*(divisor+7)
    for rs,ws,end in bursts:
        check(len(rs)==len(ws),'TX shifter/register count mismatch')
        check(all(int(e[4])==0 for t,e in ws),'TX overwrite')
        check(all(int(e[3])*10==period for t,e in rs),'wrong baud')
        check(all(b-a==period for (a,_),(b,_) in zip(rs,rs[1:])),'TX gap')
        check(end-rs[-1][0]==period,'incomplete final byte')
        for (a,_),(b,_) in zip(rs,ws[1:]):
            refill.append(b-a);check(0<=b-a<period,'late TX refill')
    edges=[(t,int(e[2])) for t,e in events if e[0]=='command']
    asserts=[t for t,v in edges if v];releases=[t for t,v in edges if not v]
    check(len(asserts)==len(releases),'unbalanced COMMAND')
    setup=[];hold=[]
    for a,b in zip(asserts,releases):
        frames=[v for v in bursts if a<=v[0][0][0]<b]
        check(len(frames)==1,'COMMAND frame count')
        if frames:
            setup.append(frames[0][0][0][0]-a);hold.append(b-frames[0][2])
    for values,low,high,name in ((setup,750,1600,'setup'),(hold,650,950,'hold')):
        check(all(low<=d/BASE_HZ*1e6<=high for d in values),'COMMAND '+name+' deadline')
    masks=masked_intervals(all_events,start,finish)
    return dict(verdict='fail' if faults else 'pass',violations=sorted(set(faults)),
        rx_service=stats(delays),tx_refill=stats(refill),command_setup=stats(setup),command_hold=stats(hold),
        tx_frames=[[int(e[2]) for _,e in rs] for rs,ws,end in bursts],rx_bytes=[int(e[2]) for _,e in receives],
        masked_max_us=max(i['duration_us'] for i in masks),byte_deadline_us=period/BASE_HZ*1e6)
