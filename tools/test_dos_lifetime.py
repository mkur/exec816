"""Private mount control and last-application shutdown over real SIO."""
import adapter_state as adapter
import argparse,json,shutil
from library_paths import library_file, read_source
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership

def run(t,out,mode,auto=False,retry=False):
    out.mkdir(parents=True,exist_ok=True)
    overrides={}
    if retry:
        text=read_source(library_file('blockwire.act')).replace('USE EXEC\n','USE EXEC\nUSE DOSFAULTCONTROL\n',1)
        old='  error=INT(CARD(state))'
        require(text.count(old)==1,'Stale mount retry completion hook')
        text=text.replace(old,old+'\n  IF error=0 AND DOSFAULTCONTROL.failNext<>0 THEN\n    DOSFAULTCONTROL.failNext=0\n    request.io_Error=4\n    request.io_Actual=0\n    error=4\n  FI')
        module=out/'blockwire.act';module.write_text(text)
        overrides[module.name]=sha256(module)
    images=[]
    for unit in range(2):
        p=out/f'volume{unit}.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',p);images.append((p,sha256(p)))
    paths=bytearray(96)
    for i,path in enumerate(('D1:TOOLS/SUB/DATA.BIN','D2:TOOLS/SUB/DATA.BIN','D1:')):
        v=path.encode()+b'\0';paths[32*i:32*i+len(v)]=v
    mounts=[dict(alias='D'+str(i+1),unit=49+i,sectors=720,sector_bytes=128) for i in range(2)]
    p=build(t,ROOT/('tests/programs/dos_mount_retry.act' if retry else 'tests/programs/dos_service_lifetime.act'),out,optimize=mode=='opt',tasks=True,task_capacity=8,dos_mounts=mounts,image_data=[(0xd1000,bytes(paths))])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest')
        for i,(path,_) in enumerate(images):b.mount(i,str(path))
        def before_run(b):
            if not retry:b.poke(next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSLIFETEST_AUTOSTOP_')),int(auto))
        try:runtime,_=execute(b,p,before_run=before_run,timeout=600,frame_limit=30000)
        except Exception:
            print('native state',b.memdump(adapter.STATE,64).hex(),'checks',data(b,p['image'],'checks',True),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        ownership(b,p,out)
        require(all(sha256(path)==old for path,old in images),'Media changed')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),auto_stop=auto,retry=retry,overrides=overrides,media=[s for _,s in images])
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--auto',action='store_true');a.add_argument('--retry',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.auto,args.retry)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS lifetime passed',args.case,args.auto,flush=True)
