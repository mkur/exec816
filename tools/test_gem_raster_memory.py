#!/usr/bin/env python3
"""Run the production CPU raster path across native CPU-bank boundaries."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,optimize=True,packing_only=False,shift_only=False):
    out.mkdir(parents=True,exist_ok=True)
    backend=ROOT/'ports/gem4xe/adapter/gem-vbxe.c'
    text=backend.read_text()
    selected=text[text.index('static UWORD raster_span('):text.index('UWORD GemDrawingCopyBorrow(')]
    (out/'c').mkdir(exist_ok=True)
    (out/'c/raster-backend.inc').write_text(selected)
    source=ROOT/'tests/programs/gem_raster_memory.c'
    entry='RasterPackingProbe' if packing_only else 'RasterShiftProbe' if shift_only else 'RasterProbe'
    foreign=emit(out/'c',[ROOT/'c/calypsi/exec.c',source],
        [ROOT/'c/calypsi/image-info.s',ROOT/'c/calypsi/gateway.s',ROOT/'ports/gem4xe/raster/shift.s'],(),optimize,
        includes=[ROOT/'ports/gem4xe/raster'],roots=[entry,'RasterChecks'])
    driver=out/'probe.act'
    driver.write_text('MODULE RASTERPROBE\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
        '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%foreign['symbols'][entry])
    program=build(compiler(ROOT/'build/actionc',release=True),driver,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,optimize=optimize,console=False,stack_checks=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,program,timeout=120,frame_limit=6000,timer_irq=True)
        observed=data(b,program['image'],'result',True)
        diagnostic={name:b.memdump(foreign['symbols'][name],size).hex()
            for name,size in (('recorded',21),('ShiftFailure',10))
            if observed!=[0,0] and name in foreign['symbols']}
        require(observed==[0,0],'Memory raster assertion line: '+str(observed)+' '+str(diagnostic))
        ownership(b,program,program['output'])
        record=dict(status='pass',tier='development',qualification=False,machine=machine,runtime=runtime,
            optimize=optimize,packing_only=packing_only,shift_only=shift_only,
            source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in [source,backend,
                ROOT/'ports/gem4xe/raster/core.h',ROOT/'ports/gem4xe/raster/shift.s',ROOT/'ports/gem4xe/raster/screen.h']},
            checks=b.peek16(foreign['symbols']['RasterChecks']),
            reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,idle=0,per_public_task=[0]*12))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    probes=p.add_mutually_exclusive_group();probes.add_argument('--packing-only',action='store_true');probes.add_argument('--shift-only',action='store_true')
    a=p.parse_args();print(run(a.output.resolve(),a.mode=='opt',a.packing_only,a.shift_only)['status'])
