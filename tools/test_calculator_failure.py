#!/usr/bin/env python3
"""Calculator missing/malformed RSC, stop-before-entry and armed-close lifetimes."""
import argparse,json
from pathlib import Path
from native_program import ROOT,read_build,require,verify_machine
from build_gem_desktop import build_desktop
from make_data_disk import make
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from desktop_mouse import schedule
from gem_applications import symbols
from prepare_calculator import resource_cases


def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if reuse else build_desktop(out,source=ROOT/'tests/programs/calculator_failure.act')
    cases=resource_cases(out/'resources');reports={}
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_CALCFAIL_'+name.upper()+'_' in d['name'])
    for mode,name in enumerate(('missing','bad','early','armed'),1):
        directory=out/name;media=directory/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        (media/'C/CALC.APP').write_bytes((out/'apps/calc/program.app').read_bytes())
        if mode!=1:(media/'CALC.RSC').write_bytes(cases['TEDBAD.RSC' if mode==2 else 'CALC.RSC'])
        make(directory/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
             binary_names={'C/CALC.APP'}|({'CALC.RSC'} if mode!=1 else set()))
        record=dict(status='running',mode=name,cycles=2)
        try:
            with emulator(BRIDGE,ROM,directory,pin=PIN) as b:
                for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
                record['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(directory/'system.atr'))
                def num(address,n=2):return int.from_bytes(b.memdump(address,n),'little')
                def reach(condition):
                    condition='(@xpc=$%x)&(%s)'%(p['labels']['native_irq'],condition)
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    run_to(b,p['labels']['native_irq'],condition=condition,timeout=240,frame_limit=16000)
                def before(b):
                    reach('dw($%x)=1'%at('phase'));b.memload(at('scenario'),mode.to_bytes(2,'little'))
                    if mode==4:
                        b._cmd_ok('MOUSE ST');position=[320,120]
                        for phase in (2,3):
                            reach('dw($%x)=%d'%(at('phase'),phase))
                            sy=symbols(b,p,out,'calc',num(at('child'),4));model=sy['Calculator']
                            reach('dw($%x)=1'%(model+4))
                            position=schedule(b,p,position,(456,96))
                            reach('@frame>=%d'%(b.eval_expr('@frame')+60))
                            b._cmd_ok('MOUSE AT 2000 0 0 1');reach('dw($%x)=3'%(model+8))
                            require(num(sy['shown'],4)==0,'Armed key activated before release')
                            b.memload(at('stop'),bytes([1,0]))
                            if phase==2:
                                reach('dw($%x)=3'%at('phase'))
                                b._cmd_ok('MOUSE AT 2000 0 0 0')
                    b.bp_clear_all()
                runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=30000)
                ownership(b,p,p['output']);require(num(at('phase'))==4,'Incomplete failure fixture')
                record.update(status='pass',runtime=runtime,checks=num(at('checks')))
        except Exception as error:record.update(status='fail',error=str(error));raise
        finally:
            (directory/'results.json').write_text(json.dumps(record,indent=2)+'\n')
        reports[name]=record;print('Calculator failure/lifetime pass:',name,flush=True)
    (out/'results.json').write_text(json.dumps(reports,indent=2)+'\n')
    return reports


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true');args=parser.parse_args();run(args.output.resolve(),args.replay)
