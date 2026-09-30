#!/usr/bin/env python3
"""Ordinary DOS packaging, explicit mounts, examples and allocation-free IoErr."""
import argparse,json,shutil
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_sio_device import PIN
from test_cooperative import data

def run(t,out,mode,name):
    source=ROOT/('tests/programs/dos_no_mounts.act' if name=='empty' else f'examples/dos-{name}.act')
    mounts=[] if name=='empty' else [dict(alias='D1',unit=49,sectors=720,sector_bytes=128)]
    p=build(t,source,out,tasks=True,task_capacity=8,optimize=mode=='opt',dos_mounts=mounts)
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);old=sha256(media)
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        runtime,_=execute(b,p,timeout=600,frame_limit=30000);ownership(b,p,out)
        if name=='empty':require(runtime['created']==0 and data(b,p['image'],'checks',True)==[4],'Unexpected eager service/allocation')
        else:
            observed={d['name']:list(b.memdump(d['address'],d['size'])) for d in p['image']['data'] if d['name'].startswith('M_DOSREAD_') or d['name'].startswith('M_DOSDIRECTORY_')}
            (out/'observed.json').write_text(json.dumps(dict(observed=observed,runtime=runtime),indent=2)+'\n')
            require(data(b,p['image'],'completed')==[1] and runtime['created']==2,'Example failed: '+str(observed)+' created='+str(runtime['created']))
        require(sha256(media)==old,'Media changed')
        return dict(status='pass',name=name,build=p['build'],runtime=runtime,machine=machine,media_sha256=old)
if __name__=='__main__':
    from pathlib import Path
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--name',choices=('empty','read','directory'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.name)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Ordinary DOS passed',args.case,args.name,flush=True)
