"""Opt-in filesystem worker: public file calls over real queued SIO."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,execute,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
from test_dos_stack import execute as stack_execute,ownership as far_ownership

def run(t,out,mode,size,capacity=4,concurrent=False,fault=None):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'volume.atr';shutil.copyfile(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr',media);before=sha256(media)
    paths=bytearray(128)
    for at,value in ((0,b'D1:TOOLS/SUB/DATA.BIN\0'),(32,b'D1:MISSING\0'),(48,b'D1:TOOLS\0')):paths[at:at+len(value)]=value
    mounts=[dict(alias='D1',unit=49,sectors=720 if size==128 else 2000,sector_bytes=size)]
    source=ROOT/'tests/programs/dos_files.act'
    if fault:
        source=out/'dos_files_fault.act'
        source.write_text((ROOT/'tests/programs/dos_files_fault.act').read_text().replace('  expected=4','  expected='+('4' if fault=='checksum' else '-4')))
        mutation='request.io_Error=4 request.io_Actual=0 error=4' if fault=='checksum' else 'request.io_Actual==-1'
        (out/'blockwire.act').write_text('MODULE BLOCKWIRE\nUSE EXEC\nPUBLIC INT FUNC Transfer(EXEC.IOSIOReq POINTER request)\n INT error\n error=EXEC.DoIO(EXEC.IORequest POINTER(request))\n IF error=0 AND request.sio_Aux1=5 AND request.sio_Aux2=0 THEN '+mutation+' FI\n\nRETURN(error)\n\nENDMODULE\n')
    p=build(t,source,out,optimize=mode=='opt',tasks=True,dos_mounts=mounts,task_capacity=capacity,image_data=[(0xd1000,bytes(paths)),(0xcffd0,bytes([165])*32+bytes(800)+bytes([165])*32),(0xe0000,bytes(32))])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media))
        def before_run(b):
            address=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSFILETEST_CONCURRENT_'))
            b.poke(address,int(concurrent))
        try:runtime,_=stack_execute(b,p,before_run=before_run,timeout=240,frame_limit=12000)
        except Exception:
            for i,pool in enumerate(p['build']['memory']['task_pools']):
                (out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            if fault:print('read result',data(b,p['image'],'got',True),'IoErr',data(b,p['image'],'lastError',True),'expected',data(b,p['image'],'expected',True),flush=True)
            print('checks',data(b,p['image'],'checks',True),flush=True);raise
        if capacity==8:far_ownership(b,p,out)
        else:clean_ownership(b,p,out)
        require(sha256(media)==before,'Unexpected media mutation')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),media_sha256=before,sector_bytes=size,concurrent=concurrent,other_checks=data(b,p['image'],'otherChecks',True),computations=data(b,p['image'],'computations',True),io_progress=data(b,p['image'],'ioProgress',True),fault=fault,override_sha256=sha256(out/'blockwire.act') if fault else None)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--size',type=int,choices=(128,256),required=True);p.add_argument('--fault',choices=('checksum','short'));p.add_argument('--concurrent',action='store_true');p.add_argument('--capacity',type=int,default=4);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,a.case,a.size,a.capacity,a.concurrent,a.fault)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS files passed',a.case,a.size,a.capacity,flush=True)
