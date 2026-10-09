#!/usr/bin/env python3
"""Small raw/optimized emitted check of the signed GEM box thickness boundary."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    f=emit(out/'c',[ROOT/'tests/programs/form_extent.c',ROOT/'c/calypsi/aes-form.c'],
        [ROOT/'c/calypsi/image-info.s'],(),optimize,roots=['FormExtentProbe'])
    source=out/'probe.act'
    source.write_text('''MODULE FORMEXTENT
USE CALYPSICALL
LONGINT result
PROC Main()

  result=CALYPSICALL.Invoke(ADDRESS($%x),0)

RETURN
ENDMODULE
'''%f['symbols']['FormExtentProbe'])
    p=build(compiler(ROOT/'build/actionc'),source,out/'program',tasks=True,task_capacity=8,
        foreign_image=f,optimize=optimize,console=False)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,p,timeout=120,frame_limit=6000,timer_irq=True)
        observed=data(b,p['image'],'result',True)
        require(observed==[0,0],'Signed box thickness failed: '+str(observed))
        ownership(b,p,p['output'])
    r=dict(status='pass',tier='development',optimized=optimize,cases=14,machine=machine,
        runtime=runtime,c_elf_sha256=f['provenance']['elf_sha256'])
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true');args=parser.parse_args();run(args.output.resolve(),not args.raw)
