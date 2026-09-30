#!/usr/bin/env python3
"""Execute the queued SIO device using only caller-side public I/O operations."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256
from os_boundary import emulator
from sio_transactions import disk_image
PIN=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text())
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership
from ports_budget import current

def run(t,out,optimize,speed=0,trace=False):
    p=build(t,ROOT/'tests/programs/sio_queued.act',out,optimize=optimize,tasks=True,io_test_device=True,
        image_data=[(a,bytes([0xa5])*256) for a in (0x8ffa0,0xaffa0,0xcffa0)])
    for unit in (0,1):disk_image(out/f'disk{unit}.atr')
    binary=ROOT/('build/altirra-sio-multi-observer' if trace else 'build/altirra-sio-multi')/'AltirraBridgeServer'
    require(sha256(binary)==(PIN['observer']['binary_sha256'] if trace else PIN['emulator']['sha256']),'Unpinned queued-SIO emulator')
    if trace:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in p['labels'].items() if k.startswith(('sio_','native_'))))
    with emulator(ROOT/('build/altirra-sio-multi-observer' if trace else 'build/altirra-sio-multi'),ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as bridge:
        for k,v in PIN['configuration'].items():bridge.config(k,str(v).lower() if isinstance(v,bool) else v)
        bridge.config('diskemu',('fastest','810','happy1050','generic56k')[speed])
        machine=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            if trace:b.profile_start()
            for unit in (0,1):b.mount(unit,str(out/f'disk{unit}.atr'))
            b.config('diskemu',('fastest','810','happy1050','generic56k')[speed])
            address=next(d['address'] for d in p['image']['data'] if '_SPEED_' in d['name'])
            b.poke(address,speed)
        try:runtime,_=execute(bridge,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('checks',data(bridge,p['image'],'checks',True),flush=True)
            first=int.from_bytes(data(bridge,p['image'],'first'), 'little')
            for address in (first,0xafff0,p['build']['task_storage']['BASE']+0x800):
                print(hex(address),far_read(bridge,address,64,out).hex(),flush=True)
            raise
        if trace:bridge.profile_stop()
        observed={n:data(bridge,p['image'],n,True) for n in ('checks','progress')}
        clean_ownership(bridge,p,out)
        hardware=far_read(bridge,p['build']['task_storage']['BASE']+0x800,128,out)
        require(hardware[0]==hardware[1]==0,'Hardware remained owned')
        require(int.from_bytes(hardware[56:58],'little')==(1 if speed==2 else 4),'Wrong terminal notification count')
        require(hardware[5]==(8 if speed==3 else 40 if speed else 0),'Wrong serial clock divisor')
        return dict(status='pass',name=('target','stock','happy','generic57600')[speed]+('-opt' if optimize else '-raw'),
            build=p['build'],runtime=runtime,observed=observed,machine=machine,hardware=hardware.hex())

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--trace',action='store_true');p.add_argument('--speed',type=int,choices=(0,1,2,3),default=0);p.add_argument('--output',type=Path,default=ROOT/'build/sio-device')
    p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running',bank_zero=current(),cases=[])
    try:
        result['cases'].append(run(compiler(a.compiler_dir),out/a.case,a.case=='opt',a.speed,a.trace))
        result['status']='pass'
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Passed queued SIO',a.case,a.speed,flush=True)
if __name__=='__main__':main()
