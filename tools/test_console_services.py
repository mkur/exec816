#!/usr/bin/env python3
"""Console/SIO claim orders, three-service retirement, and unsafe bus fail-stop."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,sha256
from os_boundary import emulator
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from sector_images import disk_image
from banked_test_memory import read

def run(t,out,mode,optimize):
    out.mkdir(parents=True,exist_ok=True)
    offline=mode==5
    source=ROOT/('tests/programs/sio_recovery.act' if offline else 'tests/programs/native_console_services.act')
    mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128)] if mode==4 else []
    p=build(t,source,out,optimize=optimize,tasks=True,task_capacity=8,console=True,io_test_device=offline,dos_mounts=mounts,image_data=[(0xd1000,b'D1:TOOLS/SUB/DATA.BIN\0')])
    media=out/'volume.atr'
    if mode==4:shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    else:disk_image(media,128)
    media_hash=sha256(media)
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console emulator')
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.mount(0,str(media))
        saved={}
        def before(b):
            saved.update(screen_at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16),key=b.memdump(520,2),brk=b.memdump(566,2))
            saved['screen']=b.memdump(saved['screen_at'],960)
            values=dict(kind=6,unit=56,expected=1,offlineExpected=1) if offline else dict(mode=mode)
            for name,value in values.items():
                b.poke(next(x['address'] for x in p['image']['data'] if '_'+name.upper()+'_' in x['name']),value)
            if offline:
                at=next(x['address'] for x in p['image']['data'] if '_SECTORSIZE_' in x['name']);b.poke(at,128);b.poke(at+1,0)
        try:rt,_=execute(b,p,before_run=before,expected_status=0xff93 if offline else 0,timeout=300,frame_limit=15000)
        except Exception:
            print('Checks',data(b,p['image'],'checks',True),flush=True);raise
        require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        hardware=read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        if offline:
            require(data(b,p['image'],'cleanupReached')==[1],'Failed before cleanup checkpoint')
            require(hardware[0]==hardware[45]==1 and hardware[12:15]==hardware[16:19]==bytes(3),'Unsafe SIO ownership/pointers')
            # These bytes remain in admitted upper RAM while unsafe finish parks.
            storage=p['build']['memory']['console_storage']
            require(read(b,storage['CAPTURE'],1,out)==b'\1','Unsafe finish released keyboard')
            require(read(b,storage['PRESENTATION']+26,1,out)==b'\1','Unsafe finish released display')
            require(b.peek(752)==b'\1','Unsafe finish restored ROM cursor')
            c=p['build']['memory']['constants'];seed=(out/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
            require(read(b,c['TABLE'],c['TABLE_BYTES'],out)!=seed,'Unsafe finish released heap ownership')
            require(read(b,storage['BASE']+104,3,out)!=bytes(3),'Unsafe finish discarded display snapshot')
        else:
            require(data(b,p['image'],'checkpoint')==[1],'Missing completed-client checkpoint')
            require(hardware[0]==0,'SIO remained owned')
            require(b.memdump(saved['screen_at'],960)==saved['screen'],'Screen not restored')
            require(b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'] and b.memdump(520,2)==saved['key'] and b.memdump(566,2)==saved['brk'],'Shared hardware not restored')
            ownership(b,p,out)
        require(sha256(media)==media_hash,'Media changed')
        return dict(status='pass',mode=mode,build=p['build'],runtime=rt,machine=machine,media_sha256=media_hash,checks=data(b,p['image'],'checks',True),cleanup_reached=True,hardware=hardware.hex())
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--mode',type=int,choices=range(6),required=True);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.mode,args.case=='opt')
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Services passed',args.mode,args.case,flush=True)
