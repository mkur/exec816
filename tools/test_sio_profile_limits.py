#!/usr/bin/env python3
"""Execute admission and full two-second STOCK810/GENERIC57600 deadlines."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine,read_build
from os_boundary import emulator
from test_mouse_observe import PIN,BRIDGE,ROM
from test_cooperative import data
from banked_test_memory import read as far_read
from sio_transaction_trace import read_events,BASE_HZ

def run(t,out,optimize,replay=False):
    p=read_build(out) if replay else build(t,ROOT/'tests/programs/sio_profile_limits.act',out,optimize=optimize,tasks=True)
    marks={k:v for k,v in p['labels'].items() if k.startswith(('sio_','native_'))}
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    binary=BRIDGE
    require(sha256(binary/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
    cases=[]
    with emulator(binary,ROM,out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROM,PIN)
        for variant in (0,1,2,3):
            if variant:b.state_load(slot='loaded')
            offset=[0]
            def before(b):
                if not variant:b.state_save(slot='loaded')
                b.poke(next(d['address'] for d in p['image']['data'] if '_EXPLICIT_' in d['name']),variant)
                b.profile_start();offset[0]=(out/'emulator.log').stat().st_size
            runtime,_=execute(b,p,before_run=before,preloaded=bool(variant),expected_status=0xff93,timeout=240,frame_limit=12000)
            b.profile_stop()
            hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,out)
            require(int.from_bytes(hardware[6:8],'little')==495 and hardware[45]==1,'Wrong profile deadline/offline state')
            require(int.from_bytes(hardware[56:58],'little')==1,'Rejected request reached hardware')
            require(data(b,p['image'],'checks',True)==[139],'Profile assertions incomplete')
            path=out/f'trace-{variant}.log'
            with (out/'emulator.log').open() as source:
                source.seek(offset[0]);path.write_text(''.join(l for l in source if '[SIOPOC] ' in l or '[SIOTXN] ' in l))
            events=read_events(path)
            start=next(t for t,e in events if e[0]=='command' and e[2]=='1')
            terminal=next(t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks['sio_terminal'])
            late=(terminal-start-495*7168)/BASE_HZ*1e6
            require(0<=late<=100,'Absolute deadline early/late')
            cases.append(dict(name='explicit' if variant&1 else 'default',profile='generic57600' if variant>=2 else 'stock810',status='pass',runtime=runtime,hardware=hardware.hex(),deadline_us=495*7168/BASE_HZ*1e6,lateness_us=late))
    return dict(status='pass',build=p['build'],pin=PIN,machine=machine,cases=cases)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replay',action='store_true')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.replay)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Profile limits passed',args.case)
