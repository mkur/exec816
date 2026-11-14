#!/usr/bin/env python3
"""Tiny raw/optimized original parser, callback and rectangle probe."""
import argparse,json
from calypsi_build import emit
from c_runtime_build import COMPILER_OPTIONS
from native_program import ROOT,build,compiler,require
from os_boundary import emulator
from prepare_mgview import PORT,prepare
from test_cooperative import data
from test_dos_stack import execute,ownership
from test_mgview import LAYOUT


def run(out,mode,reuse=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);prepare(out/'source')
    if reuse:
        from native_program import read_build
        from calypsi_image import read_image
        program=read_build(out/'program');foreign=read_image(out/'c/program.elf')
    else:
        foreign=emit(out/'c',[ROOT/'tests/programs/mgview_model.c',PORT/'native/support.c',ROOT/'c/compat/gem/rect.c'],
            [ROOT/'c/calypsi/image-info.s'],(),mode=='opt',roots=['MGViewProbe','MGViewChecks'],
            includes=[out/'source',PORT/'native'],compiler_options=COMPILER_OPTIONS,probes=[(ROOT/'tests/programs/mgview_layout.c',LAYOUT)])
        launcher=out/'probe.act';launcher.write_text('MODULE MGVIEWPROBE\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%foreign['symbols']['MGViewProbe'])
        program=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',tasks=True,
            task_capacity=8,foreign_image=foreign,optimize=True,console=False)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        runtime,_=execute(b,program,timeout=60,frame_limit=600,timer_irq=True)
        observed=data(b,program['image'],'result',True)
        require(observed==[0,0],'Original parser assertion failed at '+str(observed))
        checks=b.peek16(foreign['symbols']['MGViewChecks']);require(checks==30,'Incomplete parser probe')
        ownership(b,program,program['output'])
    (out/'results.json').write_text(json.dumps(dict(status='pass',tier='development',qualification=False,mode=mode,checks=checks,runtime=runtime),indent=2)+'\n')
    print('MGVIEW parser/callback/rectangle probe passed:',mode,checks)


if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse',action='store_true');p.add_argument('--mode',choices=('raw','opt'),default='opt')
    a=p.parse_args();run(a.output,a.mode,a.reuse)
