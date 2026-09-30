#!/usr/bin/env python3
"""Console setup failure unwinds the actual resident shell allocation/context."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,build,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_console_coexistence import PIN

def run(t,out,mode):
    out.mkdir(parents=True,exist_ok=True)
    p=build(t,ROOT/'tests/programs/shell_start_failure.act',out,optimize=mode=='opt',tasks=True,task_capacity=8,console=False,dos_mounts=[])
    require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console bridge')
    require(sha256(ROOT/'build/firmware/altirraos-816.rom')==PIN['rom']['sha256'],'Unpinned ROM')
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN)as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:rt,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:print('Startup failure checks',data(b,p['image'],'checks',True),flush=True);raise
        require(data(b,p['image'],'finished')==[1] and data(b,p['image'],'checks',True)==[5],'Incomplete startup unwind')
        require(rt['created']==0,'Failed startup created a worker');ownership(b,p,out)
    return dict(status='pass',mode=mode,build=p['build'],runtime=rt,machine=machine,pin=PIN,checks=5,source_inputs={s:sha256(ROOT/s)for s in ('examples/shell/shell-session.inc','examples/shell/shell-commands.inc','tests/programs/shell_start_failure.act','tools/test_shell_start_failure.py')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell startup unwind passed',a.case,flush=True)
