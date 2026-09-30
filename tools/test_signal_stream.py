#!/usr/bin/env python3
"""Measure POKEY-ready -> public Wait -> actual SEROUT on the signal kernel."""
import argparse
import json
import os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine
from os_boundary import emulator
from sio_latency import BASE_HZ
from test_cooperative import data
from test_signals_irq import events,PIN


def stats(values):
    ordered=sorted(values)
    return dict(count=len(values),min_us=min(values)/BASE_HZ*1e6,
                max_us=max(values)/BASE_HZ*1e6,mean_us=sum(values)/len(values)/BASE_HZ*1e6,
                p99_us=ordered[(99*len(values)-1)//100]/BASE_HZ*1e6)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-signals-bridge')
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/stream')
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--variant',type=int,choices=(0,1,2),default=0)
    p.add_argument('--count',type=int,default=256)
    p.add_argument('--pump',action='store_true')
    p.add_argument('--task-capacity',type=int,choices=(4,8),default=4)
    p.add_argument('--kernel-bank',type=int)
    p.add_argument('--replay',action='store_true')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    require(2<=args.count<=65535,'Stream length must be 2..65535')
    require(args.pump or args.task_capacity==4,'Worker-per-byte fixture uses the historical four-task pools')
    toolchain=compiler(args.compiler_dir)
    observer=json.loads((ROOT/'toolchain/altirra-signals-observer.json').read_text())
    expected=PIN['emulator']['sha256'] if args.replay else observer['binary_sha256']
    require(sha256(args.bridge_dir/'AltirraBridgeServer')==expected,'Incorrect observer/replay binary')
    require(sha256(args.rom)==PIN['rom']['sha256'],'Incorrect ROM')
    program=build(toolchain,ROOT/('tests/programs/signals_pump.act' if args.pump else 'tests/programs/signals_stream.act'),out/'program',tasks=True,optimize=args.mode=='opt',irq_probe=8 if args.pump else 0,pump_count=args.count,task_capacity=args.task_capacity,kernel_bank=args.kernel_bank)
    markers={n:program['labels'][n] for n in ('native_irq','native_nmi','signal_route_begin','signal_route_return','signal_post','signal_post_return','signal_irq_window')}
    for name in ('STREAMSTART','REFILL'):
        markers[name]=next(r['address'] for r in program['image']['routines'] if r['name'].startswith(('M_SIGNALPUMP_' if args.pump else 'M_SIGNALSTREAM_')+name+'_'))
    for name in ('DRAINONE','DRAINWAKES','COMPLETEWAIT','SELECT'):
        markers[name]=next(r['address'] for r in program['image']['routines'] if r['name'].startswith('M_TASKPOLICY_'+name+'_'))
    routines={name:next(r for r in program['image']['routines'] if r['name'].startswith('M_TASKPOLICY_'+name+'_')) for name in ('DRAINONE','DRAINWAKES')}
    returns={}
    for name,r in routines.items():
        code=next(s for s in program['image']['segments'] if s['address']<=r['address']<s['address']+len(s['bytes']))
        at=r['address']-code['address']
        returns[name]={r['address']+i for i,v in enumerate(code['bytes'][at:at+r['size']]) if v==0x6b}
    observed_pcs=set(markers.values())|set.union(*returns.values())
    env={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    if not args.replay:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{v:x}' for v in sorted(observed_pcs))
    report=dict(schema_version=1,status='running',scope='Diagnostic IRQ byte pump with block-completion signal' if args.pump else 'General public Signal/Wait worker-per-byte delivery',platform=PIN,observer=observer if not args.replay else None,variant=args.variant,count=args.count,build=program['build'],markers=markers)
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),out,pin=PIN) as bridge:
            bridge.config('siopatch','off');bridge.config('burstio','false');bridge.config('randdelay','false')
            report['machine']=verify_machine(bridge,args.rom,PIN)
            def before(b):
                for name,value,size in [('VARIANT',args.variant,1),('BYTECOUNT',args.count,2)]:
                    at=next(d['address'] for d in program['image']['data'] if '_'+name+'_' in d['name'])
                    b.memload(at,value.to_bytes(size,'little'))
                if not args.replay:b.profile_start()
            result,_=execute(bridge,program,before_run=before,timeout=600,frame_limit=30000)
            observed={n:data(bridge,program['image'],n,n in ('sent','waits','background')) for n in ('sent','waits','background','badResult')}
            require(observed['sent']==[args.count] and observed['waits']==[1 if args.pump else args.count] and observed['badResult']==[0]*4,'Stream functional completion: '+str(observed))
            report.update(runtime=result,observed=observed)
        if not args.replay:
            trace=events(out/'emulator.log')
            start=next(i for i,(t,e) in enumerate(trace) if e[0]=='cpu' and int(e[4],16)==markers['STREAMSTART'])
            trace=trace[start:]
            ready=[(t,e) for t,e in trace if e[0]=='ready']
            writes=[(t,e) for t,e in trace if e[0]=='write']
            require(len(ready)==len(writes)==args.count,'Missing/extra serial hardware events')
            require([int(e[2]) for _,e in ready]==[i&255 for i in range(args.count)],'Wrong transmitted sequence')
            require(all(int(e[3])==14 for _,e in ready),'Wrong hardware baud divisor')
            require(all(int(e[4])==0 for _,e in writes),'SEROUT overwritten')
            latency=[w[0]-r[0] for r,w in zip(ready,writes[1:])]
            gaps=[b[0]-a[0]-140 for a,b in zip(ready,ready[1:])]
            idle=[t for t,e in trace if e[0]=='idle']
            require(idle and idle[-1]==ready[-1][0]+140,'Final byte did not complete')
            begin=None;posting=[];active={};transactions={'DRAINONE':[],'DRAINWAKES':[]};ready_transactions=[]
            for t,e in trace:
                if e[0]!='cpu':continue
                require(int(e[3])==8,'Wrong observed CPU multiplier')
                pc=int(e[4],16)
                if pc==markers['signal_post']:begin=t
                if pc==markers['signal_post_return'] and begin is not None:posting.append(t-begin);begin=None
                for name in routines:
                    if pc==markers[name]:
                        require(name not in active,'Recursive kernel drain')
                        active[name]=t
                    if pc in returns[name] and name in active:
                        duration=t-active.pop(name)+6/8
                        transactions[name].append(duration)
                        if name=='DRAINONE' and int(e[5],16)==1:ready_transactions.append(duration)
            worst=max(range(len(latency)),key=latency.__getitem__)
            a,b=ready[worst][0],writes[worst+1][0]
            reverse={v:k for k,v in markers.items()}
            window=[dict(tick=t,event=reverse.get(int(e[4],16),'cpu') if e[0]=='cpu' else e[0]) for t,e in trace if a<=t<=b and (e[0]!='cpu' or int(e[4],16) in reverse)]
            report['timing']=dict(actual_baud=BASE_HZ/14,deadline_us=140/BASE_HZ*1e6,
                ready_to_refill=stats(latency),posting=stats(posting),drain_transactions=stats(transactions['DRAINONE']) if transactions['DRAINONE'] else None,ready_transactions=stats(ready_transactions) if ready_transactions else None,total_drains=stats(transactions['DRAINWAKES']) if transactions['DRAINWAKES'] else None,
                deadline_misses=sum(x>=140 for x in latency),gaps=sum(x>0 for x in gaps),max_gap_us=max(gaps)/BASE_HZ*1e6,
                verdict='pass' if max(latency)<140 and max(gaps)==0 else 'fail',worst_byte=worst,worst_window=window)
            rows=['byte,ready_tick,write_tick,latency_base_cycles,gap_cycles']+[f'{i},{r[0]},{w[0]},{l},{g}' for i,(r,w,l,g) in enumerate(zip(ready,writes[1:],latency,gaps))]
            (out/'refills.csv').write_text('\n'.join(rows)+'\n')
            report['refills_sha256']=sha256(out/'refills.csv')
            print('Timing '+report['timing']['verdict']+': max refill '+str(report['timing']['ready_to_refill']['max_us'])+' us; '+str(report['timing']['deadline_misses'])+' misses')
        report['status']='pass' # Functional/measurement integrity; timing has its own verdict.
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        for key,value in env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        report['trace_sha256']=sha256(out/'emulator.log') if (out/'emulator.log').exists() else None
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
