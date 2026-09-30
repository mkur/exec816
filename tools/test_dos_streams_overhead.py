#!/usr/bin/env python3
"""Fixed 40-byte direct-Exec versus DOS completion cost, with identical replay."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from sio_transaction_trace import read_events
from console_concurrent_trace import distribution


def run(t,out,mode):
    out.mkdir(parents=True,exist_ok=True)
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    p=build(t,ROOT/'tests/programs/dos_streams_overhead.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True)
    names=[api+stage+edge for api in ('Direct','Dos') for stage in ('Open','First','Steady') for edge in ('Begin','End')]
    marks={n:next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_STREAMCOST_'+n.upper()+'_')) for n in names}
    cases=[]
    for trace in (True,False):
        dest=out/('observed' if trace else 'replay');dest.mkdir(exist_ok=True)
        for n in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):os.environ.pop(n,None)
        if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
        with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',dest,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);saved={}
            def before(b):
                saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
                if trace:b.profile_start()
            rt,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            if trace:b.profile_stop()
            counts={n:int.from_bytes(bytes(data(b,p['image'],n)),'little') for n in ('edges','writes')}
            require(counts==dict(edges=40,writes=18) and rt['created']==1,'Incomplete overhead fixture')
            require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Overhead fixture did not restore console')
            ownership(b,p,out)
            case=dict(status='pass',runtime=rt,machine=machine,counts=counts)
        if trace:
            with (dest/'emulator.log').open() as src,(dest/'trace.log').open('w') as dst:
                for line in src:
                    if '[SIOPOC] ' in line or '[SIOTXN] ' in line:dst.write(line)
            events=read_events(dest/'trace.log');timing={}
            times=lambda name:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
            for api in ('Direct','Dos'):
                timing[api]={}
                for stage in ('Open','First','Steady'):
                    begin,end=times(api+stage+'Begin'),times(api+stage+'End')
                    require(len(begin)==len(end)==(8 if stage=='Steady' else 1),'Missing overhead timing edges')
                    require(all(a<=b for a,b in zip(begin,end)),'Overhead edge ordering')
                    timing[api][stage]=distribution([b-a for a,b in zip(begin,end)])
            timing['additional_dos_mean_us']={stage:timing['Dos'][stage]['mean_us']-timing['Direct'][stage]['mean_us'] for stage in ('Open','First','Steady')}
            case['timing']=timing;case['trace_sha256']=sha256(dest/'trace.log')
        cases.append(case);(dest/'case.json').write_text(json.dumps(case,indent=2)+'\n')
    return dict(status='pass',mode=mode,build=p['build'],marks=marks,cases=cases,
        limits=dict(host_seconds=240,guest_frames=12000),scope='Same 40 upper-RAM source bytes, one first transfer and eight steady transfers each; native marker entry to entry includes gateway, checks, worker execution and scheduling. Open includes allocation. First DOS transfer includes lazy request allocation. No scrolling; 18 full rows. Identical-image replay has observers disabled.')

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(args.compiler_dir),out,args.case)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS streams overhead passed',args.case,flush=True)
