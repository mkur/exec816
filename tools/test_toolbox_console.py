#!/usr/bin/env python3
"""Foreground console identity/geometry with redirected streams and real DOS I/O."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from stack_budget import stack_usage

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/toolbox_console.act'
    p=build(compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',tasks=True,task_capacity=8,console=True)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=180,frame_limit=9000)
        except Exception:
            print('Console check:',data(b,p['image'],'checks',True),flush=True)
            raise
        require(data(b,p['image'],'finished')==[1],'Console checks incomplete')
        ownership(b,p,out)
        stacks=stack_usage(b,p['build']['memory'])
        checks=data(b,p['image'],'checks',True)[0]
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],runtime=runtime,machine=machine,
                stacks=stacks,bank_zero_delta=dict(fixed=0,per_task=0),source_inputs={str(source.relative_to(ROOT)):sha256(source)})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.output.resolve(),args.case)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console support passed:',args.case,result['checks'])
