#!/usr/bin/env python3
"""Process completion serviced during an outstanding DOS timer operation."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/process_wait.act',out,
            optimize=optimize,tasks=True,task_capacity=8,console=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        try:runtime,_=execute(b,p,timeout=180,frame_limit=9000)
        except Exception:
            print('checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        require(data(b,p['image'],'collected')==[1],'Child not collected during wait')
        record=dict(status='pass',tier='development',qualification=False,build=p['build'],runtime=runtime,
                    checks=data(b,p['image'],'checks',True),machine=machine)
        (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true');args=parser.parse_args()
    run(args.output.resolve(),not args.raw)
