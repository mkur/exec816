#!/usr/bin/env python3
"""Focused raw/optimized public console I/O bridge and local-buffer check."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'memory-profile.json';memory.write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/console_cell_io.act',out,
            optimize=optimize,tasks=True,task_capacity=8,console=True,memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=120,frame_limit=9000)
        except Exception:
            print('Checks',data(b,p['image'],'checks'),flush=True);raise
        ownership(b,p,out)
        return dict(status='pass',tier='development',build=p['build'],machine=machine,
                    runtime=runtime,checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['raw','opt'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out,args.case=='opt')
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console cell I/O passed',args.case,result['checks'],flush=True)
