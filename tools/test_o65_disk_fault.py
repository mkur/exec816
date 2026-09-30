#!/usr/bin/env python3
"""Peripheral failure while staging an o65 file; recovery or honest reset latch."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from library_paths import read_source
from build_command import compile_command
from make_shell_disk import make
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data
from banked_test_memory import read

PIN=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
CASES={'checksum':(4,False),'device':(3,False),'short':(1,True)}

def instrument_programfile(phase):
    text=read_source(ROOT/'lib/dos/programfile.act').replace('USE EXEC','USE EXEC\nUSE O65FAULTPROBE',1)
    before='  bytes=BYTE POINTER(0)' if phase=='seek' else '        position=0'
    after=('  ' if phase=='seek' else '        ')+'O65FAULTPROBE.Opened(0)\n'+before
    require(text.count(before)==1,'Stale disk-fault checkpoint')
    return text.replace(before,after,1)


def run(out,mode,reuse=False,phase='read'):
    out.mkdir(parents=True,exist_ok=True);toolchain=compiler(ROOT/'build/actionc')
    source=out/'files';source.mkdir(exist_ok=True)
    command=compile_command(toolchain,ROOT/'examples/commands/hello.act',source/'HELLO',mode=='opt')
    (source/'HELLO.options.json').rename(out/'HELLO.options.json')
    (source/'HELLO.profile.json').rename(out/'HELLO.profile.json')
    make(out/'volume.atr',source,binary_names={'HELLO'});digest=sha256(out/'volume.atr')
    for name in ('o65_disk_fault.act','o65faultprobe.act'):(out/name).write_text(read_source(ROOT/'tests/programs'/name))
    text=instrument_programfile(phase)
    if reuse:
        require((out/'programfile.act').read_text()==text,'Replay fault checkpoint differs from the selected build')
    (out/'programfile.act').write_text(text)
    p=read_build(out) if reuse else build(toolchain,out/'o65_disk_fault.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=False,
        dos_mounts=[dict(alias='D1',unit=56,sectors=720,sector_bytes=128,profile=1)])
    selector=out/'fault.txt';selector.write_text('none\n');os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    for name in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(name,None)
    binary=ROOT/'build/altirra-sio-sector-faults'
    require(sha256(binary/'AltirraBridgeServer')==PIN['fault_responder']['binary_sha256'],'Unpinned fault responder')
    results=[]
    for name,(error,offline) in CASES.items():
        case=out/name;case.mkdir(exist_ok=True);selector.write_text('none\n')
        selected=dict(p['image'],data=[d for d in p['image']['data'] if '_O65FAULTPROBE_' in d['name']])
        def at(name):return next(d['address'] for d in selected['data'] if '_'+name.upper()+'_' in d['name'])
        with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',case,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.config('diskemu','fastest');b.mount(7,str(out/'volume.atr'))
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            def before(b):
                b.poke(at('expected'),error);b.poke(at('offline'),int(offline))
                for phase in (1,2):
                    condition=f'db(${at("phase"):x})={phase}'
                    b.bp_set(p['labels']['native_nmi'],condition=condition)
                    run_to(b,p['labels']['native_nmi'],12000,240,condition);b.bp_clear_all()
                    selector.write_text((name if phase==1 else 'none')+'\n')
                    b.poke(at('gate'),1)
            try:runtime,_=execute(b,p,before_run=before,expected_status=0xff93 if offline else 0,timeout=600,frame_limit=30000)
            except Exception:
                print('Fault checks',name,data(b,p['image'],'checks',True),flush=True);raise
            require(data(b,selected,'finished')==[1],'Loader software cleanup did not finish: '+str(dict(case=name,checks=data(b,p['image'],'checks',True),phase=data(b,selected,'phase'),expected=data(b,selected,'expected'),offline=data(b,selected,'offline'))))
            hardware=read(b,p['build']['task_storage']['BASE']+0x800,128,case)
            require(hardware[45]==int(offline) and hardware[12:15]==hardware[16:19]==bytes(3),'SIO ownership/reset latch')
            if not offline:ownership(b,p,out)
            require(sha256(out/'volume.atr')==digest,'Command media changed')
            results.append(dict(status='pass',case=name,runtime=runtime,machine=machine,hardware=hardware.hex(),checks=data(b,p['image'],'checks',True)))
    return dict(status='pass',mode=mode,fault_phase=phase,build=p['build'],command=command,cases=results,pin=PIN,media_sha256=digest,
                observer_sha256=sha256(out/'programfile.act'),bank_zero_delta=dict(fixed=0,per_task=0))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--phase',choices=('seek','read'),default='read')
    args=parser.parse_args();result=run(args.output.resolve(),args.case,args.reuse,args.phase)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Disk loader faults passed',args.case,flush=True)
