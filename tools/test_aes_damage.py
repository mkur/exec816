#!/usr/bin/env python3
"""Small raw/optimized invalidation API and generated-record probes."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from generate_aes_server import expected_layout
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,optimize=True):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/aes_damage.c',ROOT/'c/calypsi/aes-windows.c',ROOT/'c/calypsi/exec.c']
    foreign=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),optimize,
        roots=['DamageProbe','DamageChecks','DamageWire'],
        definitions={'aes-windows.c':['--no-interprocedural-cross-jump']},
        probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout())])
    source=out/'probe.act'
    source.write_text('''MODULE AESDAMAGE
USE CALYPSICALL
USE AESTYPES
LONGINT result
PROC Main()
  AESTYPES.Request POINTER wire
  wire=AESTYPES.Request POINTER(ADDRESS($%x))
  wire.invalidationCount=7
  wire.invalidations(6).handle=$7f12
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
  IF result=0 AND (wire.invalidationCount<>2 OR
      wire.invalidations(1).epoch<>LONGCARD($12345678) OR
      wire.invalidations(1).rect.right<>123) THEN
    result=-1
  FI
RETURN
ENDMODULE
'''%(foreign['symbols']['DamageWire'],foreign['symbols']['DamageProbe']))
    program=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
        task_capacity=8,foreign_image=foreign,optimize=optimize,console=False,stack_checks=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,program,timeout=120,frame_limit=6000,timer_irq=True)
        observed=data(b,program['image'],'result',True)
        require(observed==[0,0],'Invalidation assertion line: '+str(observed))
        ownership(b,program,program['output'])
        record=dict(status='pass',tier='development',qualification=False,checks=b.peek16(foreign['symbols']['DamageChecks']),
            optimize=optimize,machine=machine,runtime=runtime,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in sources},
            reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');a=p.parse_args()
    print(run(a.output.resolve(),a.mode=='opt')['status'])
