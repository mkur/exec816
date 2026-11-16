#!/usr/bin/env python3
"""Emitted raw hit snapshots and scene/UPDATE-independent caller queries."""
import argparse
import json
from pathlib import Path
from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=16384
    memory=out/'fixture-memory.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/aes_find.act',out/'program',
        tasks=True,task_capacity=8,optimize=True,memory_profile=memory,
        console=False,console_deferred=True)
    with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        runtime,_=execute(bridge,program,frame_limit=600,timeout=60)
        ownership(bridge,program,program['output'])
        checks=data(bridge,program['image'],'checks',True)[0]
        require(checks==110,'Incomplete committed hit checks: '+str(checks))
    report=dict(status='pass',tier='development',qualification=False,mode='opt',
        checks=checks,machine=machine,runtime=runtime,build=program['build'])
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Committed hit checks passed:',checks,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
