#!/usr/bin/env python3
"""Execute bounded console input drains and invalid resident-lease failure."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,verify_machine,sha256
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from test_cooperative import data
from os_boundary import emulator


def run(out,mode,replay=False,input_diagnostics=False):
    out.mkdir(parents=True,exist_ok=True)
    (out/'program').mkdir(exist_ok=True)
    source=out/'program/console_input_pump.act'
    source.write_bytes((ROOT/'tests/programs/console_input_pump.act').read_bytes())
    p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),
        source,out/'program',optimize=mode=='opt',
        tasks=True,task_capacity=8,console=False,console_test=True,input_diagnostics=input_diagnostics)
    require(p['build']['input_diagnostics']==input_diagnostics,'Wrong input diagnostics')
    require(p['build']['optimize']==(mode=='opt'),'Wrong pump fixture mode')
    require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned bridge')
    at=lambda name:next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_INPUTPUMP_'+name.upper()+'_'))
    result=dict(status='running',tier='development',mode=mode,build=p['build'],pin=PIN,cases=[],
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
    try:
        for variant in ((0,1,2) if input_diagnostics else (0,2)):
            folder=out/f'case-{variant}';folder.mkdir(exist_ok=True)
            with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
                machine=verify_machine(b,ROM,PIN)
                runtime,_=execute(b,p,expected_status=4 if variant else 0,
                    before_run=lambda b:b.poke(at('variant'),variant),timer_irq=True,frame_limit=2000)
                counts=data(b,p['image'],'counts',True)
                require(data(b,p['image'],'finished')==[0 if variant else 1],'Pump fault returned normally')
                if not variant:
                    require(counts==[0,7,63,64,0,64,2,0,8,8],'Wrong drain counts: '+str(counts))
                    ownership(b,p,p['output'])
                result['cases'].append(dict(variant=variant,machine=machine,runtime=runtime,
                    checks=data(b,p['image'],'checks',True),counts=counts))
        result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console input pump passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),required=True);p.add_argument('--replay',action='store_true')
    p.add_argument('--input-diagnostics',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.mode,a.replay,a.input_diagnostics)
