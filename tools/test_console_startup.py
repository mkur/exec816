#!/usr/bin/env python3
"""Public-only client exercises configured startup and explicit disable override."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,sha256
from os_boundary import emulator
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out,optimize,enabled):
    out.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config/kernel.json').read_text());config['console']=True
    cfg=out/'kernel.json';cfg.write_text(json.dumps(config)+'\n')
    p=build(t,ROOT/'tests/programs/native_console_startup.act',out,optimize=optimize,tasks=True,task_capacity=8,kernel_config=cfg,console=None if enabled else False)
    require(bool(p['build'].get('console_enabled'))==enabled,'Wrong resolved option')
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console emulator')
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):b.poke(next(x['address'] for x in p['image']['data'] if '_ENABLED_' in x['name']),int(enabled))
        rt,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        require(data(b,p['image'],'checkpoint')==[1],'Public client did not finish')
        require(rt['created']==int(enabled),'Unexpected resident worker count')
        require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
        ownership(b,p,out)
    return dict(status='pass',enabled=enabled,build=p['build'],runtime=rt,machine=machine)
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--disabled',action='store_true');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',not args.disabled)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Public startup passed',args.case,not args.disabled,flush=True)
