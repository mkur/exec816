#!/usr/bin/env python3
"""Focused emitted DOS ASSIGN registry and path resolution on MyDOS."""
import argparse
import json
import shutil
from pathlib import Path

from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(output,mode):
    output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(ROOT/'build/actionc')
    source=ROOT/'tests/fixtures/mydos/mydos450-128.atr'
    media=output/'volume.atr'
    shutil.copyfile(source,media)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    memory_profile=output/'memory-profile.json'
    memory_profile.write_text(json.dumps(profile,indent=2)+'\n')
    program=build(toolchain,ROOT/'tests/programs/dos_assign.act',output,
                  optimize=mode=='opt',tasks=True,task_capacity=8,console=True,
                  dos_mounts=[dict(alias='D1',unit=49,sectors=720,
                                   sector_bytes=128,profile=1)],
                  memory_profile=memory_profile)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',
                  output,pin=PIN) as bridge:
        for key,value in PIN['configuration'].items():
            bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
        bridge.config('diskemu','fastest')
        bridge.mount(0,str(media))
        runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
        ownership(bridge,program,output)
        observations=dict(checks=data(bridge,program['image'],'checks',True),
                          finished=data(bridge,program['image'],'finished'))
        require(observations['finished']==[1],'ASSIGN fixture did not finish')
        require(sha256(media)==sha256(source),'Read-only fixture changed')
    return dict(status='pass',mode=mode,build=program['build'],runtime=runtime,
                machine=machine,observations=observations,
                fixture_sha256=sha256(source),media_sha256=sha256(media))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.output,args.case)
    result.update(tier='development',runner_sha256=sha256(Path(__file__)))
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ASSIGN DOS checks passed',args.case,flush=True)
