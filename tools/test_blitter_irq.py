#!/usr/bin/env python3
"""Real VBXE IRQ delivery and retained producer lifetime through emitted code."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256, read_build
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage


def run(out, mode, replay=False, timer=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/blitter_irq.act',
            out/'program',tasks=True,task_capacity=8,console=False,optimize=mode=='opt')
    report=dict(status='running',tier='development',mode=mode,timer_irq=timer,build=p['build'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            report['machine']=verify_machine(b,ROM,PIN)
            saved={}
            def before(b):
                saved['irq']=b.memdump(0x216,2)
                saved['timer']=b.memdump(0x210,2)
            runtime,_=execute(b,p,before_run=before,timeout=90,frame_limit=4000,timer_irq=timer)
            require(b.memdump(0x216,2)==saved['irq'],'IRQ vector not restored')
            require(b.memdump(0x210,2)==saved['timer'],'Timer vector not restored')
            require(b.peek(0xd654)==b'\0','VBXE IRQ left asserted')
            at=p['build']['task_storage']['BLITTER_STATE']
            emulations=b.peek16(at+30)
            require(emulations==1,'Expected one emulation IRQ completion')
            clean_ownership(b,p,p['output'])
            require(data(b,p['image'],'checks',True)==[17],'Incomplete IRQ fixture')
            report.update(status='pass',emulation_completions=emulations,checks=data(b,p['image'],'checks',True),
                          runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/('results-timer.json' if timer else 'results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Blitter IRQ passed',mode,report['checks'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    parser.add_argument('--replay',action='store_true')
    parser.add_argument('--timer',action='store_true')
    args=parser.parse_args();run(args.output,args.mode,args.replay,args.timer)
