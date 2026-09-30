#!/usr/bin/env python3
"""Ordinary Tasks prove the SIO driver's public coordination contract."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from test_signals_irq import PIN


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',required=True,choices=('raw','opt'))
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    args=parser.parse_args(); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    program=build(compiler(args.compiler_dir),ROOT/'tests/programs/driver_boundary.act',
                  out/'program',tasks=True,optimize=args.mode=='opt')
    bridge_dir=ROOT/'build/shell-paced-bridge'; rom=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',build=program['build'],platform=PIN,
                emulator_sha256=sha256(bridge_dir/'AltirraBridgeServer'),
                reservation_delta=dict(fixed_bank_zero=0,per_task_bank_zero=0))
    try:
        with emulator(bridge_dir,rom,out,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,rom,PIN)
            runtime,_=execute(bridge,program,frame_limit=3000,timeout=180)
            require(data(bridge,program['image'],'finished')==[1],'Driver coordination did not finish')
            clean_ownership(bridge,program,program['output'])
            report.update(status='pass',runtime=runtime,checks=data(bridge,program['image'],'checks',True),
                          scope='Public dequeue/claim exclusion, signal-before-Wait, immediate reply reuse/free, guards and ownership restoration')
        print(args.mode+': public driver coordination passed',flush=True)
    except Exception as error:
        report.update(status='fail',error=str(error)); raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
