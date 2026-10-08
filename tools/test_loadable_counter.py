#!/usr/bin/env python3
"""Two private disk counters, physical close, cooperative stop and restart."""
import argparse,json
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT,read_build,require,verify_machine
from build_gem_desktop import build_desktop
from make_data_disk import make
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from desktop_mouse import schedule

def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if reuse else build_desktop(out,
        source=ROOT/'tests/programs/c_counter.act',program_output=out/'program',
        system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                                         sector_bytes=256,profile=4,format=2)])
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'COUNTER.APP').write_bytes((out/'apps/counter/program.app').read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
         binary_names={'COUNTER.APP'})
    app=json.loads((out/'apps/counter/app.json').read_text())
    relative=app['image']['symbols']['GEMCounter']-(12<<16)
    report=dict(status='running',tier='development',qualification=False,build=p['build'],app=app,cases=[])
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_CCOUNTERTEST_'+name.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.mount(0,str(out/'system.atr'));report['machine']=verify_machine(b,ROM,PIN)
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                faults=[p['labels'][name] for name in ('heap_fault','stack_overflow','arithmetic_fault')]
                for fault in faults:b.bp_set(fault)
                original=b.regs
                def regs():
                    result=original();pc=int(result['PC'].lstrip('$'),16)
                    require(pc not in faults,'Guest fault before graphics shutdown: '+str(result))
                    require(pc!=p['labels']['done'],'Guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return result
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
            def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def number(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
            def before(b):
                position=[320,120];b._cmd_ok('MOUSE ST')
                for phase in (1,2):
                    reach('dw($%x)=%d'%(at('phase'),phase))
                    bases=[number(at('bases')+i*4,4) for i in range(2)]
                    models=[base+relative for base in bases]
                    reach('&'.join('(dw($%x)=1)'%(m+12) for m in models))
                    frames(120)
                    require(all(number(m+14,4)>0 for m in models),'Both private counters must tick')
                    report['cases'].append(dict(phase=phase,bases=bases,
                        counts=[number(m+14,4) for m in models]))
                    if phase==1:
                        position=schedule(b,p,position,(392,40));frames(20)
                        b._cmd_ok('MOUSE AT 2000 0 0 1');frames(15)
                        b._cmd_ok('MOUSE AT 2000 0 0 0');frames(80)
                        require(any(number(m+12)==0 for m in models),'Physical close did not retire a counter')
                    b.poke16(at('stop'),1)
                b.bp_clear_all()
            try:runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=18000)
            except Exception:
                report['checks']=number(at('checks'));report['phase']=number(at('phase'))
                raise
            ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[5],'Counter lifetimes incomplete')
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.from_build)
