#!/usr/bin/env python3
"""Copied console consumer/ingress checks after removal of frontend polling."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,verify_machine
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_mouse_observe import PIN,BRIDGE,ROM
from os_boundary import emulator


def run(out,mode,replay=False,input_diagnostics=False):
    out.mkdir(parents=True,exist_ok=True)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile)+'\n')
    p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/console_input_pump.act',out/'program',optimize=mode=='opt',
        tasks=True,task_capacity=8,console=False,console_test=True,memory_profile=memory,input_diagnostics=input_diagnostics)
    result=dict(status='running',tier='development',qualification=False,mode=mode)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            result['machine']=verify_machine(b,ROM,PIN)
            result['runtime'],_=execute(b,p,frame_limit=2000)
            require(data(b,p['image'],'finished')==[1],'Consumer did not finish')
            result['checks']=data(b,p['image'],'checks',True)[0]
            require(result['checks']==20,'Incomplete copied console checks')
            ownership(b,p,p['output'])
            result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Copied console ingress passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true')
    p.add_argument('--input-diagnostics',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.mode,a.replay,a.input_diagnostics)
