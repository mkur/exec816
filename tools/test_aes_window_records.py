#!/usr/bin/env python3
"""Target-emitted private window record, pointer-index and retirement checks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_mouse_observe import BRIDGE,ROM,PIN

def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    p=build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/aes_window_records.act',
            out,optimize=mode=='opt',tasks=True,task_capacity=12,console=False,dos_mounts=[])
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROM,PIN)
        runtime,_=execute(b,p)
        ownership(b,p,out)
        result=dict(status='pass',tier='development',qualification=False,mode=mode,
                    build=p['build'],machine=machine,runtime=runtime)
        for field in ('checks','windowBytes','serviceBytes'):result[field]=data(b,p['image'],field,True)[0]
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),required=True);args=a.parse_args()
    print(run(args.output.resolve(),args.mode)['checks'],'window record checks passed',args.mode,flush=True)
