#!/usr/bin/env python3
"""Emitted cancellation/recovery with a real serial fault responder on D8."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256,read_build
from os_boundary import emulator
from sector_images import disk_image
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership
from test_sio_device import PIN
# kind, unit, expected first error, latched offline, peripheral fault
CASES={'queued':(0,49,0,0,''),'preparing':(1,49,254,0,''),
       'active':(2,49,254,1,''),'terminal':(3,49,0,0,''),
       'wrap':(4,56,1,1,''),'nak':(5,49,2,0,''),'absent':(6,56,1,1,''),
       'overrun':(7,49,5,1,''),'bound-worker':(8,49,0,0,''),
       'startup-binding':(10,49,0,0,''),'startup-capacity':(11,49,0,0,''),'duplicate-entry':(12,49,0,0,''),
       'device':(9,56,3,0,'device'),'checksum':(9,56,4,0,'checksum'),
       'short':(9,56,1,1,'short'),'firstcause':(9,56,3,1,'firstcause'),
       'extra':(9,56,0,1,'extra'),'late':(9,56,0,1,'late'),
       'framing':(9,56,6,1,'framing'),'protocol':(9,56,7,1,'protocol'),
       'late-preparing':(13,56,0,1,'late'),'reuse':(14,49,0,0,''),
       'claim-race':(15,49,254,0,''),'reply-race':(16,49,0,0,'')}

def run(t,out,optimize,names,trace=False,sector_size=128,prepared=None):
    p=prepared or build(t,ROOT/'tests/programs/sio_recovery.act',out,optimize=optimize,tasks=True,io_test_device=True,
            sio_request_probe=bool({'claim-race','reply-race'} & set(names)))
    require(p['build']['optimize']==optimize,'Wrong NIR replay mode')
    selector=out/'fault.txt';selector.write_text('none\n')
    os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(key,None)
    pin=PIN if sector_size==128 else json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
    binary=ROOT/('build/altirra-sio-faults' if sector_size==128 else 'build/altirra-sio-sector-faults')
    require(sha256(binary/'AltirraBridgeServer')==pin['fault_responder']['binary_sha256'],'Unpinned responder')
    marks={k:v for k,v in p['labels'].items() if k.startswith(('sio_','native_'))}
    marks.update({r['name']:r['address'] for r in p['image']['routines'] if r['name'].startswith('M_SIODRIVER_ABORTIO_')})
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    cases=[]
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest')
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        for number,name in enumerate(names):
            print('Running',name,flush=True)
            kind,unit,error,offline,fault=CASES[name]
            if number:b.state_load(slot='loaded')
            caseout=out/name;caseout.mkdir(exist_ok=True)
            disk_image(caseout/'disk.atr',sector_size);selector.write_text((fault or 'none')+'\n')
            offset=[0]
            def before(b):
                if not number:b.state_save(slot='loaded')
                b.mount(0,str(caseout/'disk.atr'))
                if fault:b.mount(7,str(caseout/'disk.atr'))
                for name,value in dict(kind=kind,unit=unit,expected=error,offlineExpected=offline).items():
                    symbol=next(d for d in p['image']['data'] if '_'+name.upper()+'_' in d['name'])
                    b.poke(symbol['address'],value)
                symbol=next(d for d in p['image']['data'] if '_SECTORSIZE_' in d['name'])
                for index,value in enumerate(sector_size.to_bytes(2,'little')):b.poke(symbol['address']+index,value)
                if trace:
                    b.profile_start();offset[0]=(out/'emulator.log').stat().st_size
            status=0xff93 if offline else 4 if kind==8 else 0
            try:runtime,_=execute(b,{**p,'output':caseout},before_run=before,expected_status=status,preloaded=bool(number),timeout=240,frame_limit=12000)
            except Exception:
                print('checks',data(b,p['image'],'checks',True),flush=True)
                if int(b.regs()['PC'].lstrip('$'),16)==p['labels']['done']:
                    print('hardware',far_read(b,p['build']['task_storage']['BASE']+0x800,128,caseout).hex(),flush=True)
                raise
            timing=None
            if trace:
                b.profile_stop()
                with (out/'emulator.log').open() as source:
                    source.seek(offset[0]);lines=source.readlines()
                path=caseout/'trace.log';path.write_text(''.join(line for line in lines if '[SIOPOC] ' in line or '[SIOTXN] ' in line))
                timing=recovery_timing(path,p,kind)
            hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,caseout)
            require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained caller pointer')
            require(hardware[45]==offline,'Offline state mismatch')
            cleanup_reached=data(b,p['image'],'cleanupReached')==[1]
            if offline:require(cleanup_reached,'Guest failed before expected offline shutdown')
            posts=int.from_bytes(hardware[56:58],'little')
            baseline=data(b,p['image'],p['recovery_posts_baseline'],True)[0]if 'recovery_posts_baseline'in p else 0
            require(posts==baseline+(0 if kind==8 else 1 if offline else 2),'Duplicate/lost terminal post')
            if not offline:clean_ownership(b,p,p['output'])
            cases.append(dict(name=name,status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),hardware=hardware.hex(),fault=fault,timing=timing,cleanup_reached=cleanup_reached,posts_baseline=baseline))
            (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    return dict(status='pass',build=p['build'],machine=machine,cases=cases,sector_size=sector_size,loaded_snapshot='Paused after banked loader, before native start; restored for each independent case')

def recovery_timing(path,p,kind):
    from sio_transaction_trace import read_events,BASE_HZ,stats
    events=read_events(path)
    marker=lambda address:[t for t,e in events if e[0]=='cpu' and int(e[4],16)==address]
    terminal=marker(p['labels']['sio_terminal'])
    assertions=[t for t,e in events if e[0]=='command' and int(e[2])==1]
    result={}
    if kind in (4,6):
        elapsed=(terminal[0]-assertions[0])/BASE_HZ*1e6
        due=5*7168/BASE_HZ*1e6
        require(due<=elapsed<=due+100,'Silent deadline early/late: '+str(elapsed))
        result.update(deadline_us=due,terminal_us=elapsed,enforcement_lateness_us=elapsed-due)
    if kind==2:
        abort=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_SIODRIVER_ABORTIO_'))
        aborts=marker(abort)
        elapsed=(terminal[0]-aborts[0])/BASE_HZ*1e6
        require(0<=elapsed<=7168/BASE_HZ*1e6+100,'Cancellation observation late')
        result['abort_entry_to_terminal_us']=elapsed
    require(result,'Timing case has no asserted acceptance bound')
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),default='opt')
    parser.add_argument('--trace',action='store_true')
    parser.add_argument('--from-build',type=Path)
    parser.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    parser.add_argument('--suite',default=','.join(CASES));parser.add_argument('--output',type=Path,default=ROOT/'build/sio-recovery')
    a=parser.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result={'status':'running'}
    try:result=run(None if a.from_build else compiler(ROOT/'build/actionc'),out,a.case=='opt',a.suite.split(','),a.trace,a.sector_size,read_build(a.from_build) if a.from_build else None)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Passed recovery',a.case,len(result['cases']),flush=True)
if __name__=='__main__':main()
