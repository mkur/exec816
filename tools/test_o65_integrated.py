#!/usr/bin/env python3
"""Full-capacity disk commands, rollback, cancellation and serial qualification."""
import argparse
import json
import os
import shutil
from pathlib import Path
from build_command import compile_command
from library_paths import read_source
from make_shell_disk import make
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from test_dos_stack import execute, ownership
from test_cooperative import data
from os_boundary import emulator, run_to
from dos_concurrent_trace import sector_end_marker
from console_concurrent_trace import analyze

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def transport_variant(base, out, size, profile):
    """Keep emitted code frozen; vary only the boot-time DOS mount descriptor."""
    from generate_dos_mounts import encode, validate_mounts
    from banked_image import emit
    original=read_build(base)
    mounts=validate_mounts([dict(alias='D1',unit=49,sectors=720,sector_bytes=size,profile=profile)])
    for source in base.iterdir():
        if source.is_file() and source.suffix not in ('.log','.atr') and source.name!='results.json':
            shutil.copyfile(source,out/source.name)
    shutil.copytree(base/'task-kernel',out/'task-kernel',dirs_exist_ok=True)
    p=read_build(out);image=p['image'];address=p['build']['task_storage']['BASE']+0x900
    segments=[s for s in image['segments'] if s['address']==address]
    require(len(segments)==1,'Missing mount descriptor')
    encoded=encode(mounts)
    require(len(encoded)==len(segments[0]['bytes']),'Variant changes descriptor extent')
    segments[0]['bytes']=list(encoded)
    (out/'program.a816.json').write_text(json.dumps(image,indent=2)+'\n')
    payload,labels=emit(out,image,p['build']['memory'],p['labels'])
    (out/'program.xex').write_bytes(payload)
    record=p['build'];record.update(dos_mounts=mounts,image_sha256=sha256(out/'program.a816.json'),
        xex_sha256=sha256(out/'program.xex'),manifest_sha256=sha256(out/'manifest.bin'),
        configuration_variant=dict(base_image_sha256=original['build']['image_sha256'],
            base_xex_sha256=original['build']['xex_sha256'],change='Only the serialized DOS mount descriptor; emitted routines/providers are identical'))
    for name in record['generated_sha256']:
        if (out/name).exists():record['generated_sha256'][name]=sha256(out/name)
    (out/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    return read_build(out)


def instrument(out):
    for name in ('o65integration.act','o65control.act','o65_integrated.act'):
        (out/name).write_text(read_source(ROOT/'tests/programs'/name))
    replacements = {
        'programfile.act': [('USE EXEC','USE EXEC\nUSE O65INTEGRATION'),
            ('bytes=EXEC.AllocMem(', 'bytes=O65INTEGRATION.Stage('),
            ('ELSE\n              position==+count\n            FI','ELSE position==+count O65INTEGRATION.Chunk(position) FI')],
        'o65memory.act': [('USE EXEC','USE EXEC\nUSE O65CONTROL'),
            ('RETURN(EXEC.AllocMem', '  O65CONTROL.allocations==+1\n  IF O65CONTROL.failAt<>0 AND O65CONTROL.allocations=O65CONTROL.failAt THEN RETURN(BYTE POINTER(0)) FI\nRETURN(EXEC.AllocMem')],
        'process.act': [('USE EXEC','USE EXEC\nUSE O65INTEGRATION'),
            ('RETURN(image.entry())', '  O65INTEGRATION.Enter(process)\n\nRETURN(image.entry())'),
            ('    PROGRAMIMAGE.Detach(PROGRAMIMAGE.Image POINTER(process.image))',
             '    O65INTEGRATION.Retire(process)\n    PROGRAMIMAGE.Detach(PROGRAMIMAGE.Image POINTER(process.image))')],
    }
    for name, edits in replacements.items():
        source=read_source(ROOT/'lib/dos'/name)
        for old,new in edits:
            require(source.count(old)==1,'Stale observation: '+name+' '+old)
            source=source.replace(old,new)
        (out/name).write_text(source)
    return {name:sha256(out/name) for name in [*replacements,'o65integration.act','o65control.act','o65_integrated.act']}


def media(toolchain,out,mode,size):
    source=out/'files';source.mkdir(exist_ok=True)
    commands={}
    for name,path in [('HELLO','examples/commands/hello.act'),('WAIT','tests/programs/disk_wait.act'),
                      ('READ','tests/programs/disk_read.act'),('READER','tests/programs/disk_reader_hold.act')]:
        commands[name]=compile_command(toolchain,ROOT/path,source/name,mode=='opt')
        (source/(name+'.options.json')).rename(out/(name+'.options.json'))
        (source/(name+'.profile.json')).rename(out/(name+'.profile.json'))
    length=777 if size==128 else 70003
    (source/'DATA.BIN').write_bytes(bytes((i & 255)^83 for i in range(length)))
    files=make(out/'volume.atr',source,binary_names={*commands,'DATA.BIN'},sector_bytes=size)
    return commands,length,{name:len(payload) for name,payload in files.items()}


def run_case(p,out,size,profile,length,trace,timing_only=False):
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p['output']/'manifest.bin',out/'manifest.bin')
    for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS','EXEC816_SIO_FAULT_FILE'):
        os.environ.pop(key,None)
    names=('native_nmi','native_irq','sio_start','sio_retire','sio_shutdown','signal_post','sio_alarm','sio_watchdog','tasks_forbid','tasks_permit')
    marks={name:p['labels'][name] for name in names}
    marks['sector_end']=sector_end_marker(p)
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
    volume=p['output']/'volume.atr';digest=sha256(volume)
    def at(module,name):return next(d['address'] for d in p['image']['data'] if f'_{module}_{name.upper()}_' in d['name'])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for name,value in PIN['configuration'].items():b.config(name,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu',{1:'fastest',2:'810',4:'generic56k'}[profile]);b.mount(0,str(volume))
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            b.poke(at('O65INTEGRATION','timingOnly'),int(timing_only))
            value=at('O65INTEGRATED','expectedBytes')
            for i,byte in enumerate(length.to_bytes(4,'little')):b.poke(value+i,byte)
            condition=f'db(${at("O65INTEGRATION","phase"):x})=1'
            b.bp_set(p['labels']['native_nmi'],condition=condition)
            run_to(b,p['labels']['native_nmi'],12000,240,condition)
            b.bp_clear_all()
            if trace:b.profile_start()
            b.poke(at('O65INTEGRATION','gate'),1)
        try:runtime,_=execute(b,{**p,'output':out},before_run=before,timeout=1800,frame_limit=90000)
        except Exception:
            selected=dict(p['image'],data=[d for d in p['image']['data'] if '_O65INTEGRATION_' in d['name']])
            print({name:data(b,selected,name) for name in ('checks','entered','retired','peak','phase')},flush=True)
            raise
        if trace:b.profile_stop()
        require(data(b,p['image'],'finished')==[1],'Integration did not finish')
        ownership(b,p,out)
        selected=dict(p['image'],data=[d for d in p['image']['data'] if '_O65INTEGRATION_' in d['name']])
        entered=int.from_bytes(bytes(data(b,selected,'entered')),'little')
        require(data(b,selected,'peak')==[8],'Missing full-capacity loaded command')
        require(int.from_bytes(bytes(data(b,selected,'retired')),'little')==entered,'Missing Image retirement')
        checks=int.from_bytes(bytes(data(b,selected,'checks')),'little')
        placements=bytes(data(b,selected,'placements'))[:entered*22]
        rows=[dict(text=int.from_bytes(placements[i:i+4],'little'),data=int.from_bytes(placements[i+4:i+8],'little'),
                   bss=int.from_bytes(placements[i+8:i+12],'little'),backing=int.from_bytes(placements[i+12:i+16],'little'),
                   backing_bytes=int.from_bytes(placements[i+16:i+20],'little'),live=placements[i+20],slot=placements[i+21]) for i in range(0,len(placements),22)]
        require(sha256(volume)==digest,'Read-only command media changed')
    result=dict(status='pass',runtime=runtime,machine=machine,placements=rows,processes=entered,
                checks=checks,
                media_sha256=digest,trace=trace,timing_only=timing_only)
    if trace:
        with (out/'emulator.log').open() as source,(out/'trace.log').open('w') as target:
            for line in source:
                if '[SIOPOC] ' in line or '[SIOTXN] ' in line:target.write(line)
        result['timing']=analyze(out/'trace.log',marks,volume,size,int(profile==2),None,key_count=None,divisor={1:0,2:40,4:8}[profile])
        require(result['timing']['verdict']=='pass','Integrated SIO timing gate failed: '+str(result['timing']['violations']))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--size',type=int,choices=(128,256),default=128)
    parser.add_argument('--profile',type=int,choices=(1,2,4),default=1)
    parser.add_argument('--bank',type=int,choices=(2,3),default=2)
    parser.add_argument('--trace',action='store_true')
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--from-build',type=Path,help='Repackage frozen machine code with another mount geometry/profile')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(ROOT/'build/actionc');observers=instrument(out)
    commands,length,files=media(toolchain,out,args.case,args.size)
    p=transport_variant(args.from_build.resolve(),out,args.size,args.profile) if args.from_build else read_build(out) if args.reuse else build(toolchain,out/'o65_integrated.act',out,optimize=args.case=='opt',tasks=True,task_capacity=8,console=True,kernel_bank=args.bank,
        system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=args.size,profile=args.profile)])
    require(p['build']['optimize']==(args.case=='opt') and p['build']['memory']['constants']['KERNEL_BANK']==args.bank,'Replay mode/bank mismatch')
    first=run_case(p,out/'observed' if args.trace else out/'run',args.size,args.profile,length,args.trace,args.trace)
    result=dict(status='pass',mode=args.case,sector_bytes=args.size,profile=args.profile,kernel_bank=args.bank,
                build=p['build'],commands=commands,files=files,observers=observers,pin=PIN,cases=[first],bank_zero_delta=dict(fixed=0,per_task=0))
    if args.trace:
        result['cases'].append(run_case(p,out/'replay',args.size,args.profile,length,False,True))
        result['cases'].append(run_case(p,out/'functional',args.size,args.profile,length,False,False))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Integrated disk commands passed',args.case,args.size,args.profile,args.bank,flush=True)
