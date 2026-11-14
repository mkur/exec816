#!/usr/bin/env python3
"""Small emitted cursor-policy counter, failure and private-layout checks."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from generate_memory import PROFILE


def run(out,mode,routing=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=16384 if routing else 8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),
        ROOT/('tests/programs/aes_cursor_route.act' if routing else 'tests/programs/aes_cursor_policy.act'),out/'program',
        tasks=True,task_capacity=8,optimize=mode=='opt',memory_profile=memory)
    with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        runtime,_=execute(bridge,program,frame_limit=600,timeout=60)
        ownership(bridge,program,program['output'])
        checks=data(bridge,program['image'],'checks',True)[0]
        require(checks==(22 if routing else 52),'Incomplete cursor policy checks: '+str(checks))
    report=dict(status='pass',tier='development',qualification=False,mode=mode,
        checks=checks,machine=machine,runtime=runtime,build=program['build'])
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Cursor policy checks passed:',checks,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    parser.add_argument('--routing',action='store_true')
    args=parser.parse_args();run(args.output,args.mode,args.routing)
