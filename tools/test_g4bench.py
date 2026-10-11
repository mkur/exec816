#!/usr/bin/env python3
"""Focused loaded G4BENCH clock, window and cleanup development check."""
import argparse
import json
from pathlib import Path
from build_c_program import build as application
from build_gem_desktop import build_desktop
from gem_applications import symbols
from make_data_disk import make
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import PIN, BRIDGE, ROM
from test_cooperative import data
from stack_budget import bank_zero_delta, stack_usage
import adapter_state as adapter


def run(out,reuse=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if reuse:p=read_build(out/'program')
    else:
        p=build_desktop(out,source=ROOT/'tests/programs/g4bench_session.act',
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2)])
        application(out/'clock-probe',[ROOT/'tests/programs/g4bench_clock.c',
                    ROOT/'ports/gem4xe/apps/g4bench/clock.c'])
        media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        (media/'C/G4BENCH.APP').write_bytes((out/'apps/g4bench/program.app').read_bytes())
        (media/'C/G4CLOCK.APP').write_bytes((out/'clock-probe/program.app').read_bytes())
        make(out/'system.atr',media,binary_names={'C/G4BENCH.APP','C/G4CLOCK.APP'},
             filesystem='sdfs',sector_bytes=256,sectors=2880)
    report=dict(status='running',tier='development',qualification=False,
                bank_zero_delta=bank_zero_delta(p['build']['memory']),cases=[])
    at=lambda name:next(d['address'] for d in p['image']['data']
                       if '_G4BENCHTEST_'+name.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(out/'system.atr'))
            def get(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                except Exception:
                    report['failure']=dict(adapter=b.memdump(adapter.STATE,64).hex(),
                        checks=get(at('checks')),ready=get(at('ready')),pc=b.regs())
                    raise
            def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def key(name):
                b._cmd_ok('KEY '+name+' down');frames(3)
                b._cmd_ok('KEY '+name+' up');frames(20)
            def before(b):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                for cycle in (1,2):
                    reach('dw($%x)=%d'%(at('ready'),cycle))
                    sy=symbols(b,p,out,'g4bench',get(at('benchmark'),4))
                    reach('dw($%x)=1'%sy['g4b_ready']);frames(100)
                    first=get(sy['g4b_clock']+4,4);reads=get(sy['g4b_reads'],4)
                    key('RETURN');reach('dw($%x)>%d'%(sy['g4b_reads'],reads))
                    require(get(sy['g4b_clock']+4,4)>first,'Clock did not advance')
                    require(get(sy['g4b_clock']+8,4)==50,'Expected pinned PAL clock')
                    report['cases'].append(dict(cycle=cycle,clock_reads=get(sy['g4b_reads'],4)))
                    if cycle==1:key('ESC')
                    else:b._cmd_ok('KEY ESC down')
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=18000)
            ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[2],'Benchmark lifetimes incomplete')
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                          stack_usage=stack_usage(b,p['build']['memory']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();run(args.output,args.replay)
