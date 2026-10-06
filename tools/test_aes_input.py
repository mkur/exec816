#!/usr/bin/env python3
"""Small raw/optimized emitted regression for deferred pointer ownership."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_mouse_observe import BRIDGE,ROM,PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',qualification=False,cases={})
    for mode in ('raw','opt'):
        target=out/mode
        p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/aes_input.act',target,
            tasks=True,task_capacity=8,optimize=mode=='opt')
        with emulator(BRIDGE,ROM,target,pin=PIN) as b:
            row=dict(build=p['build'],machine=verify_machine(b,ROM,PIN))
            row['runtime'],_=execute(b,p,timeout=60,frame_limit=2000)
            ownership(b,p,p['output'])
            row['checks']=data(b,p['image'],'checks',True)[0]
            row['service_bytes']=data(b,p['image'],'serviceBytes',True)[0]
            require(row['checks']==31,'Incomplete pointer checks')
            report['cases'][mode]=row
    report['status']='pass'
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Deferred AES pointer: raw and optimized pass')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
