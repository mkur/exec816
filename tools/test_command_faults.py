#!/usr/bin/env python3
"""Real DOS formatter, printing and headless argument-help contracts."""
import argparse
import json
from pathlib import Path

from generate_program import fault_messages
from library_paths import read_source
from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from stack_budget import stack_usage
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    calls=['PROC Cases()','']
    for code,text in sorted(fault_messages().items()):
        calls.append(f'  Case({code},c"TEST: {text} ({code})")')
    (out/'fault-cases.inc').write_text('\n'.join(calls)+'\n\nRETURN\n')
    source=out/'command_faults.act'
    source.write_text(read_source(ROOT/'tests/programs/command_faults.act'))
    # Expected strings for every message live beside the resident table in this
    # fixture only. Production keeps its unchanged upper-RAM data reservation.
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    (out/'profile.json').write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc'),source,out,optimize=mode=='opt',tasks=True,
            task_capacity=8,console=True,memory_profile=out/'profile.json')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=180,frame_limit=9000)
        except Exception:
            print('Fault check:',data(b,p['image'],'checks',True),flush=True)
            raise
        require(data(b,p['image'],'finished')==[1],'Fault checks incomplete')
        ownership(b,p,out)
        stacks=stack_usage(b,p['build']['memory'])
        checks=data(b,p['image'],'checks',True)[0]
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],
                runtime=runtime,machine=machine,stacks=stacks,runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();result=run(out,args.case)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Fault services passed:',args.case,result['checks'],flush=True)
