#!/usr/bin/env python3
"""Focused public DOS SDFS/MyDOS integration through real emulated SIO."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine,read_build
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out,mode,size,replay=False):
    paths=('D1:','D1:TOOLS/SUB','TEXT.TXT','/','//','D1:MANY','D1:BINARY.BIN','D2:TOOLS/SUB/DATA.BIN','D1:LARGE.BIN')
    names=b''.join(n.encode().ljust(32,b'\0') for n in paths)
    media=[]
    for index,relative in enumerate((f'sdfs/sdfs-21-{size}.atr','mydos/mydos450-128.atr')):
        source=ROOT/'tests/fixtures'/relative;target=out/f'volume{index}-{size}.atr';shutil.copyfile(source,target);media.append(target)
    mounts=[dict(alias='D1',unit=49,sectors=2000,sector_bytes=size,profile=4,format=2),dict(alias='D2',unit=50,sectors=720,sector_bytes=128,profile=4,format=1)]
    if replay:
        p=read_build(out)
        require(p['build']['optimize']==(mode=='opt'),'Replay optimization differs')
        require(p['build']['source_sha256']==sha256(ROOT/'tests/programs/sdfs_dos.act'),'Stale DOS source')
        require(all(sha256(ROOT/name)==digest for name,digest in p['build']['task_inputs'].items()),'Stale DOS implementation')
    else:
        p=build(t,ROOT/'tests/programs/sdfs_dos.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console_deferred=True,dos_mounts=mounts,
            image_data=[(0xd1000,names),(0xd2000,bytes(512)),(0xd3000,bytes(260)),(0xd3200,bytes(260)),(0xd5000,bytes(280))])
    hashes=[sha256(p) for p in media]
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','generic56k')
        for i,path in enumerate(media):b.mount(i,str(path.resolve()))
        def before_run(b):
            if p['build']['dos_mounts'][0]['sector_bytes']!=size:
                from banked_test_memory import write
                write(b,p['build']['task_storage']['BASE']+0x900+40,size.to_bytes(2,'little'),out)
        try:runtime,_=execute(b,p,before_run=before_run,timeout=300,frame_limit=15000)
        except Exception:
            print('SDFS DOS checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out);require(data(b,p['image'],'finished')==[1],'Incomplete SDFS DOS fixture')
        require([sha256(p) for p in media]==hashes,'Read-only media changed');checks=data(b,p['image'],'checks',True)
    return dict(status='pass',mode=mode,sector_bytes=size,build=p['build'],runtime=runtime,machine=machine,checks=checks,media=hashes,mounts=mounts,replay=replay,geometry_override=size if p['build']['dos_mounts'][0]['sector_bytes']!=size else None,scope='Real emulated SIO, GENERIC57600, mixed volumes; focused development evidence')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--size',type=int,choices=(128,256),required=True);parser.add_argument('--replay',action='store_true');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(compiler(ROOT/'build/actionc'),out,args.case,args.size,args.replay)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/f'results-{args.size}.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDFS DOS passed',args.case,args.size,flush=True)
