#!/usr/bin/env python3
"""Small emitted-code probe of selected GEM4XE raster algorithms."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,optimize=True,visible=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/('tests/programs/gem_raster_visible.c' if visible else 'tests/programs/gem_raster_core.c')
    foreign=emit(out/'c',[source],[ROOT/'c/calypsi/image-info.s'],(),optimize,
        includes=[ROOT/'ports/gem4xe/raster'],roots=['RasterProbe','RasterChecks'])
    driver=out/'probe.act'
    driver.write_text('MODULE RASTERPROBE\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
        '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%foreign['symbols']['RasterProbe'])
    program=build(compiler(ROOT/'build/actionc',release=True),driver,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,optimize=optimize,console=False,stack_checks=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,program,timeout=180,frame_limit=10000,timer_irq=True)
        observed=data(b,program['image'],'result',True)
        require(observed==[0,0],'Raster assertion line: '+str(observed))
        ownership(b,program,program['output'])
        record=dict(status='pass',tier='development',qualification=False,optimize=optimize,
            machine=machine,runtime=runtime,source_sha256=sha256(source),
            source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [source,
                *(ROOT/'ports/gem4xe/raster'/n for n in ('core.h','geometry.h','visible.h','inputs.json'))]},
            checks_modulo_65536=b.peek16(foreign['symbols']['RasterChecks']),
            reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,idle=0,per_public_task=[0]*12))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--visible',action='store_true')
    a=p.parse_args();print(run(a.output.resolve(),a.mode=='opt',a.visible)['status'])
