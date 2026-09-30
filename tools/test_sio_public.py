#!/usr/bin/env python3
"""Run the read-only example with ordinary resident registration."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require
from os_boundary import emulator
from test_sio_device import PIN
from sio_transactions import disk_image
from test_cooperative import data
from test_heap_api import clean_ownership

def main():
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),default='opt');a.add_argument('--output',type=Path,default=ROOT/'build/sio-public');args=a.parse_args()
    out=args.output.resolve();p=build(compiler(ROOT/'build/actionc'),ROOT/'examples/device-io.act',out,tasks=True,optimize=args.case=='opt')
    disk_image(out/'disk.atr')
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest')
        runtime,_=execute(b,p,before_run=lambda b:b.mount(0,str(out/'disk.atr')),timeout=240,frame_limit=12000)
        observed={n:data(b,p['image'],n,n=='ioError') for n in ('completed','ioError')}
        require(observed['completed']==[1],'Public example failed: '+str(observed))
        clean_ownership(b,p,out)
        (out/'results.json').write_text(json.dumps(dict(status='pass',build=p['build'],runtime=runtime,observed=observed),indent=2)+'\n')
    print('Public example passed',args.case,flush=True)
if __name__=='__main__':main()
