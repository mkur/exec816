#!/usr/bin/env python3
"""Read short boot and full double-density sectors through real queued SIO."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256
from os_boundary import emulator
from sector_images import disk_image
from test_sio_device import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership

def run(t,out,optimize,profile=1):
    require(profile in (1,4),'Unsupported sector probe profile')
    p=build(t,ROOT/'tests/programs/sio_sectors.act',out,optimize=optimize,tasks=True,
            image_data=[(0xaffd0,bytes([0xa5])*320)])
    disk=out/'sectors.atr';disk_image(disk,256,65535)
    initial=sha256(disk)
    binary=ROOT/'build/altirra-sio-multi'
    require(sha256(binary/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        diskemu='generic56k' if profile==4 else 'fastest'
        for k,v in {**PIN['configuration'],'diskemu':diskemu}.items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            b.mount(0,str(disk))
            b.poke(next(d['address'] for d in p['image']['data'] if '_PROFILE_' in d['name']),profile)
        try:runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('checks',data(b,p['image'],'checks',True),flush=True);raise
        clean_ownership(b,p,out)
        buf=far_read(b,0xaffd0,320,out)
        require(buf[:32]==buf[-32:]==bytes([0xa5])*32,'Sector buffer guard changed')
        hardware=far_read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        require(int.from_bytes(hardware[56:58],'little')==8,'Rejected request reached wire')
        require(hardware[5]==(8 if profile==4 else 0),'Wrong serial clock divisor')
        require(hardware[0]==hardware[1]==0 and hardware[12:15]==hardware[16:19]==bytes(3),'Hardware retained ownership')
        require(sha256(disk)==initial,'Read modified media')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,
                    checks=data(b,p['image'],'checks',True),hardware=hardware.hex(),
                    media_sha256=initial,sectors=[1,2,3,4,720,1024,32768,65535],sector_bytes=256,profile=profile,diskemu=diskemu)

def suite(t,out,optimize):
    from sio_sector_record import snapshot_inputs,validate_current_inputs
    from test_sio_concurrent import run as concurrent
    from test_sio_recovery import run as recovery
    from test_sio_device import run as regression
    inputs=snapshot_inputs(ROOT)
    cases=[]
    def execute_case(name,fn):
        directory=out/name;directory.mkdir(parents=True,exist_ok=True)
        print('Sector suite:',name,flush=True)
        result=fn(directory);result['name']=name;cases.append(result)
        (directory/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    execute_case('boundaries',lambda d:run(t,d,optimize))
    for capacity in (4,8):
        execute_case(f'concurrent-{capacity}',lambda d:concurrent(t,d,optimize,capacity,0,1,True,key=True,sector_size=256))
    execute_case('recovery',lambda d:recovery(t,d,optimize,
        ['queued','preparing','active','terminal','absent','checksum','short','extra'],sector_size=256))
    # Each harness sets its observer environment explicitly. These functional
    # regression runs use ordinary pinned binaries, without inherited tracing.
    import os
    for k in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(k,None)
    for speed in (0,1,2):
        execute_case(f'regression-{speed}',lambda d:regression(t,d,optimize,speed))
    result=dict(status='pass',optimize=optimize,cases=cases,inputs=inputs)
    validate_current_inputs(result,ROOT)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--suite',action='store_true')
    a.add_argument('--profile',type=int,choices=(1,4),default=1)
    a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result={'status':'running'}
    try:
        require(not args.suite or args.profile==1,'Suite selects its own profiles')
        result=suite(compiler(args.compiler_dir),out,args.case=='opt') if args.suite else run(compiler(args.compiler_dir),out,args.case=='opt',args.profile)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SIO sector boundaries passed',args.case)
