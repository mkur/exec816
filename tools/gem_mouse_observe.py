"""Read-only cursor timing and real-controller rate workload."""
import hashlib
from bisect import bisect_left
import adapter_state as adapter
from native_program import require
from gem_render_oracle import PENS,PALETTE
from test_gem_interactive import scene
from sio_transaction_trace import read_events,stats,BASE_HZ
from sio_adapter_trace import analyze
from mouse_timer_trace import accounting

def timing(path,labels,divisor=8,serial=True):
    events=read_events(path)
    marks=lambda label:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==labels[label]]
    reads=marks('pointer_port_read');starts=marks('pointer_sample');ends=marks('pointer_sample_return')
    gaps=[b-a for a,b in zip(reads,reads[1:])]
    require(gaps and max(gaps)/BASE_HZ<.001,'Pointer sampling gap exceeds 1 ms: '+str(stats(gaps)))
    costs=[]
    for t in starts:
        i=bisect_left(ends,t)
        if i<len(ends):costs.append(ends[i]-t)
    entries=marks('native_irq');returns=marks('signal_route_return')
    irq_costs=[]
    for t in entries:
        i=bisect_left(returns,t)
        if i<len(returns):irq_costs.append(returns[i]-t)
    sio=analyze(path,labels,divisor=divisor,all_events=events) if serial else None
    if serial:require(sio['verdict']=='pass','Mouse/SIO timing: '+str(sio['violations']))
    return dict(sample_gaps=stats(gaps),sample_cost=stats(costs),sample_count=len(reads),
                native_irq_service=stats(irq_costs),irq_cost_scope='Native IRQ entry through fixed source routing return; scheduler/RTI excluded',
                serial=sio,timer_accounting=accounting(path,labels,events)),reads

def visible(b,p,foreign,output,folder,reach,get,command,expected,observe):
    sy=foreign['symbols'];capture=p['build']['memory']['input_storage']['POINTER_CAPTURE']
    rgb=bytes((v&254)+(v>>7) for v in PALETTE);hardware=[None]*16
    for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
    samples=[]
    for i,(dx,dy) in enumerate(((8,0),(0,8),(-8,-8))):
        # Begin with an empty native/GUI queue and completed cursor packet.
        reach(f'(dw(${sy["dirty"]:x})=0)&(dw(${sy["pointerDirty"]:x})=0)&'
              f'(dw(${sy["client"]+12:x})=0)&(dw(${sy["client"]+14:x})=0)')
        head=b.peek(capture+1)[0];old=list(expected)
        command(2000,dx*16,dy*16)
        reach(f'db(${capture+1:x})!={head}','native_irq')
        raw=b.memdump(capture+128+(head&31)*24,24)
        tick=int.from_bytes(raw[8:10],'little')
        expected[:]=[old[0]+dx,old[1]+dy]
        # Compare a stable blank region containing both old and new arrows;
        # disk progress redraws elsewhere must not affect this observer.
        packed=scene(output,cursor=tuple(expected))
        x0=min(old[0],expected[0]);x1=max(old[0],expected[0])+16
        y0=min(old[1],expected[1]);y1=max(old[1],expected[1])+16
        color=lambda x,y:(packed[y*320+x//2]>>(4 if x%2==0 else 0))&15
        golden=b''.join(hardware[color(x,y)] for y in range(y0,y1) for x in range(x0,x1))
        scans=[]
        for attempt in range(15):
            path=folder/f'mouse-latency-{i}-{attempt}.bgra';frame=b.rawscreen(str(path));data=path.read_bytes()
            actual=b''.join(data[y*frame.stride+(x+16)*4:y*frame.stride+(x+16)*4+3] for y in range(y0,y1) for x in range(x0,x1))
            scans.append(dict(tick=b.peek16(adapter.VBI_COUNT),matches=actual==golden,sha256=hashlib.sha256(actual).hexdigest()))
            if actual==golden:break
            reach(f'@frame>{b.eval_expr("@frame")}')
        latency=(scans[-1]['tick']-tick)&65535
        samples.append(dict(first_record=raw.hex(),capture_tick=tick,scans=scans,latency_ticks=latency,position=list(expected)))
        require(scans[-1]['matches'] and latency<=12,'Mouse response exceeds twelve PAL ticks: '+str(samples[-1]))
        observe('visible-latency')
    return dict(samples=samples,maximum_ticks=max(s['latency_ticks'] for s in samples))
