"""Real D8 short-frame failure, queued D1 work, software cleanup and reset latch."""
import argparse,json,os,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator,run_to
from test_sio_device import PIN
from test_cooperative import data
from test_dos_stack import execute
from banked_test_memory import read

def run(t,out,mode):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);old=sha256(media)
    selector=out/'fault.txt';selector.write_text('none\n');os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    pin=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text());binary=ROOT/'build/altirra-sio-sector-faults'
    require(sha256(binary/'AltirraBridgeServer')==pin['fault_responder']['binary_sha256'],'Unpinned responder')
    paths=bytearray(96)
    for i,name in enumerate(('D8:TOOLS/SUB/DATA.BIN','D1:TOOLS/SUB/DATA.BIN','D1:')):paths[32*i:32*i+len(name)+1]=name.encode()+b'\0'
    p=build(t,ROOT/'tests/programs/dos_offline.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,dos_mounts=[dict(alias='D8',unit=56,sectors=720,sector_bytes=128),dict(alias='D1',unit=49,sectors=720,sector_bytes=128)],image_data=[(0xd1000,bytes(paths))])
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin);b.config('diskemu','fastest');b.mount(0,str(media));b.mount(7,str(media))
        snapshot={}
        def before(b):
            flag=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_DOSOFFLINETEST_GO_'))
            marker=p['labels']['native_cop'];condition=f'db(${flag:x})=1'
            b.bp_set(marker,condition=condition)
            run_to(b,marker,timeout=240,frame_limit=12000,condition=condition);b.bp_clear_all()
            # Descriptor lies in upper RAM. Never invoke the far helper during
            # native execution; only change the host peripheral fault selector.
            selector.write_text('short\n')
            print('Fault armed',flush=True)
        try:runtime,_=execute(b,p,before_run=before,expected_status=0xff93,timeout=600,frame_limit=30000)
        except Exception:
            print('native state',b.memdump(0x2000,64).hex(),'checks',data(b,p['image'],'checks',True),flush=True)
            for i,pool in enumerate(p['build']['memory']['task_pools']):(out/f'fault-stack-{i}.bin').write_bytes(b.memdump(pool['stack_base'],pool.get('stack_bytes',1536)))
            raise
        hardware=read(b,p['build']['task_storage']['BASE']+0x800,128,out)
        require(hardware[0]==hardware[45]==1,'Reset latch lost')
        require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained caller buffer')
        require(sha256(media)==old,'Media changed')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),hardware=hardware.hex(),media_sha256=old,emulator_sha256=sha256(binary/'AltirraBridgeServer'),fault='short')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS offline passed',args.case,flush=True)
