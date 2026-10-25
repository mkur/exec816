#!/usr/bin/env python3
"""Small raw/optimized copy admission, results and layout probes."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from generate_vdi_client import expected_layout
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,optimize=True):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/vdi_copy_abi.c',ROOT/'c/calypsi/vdi.c']
    foreign=emit(out/'c',sources,[ROOT/'c/calypsi/image-info.s'],(),optimize,
        includes=[ROOT/'c/calypsi',ROOT/'ports/gem4xe/adapter'],
        roots=['CopyProbe','CopyChecks'],probes=[(ROOT/'c/calypsi/vdi-layout.c',expected_layout())])
    source=out/'probe.act'
    source.write_text('MODULE VDICOPYPROBE\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
        '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%foreign['symbols']['CopyProbe'])
    program=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,optimize=optimize,console=False,stack_checks=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,program,timeout=120,frame_limit=6000,timer_irq=True)
        observed=data(b,program['image'],'result',True)
        require(observed==[0,0],'Copy assertion line: '+str(observed))
        ownership(b,program,program['output'])
        record=dict(status='pass',tier='development',qualification=False,checks=b.peek16(foreign['symbols']['CopyChecks']),
            optimize=optimize,machine=machine,runtime=runtime,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in sources},
            reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');a=p.parse_args()
    print(run(a.output.resolve(),a.mode=='opt')['status'])
