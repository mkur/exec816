#!/usr/bin/env python3
"""Emitted decoder boundary tests; separate from real-controller acceptance."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine,read_build
from os_boundary import emulator
from test_mouse_observe import PIN,BRIDGE,ROM
from test_heap_api import clean_ownership
from stack_budget import stack_usage

def run(out,mode,replay=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    r=dict(status='running',tier='development',slice='M5',mode=mode)
    try:
        p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/pointer_failures.act',out/'program',
                optimize=mode=='opt',tasks=True,task_capacity=8,irq_probe=12,console=False)
        at=lambda name:next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_POINTERFAIL_'+name.upper()+'_'))
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            r['machine']=verify_machine(b,ROM,PIN)
            try:runtime,_=execute(b,p,timeout=80,frame_limit=3000)
            finally:r.update(checks=b.peek16(at('checks')),tags=b.memdump(at('tag'),8).hex(),source=b.memdump(0x3f4680,144).hex(),event=b.memdump(at('event'),24).hex(),capture=b.memdump(p['build']['memory']['input_storage']['POINTER_CAPTURE'],p['build']['memory']['input_storage']['POINTER_CAPTURE_BYTES']).hex())
            clean_ownership(b,p,p['output'])
            storage=p['build']['memory']['input_storage'];n=storage['POINTER_GUARD_BYTES']
            for address in (storage['POINTER_RESERVE'],storage['POINTER_CAPTURE']+storage['POINTER_CAPTURE_BYTES']):
                require(b.memdump(address,n)==bytes([0xa5])*n,'Pointer guard')
            r.update(runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']))
        r.update(status='pass',build=p['build'],xex_sha256=sha256(p['xex']),pin=PIN,
                 bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Pointer failures passed',mode,r['checks'],flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--mode',choices=['raw','opt'],required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--replay',action='store_true');a=ap.parse_args();run(a.output,a.mode,a.replay)
