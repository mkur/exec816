#!/usr/bin/env python3
"""Emitted atomic input/stop acknowledgement and passive cycle measurement."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_mouse_observe import PIN,BRIDGE,ROM
from os_boundary import emulator
from bitmap_console_performance import native_markers,spans,totals


def run(out,mode,replay=False,observe=True):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),
        ROOT/'tests/programs/console_input_signals.act',out/'program',
        tasks=True,task_capacity=8,console=False,optimize=mode=='opt')
    require(p['build']['optimize']==(mode=='opt'),'Wrong image mode')
    marks=native_markers(p,[('INPUTSIGNALS_COLLECT','collect')])
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')
    old={k:os.environ.get(k) for k in keys}
    result=dict(status='running',tier='development',mode=mode,observed=observe,build=p['build'],pin=PIN,
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
    try:
        for key in keys:os.environ.pop(key,None)
        if observe:
            os.environ['EXEC816_LATENCY_TRACE']='1'
            os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for m in marks.values() for pc in [m['entry'],*m['returns']])
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned bridge')
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            result['machine']=verify_machine(b,ROM,PIN)
            runtime,_=execute(b,p,before_run=lambda b:b.profile_start() if observe else None,timer_irq=True)
            if observe:b.profile_stop()
            ownership(b,p,p['output'])
            result.update(runtime=runtime,checks=data(b,p['image'],'checks',True),merged=data(b,p['image'],'merged'))
            require(result['checks']==[28],'Signal checks missing')
        if observe:
            rows=spans(out/'emulator.log',marks)
            require(len(rows)==20,'Signal collection samples missing')
            result['timing']=dict(scope='Elapsed time includes preemption; 16 consecutive empty samples plus four notified/settling calls.',all=totals(rows),empty=totals(rows[1:17]))
        result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        (out/('results.json' if observe else 'replay-results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Input signal collection passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),required=True);p.add_argument('--replay',action='store_true');p.add_argument('--unobserved',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.mode,a.replay,not a.unobserved)
