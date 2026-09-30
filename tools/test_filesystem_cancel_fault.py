#!/usr/bin/env python3
"""Break during real SIO errors: preserve cause, exact retirement and reset latch."""
import argparse,json,os,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read as far_read
from test_filesystem_active_cancel import instrument

CASES={'checksum':(4,0),'device':(3,0),'short':(1,1),'firstcause':(3,1),'framing':(6,1),'protocol':(7,1)}

def run(out,optimize,size,names,point):
    observers=instrument(out,'mydos')
    worker=out/'fsworker.act'
    source=worker.read_text();old='        service.resultState=FSIO.Complete(service)'
    require(source.count(old)==1,'Stale terminal fault checkpoint')
    worker.write_text(source.replace(old,old+'\n        FSACTIVEPROBE.Deliver(service,11)'))
    observers['fsworker.act']=sha256(worker)
    selector=out/'fault.txt';selector.write_text('none\n')
    os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    pin=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
    binary=ROOT/'build/altirra-sio-sector-faults'
    require(sha256(binary/'AltirraBridgeServer')==pin['fault_responder']['binary_sha256'],'Unpinned responder')
    media=out/'volume.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);old_media=sha256(media)
    # Alias D1 to the fault responder's physical unit; only host fault selection
    # changes after normal Open/Lock and before the first file-data transfer.
    source=out/'filesystem_cancel_fault.act';source.write_bytes((ROOT/'tests/programs'/source.name).read_bytes())
    p=build(compiler(ROOT/'build/actionc'),source,out,optimize=optimize,tasks=True,task_capacity=8,console=True,
            dos_mounts=[dict(alias='D1',unit=56,sectors=720 if size==128 else 2000,sector_bytes=size,profile=1)])
    selected=dict(p['image'],data=[d for d in p['image']['data'] if '_FILESYSTEMCANCELFAULT_' in d['name']])
    def at(name):return next(d['address'] for d in selected['data'] if '_'+name.upper()+'_' in d['name'])
    cases=[]
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        b.config('diskemu','fastest');b.mount(7,str(media))
        for i,name in enumerate(names):
            print('Cancellation fault',name,flush=True)
            expected,offline=CASES[name];selector.write_text('none\n')
            caseout=out/name;caseout.mkdir(exist_ok=True);saved={}
            if i:b.state_load(slot='loaded')
            def pause(phase):
                marker=p['labels']['native_cop'];condition=f'db(${at("phase"):x})={phase}'
                b.bp_set(marker,condition=condition)
                run_to(b,marker,timeout=240,frame_limit=12000,condition=condition);b.bp_clear_all()
            def before(b):
                if not i:b.state_save(slot='loaded')
                for key,value in dict(expected=expected,offline=offline,point=point).items():b.poke(at(key),value)
                saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
                pause(1);selector.write_text(name+'\n');b.poke(at('gate'),1)
                if not offline:
                    pause(2);selector.write_text('none\n');b.poke(at('gate'),1)
            try:runtime,_=execute(b,{**p,'output':caseout},before_run=before,expected_status=0xff93 if offline else 0,timeout=600,frame_limit=30000,preloaded=bool(i))
            except Exception:
                print('Fault state',{n:data(b,selected,n,True) for n in ('checks','result','error')},flush=True);raise
            require(data(b,selected,'cleanupReached')==[1],'Software ownership did not retire: '+str({n:data(b,selected,n,True) for n in ('checks','result','error')}))
            hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,caseout)
            require(hardware[45]==offline,'Offline latch changed')
            require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained caller buffer')
            if not offline:
                ownership(b,p,out)
                require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console not restored')
            probe=dict(p['image'],data=[d for d in p['image']['data'] if '_FSACTIVEPROBE_' in d['name']])
            cases.append(dict(name=name,status='pass',runtime=runtime,checks=data(b,selected,'checks',True),error=data(b,selected,'error'),hardware=hardware.hex(),offline=offline,cleanup_reached=True,wire_phase=data(b,probe,'wirePhase')))
            (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
        require(sha256(media)==old_media,'Read-only media changed')
    return dict(status='pass',build=p['build'],cases=cases,machine=machine,pin=pin,observers=observers,sector_bytes=size,point=point,media_sha256=old_media,
                scope='Real peripheral errors, Task-side break injection during wire activity, a fast terminal race (reported wire phase), or after terminal error. Unsafe cases assert reset-required status after complete software cleanup, not OS restoration.',bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--size',type=int,choices=(128,256),default=128)
    a.add_argument('--point',type=int,choices=(3,11),default=3);a.add_argument('--suite',default=','.join(CASES));a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.case=='opt',args.size,args.suite.split(','),args.point)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Filesystem fault cancellation passed',args.case,args.size,args.point,flush=True)
