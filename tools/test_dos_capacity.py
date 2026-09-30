"""Actual capacity pressure on FS admission and the dependent SIO admission."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership

def run(t,out,mode,count):
    out.mkdir(parents=True,exist_ok=True);media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);old=sha256(media)
    p=build(t,ROOT/'tests/programs/dos_capacity.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128)],image_data=[(0xd1000,b'D1:TOOLS/SUB/DATA.BIN\0')])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def before_run(b):
            for name,value,size in [('COUNT',count,1),('EXPECTED',103 if count==7 else -1,4)]:
                at=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSCAPTEST_'+name+'_'));b.memload(at,(value&((1<<(size*8))-1)).to_bytes(size,'little'))
        try:runtime,_=execute(b,p,before_run=before_run,timeout=240,frame_limit=12000)
        except Exception:
            print('native state',b.memdump(0x2000,64).hex(),'checks',data(b,p['image'],'checks',True),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        ownership(b,p,out);require(sha256(media)==old,'Media changed')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),application_children=count,media_sha256=old)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--children',type=int,choices=(6,7),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.children)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS capacity passed',args.case,args.children,flush=True)
