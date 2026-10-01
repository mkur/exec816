"""Passive attribution of DOS endpoint Forbid and active CPU masking intervals."""
from bisect import bisect_left
from native_program import require
from sio_transaction_trace import read_events,BASE_HZ
from console_concurrent_trace import distribution
from test_signal_concurrency import masked_intervals


def endpoint_marks(p):
    marks={}
    idle=p['labels']['idle_start']
    native=(p['output']/'hosted.bin').read_bytes();offset=idle-p['build']['memory']['regions']['resident'][0]
    require(native[offset]==0x78 and native[offset+19:offset+21]==b'\xcb\x58','Idle SEI/WAI/CLI layout changed')
    marks['stream_idle_cli_after']=idle+21
    for r in p['image']['routines']:
        if not r['name'].startswith('M_DOSRAW_'):continue
        raw=bytearray(r['size']);start=r['address']
        for s in p['image']['segments']:
            lo=max(start,s['address']);hi=min(start+len(raw),s['address']+len(s['bytes']))
            if lo<hi:raw[lo-start:hi-start]=bytes(s['bytes'][lo-s['address']:hi-s['address']])
        needle=b'\x22'+p['labels']['tasks_forbid'].to_bytes(3,'little')
        for i in range(len(raw)-3):
            if raw[i:i+4]==needle:marks['endpoint_'+r['name']+'_'+str(i)]=start+i
    require(len(marks)>1,'No endpoint Forbid call sites')
    return marks


def analyze(path,marks):
    events=read_events(path)
    callers={pc:name for name,pc in marks.items() if name.startswith('endpoint_')}
    pending={};active={};intervals=[]
    for t,e in events:
        if e[0]!='cpu':continue
        pc=int(e[4],16);dp=e[9]
        if pc in callers:pending[dp]=callers[pc]
        elif pc==marks['tasks_forbid']:active.setdefault(dp,[]).append((t,pending.pop(dp,None)))
        elif pc==marks['tasks_permit'] and active.get(dp):
            begin,name=active[dp].pop()
            if name:intervals.append(dict(start_tick=begin,end_tick=t,call_site=name,duration_us=(t-begin)/BASE_HZ*1e6))
    require(intervals and not pending and not any(active.values()),'Incomplete endpoint Forbid timeline')
    times=lambda name:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
    starts=times('sio_start');ends=times('sio_retire');stop=times('sio_shutdown')[0]
    masks=masked_intervals(events,starts[0],stop)
    cpu=[];idle=[]
    for item in masks:
        # The idle path is SEI/WAI/CLI; the transition out of I occurs at CLI.
        # Attribute by its qualified native label, not by a duration threshold.
        idle_wait=item['exit_pc']==marks['stream_idle_cli_after']
        index=bisect_left(ends,item['start_tick'])
        while index<len(starts) and starts[index]<item['end_tick']:
            duration=min(item['end_tick'],ends[index])-max(item['start_tick'],starts[index])
            if duration>0:(idle if idle_wait else cpu).append(dict(item,transaction=index,overlap_us=duration/BASE_HZ*1e6))
            index+=1
    require(cpu,'No active CPU masked observations')
    return dict(endpoint_forbid=distribution([v['end_tick']-v['start_tick'] for v in intervals]),
        endpoint_forbid_max=max(intervals,key=lambda x:x['duration_us']),
        endpoint_call_sites=sorted({v['call_site'] for v in intervals}),
        active_cpu_masked_max=max(cpu,key=lambda x:x['overlap_us']),
        active_idle_masked_max=max(idle,key=lambda x:x['overlap_us']) if idle else None,
        boundary='Endpoint caller JSL attribution, native Forbid entry to native Permit entry; IRQs remain permitted. Mask intervals overlap live serial transactions; SEI/WAI/CLI idle intervals are classified by the CLI return PC and reported separately.')
