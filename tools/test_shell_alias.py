#!/usr/bin/env python3
"""Focused emitted-code checks for bounded resident shell alias expansion."""
import argparse
import json
from pathlib import Path

from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(output,mode):
    output.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    memory=output/'memory-profile.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc'),
                  ROOT/'tests/programs/shell_alias.act',output,
                  optimize=mode=='opt',tasks=True,task_capacity=8,
                  console=True,dos_mounts=[],memory_profile=memory)
    bridge_dir=ROOT/'build/shell-paced-bridge'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
        for key,value in PIN['configuration'].items():
            bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(bridge,rom,PIN)
        runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
        ownership(bridge,program,output)
        observations=dict(checks=data(bridge,program['image'],'checks',True),
                          finished=data(bridge,program['image'],'finished'))
        require(observations['finished']==[1],'Alias fixture did not finish')
    return dict(status='pass',tier='development',mode=mode,
                build=program['build'],machine=machine,runtime=runtime,
                observations=observations,runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.output.resolve(),args.case)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Shell alias checks passed',args.case,flush=True)
