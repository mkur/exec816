#!/usr/bin/env python3
"""Focused public Task lease/residency checks; one image per NIR mode."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,read_build,sha256
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from test_signals_irq import PIN
CASES={'lifetime':0,'held-removal':1,'resident-signal':2,'late-registration':3,'hold-limit':4}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('raw','opt'),required=True)
    parser.add_argument('--suite',default=','.join(CASES));parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(args.from_build) if args.from_build else build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/task_lifetime.act',out/'program',tasks=True,optimize=args.mode=='opt')
    require(p['build']['optimize']==(args.mode=='opt'),'Wrong NIR replay mode')
    result=dict(status='running',build=p['build'],cases=[],pin=PIN,emulator_sha256=sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer'))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            result['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            for number,name in enumerate(args.suite.split(',')):
                kind=CASES[name];caseout=out/name;caseout.mkdir(exist_ok=True)
                if number:b.state_load(slot='loaded')
                def before(b):
                    if not number:b.state_save(slot='loaded')
                    symbol=next(d for d in p['image']['data'] if '_KIND_' in d['name']);b.poke(symbol['address'],kind)
                status=4 if kind in (1,2) else 0
                try:runtime,_=execute(b,{**p,'output':caseout},before_run=before,preloaded=bool(number),expected_status=status,frame_limit=3000,timeout=180)
                except Exception:
                    print('checks',data(b,p['image'],'checks',True),flush=True);raise
                if not status:
                    require(data(b,p['image'],'finished')==[1],'Resident did not retire')
                    clean_ownership(b,p,p['output'])
                result['cases'].append(dict(name=name,status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True)))
                print('Passed',args.mode,name,flush=True)
        result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
