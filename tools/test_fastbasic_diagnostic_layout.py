#!/usr/bin/env python3
"""Small raw/optimized diagnostic layout and stale-record reader probes."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(out,optimize):
 out.mkdir(parents=True,exist_ok=True)
 f=emit(out/'c',[ROOT/'tests/programs/fastbasic_diagnostic_layout.c',ROOT/'c/calypsi/fastbasic-diagnostic.c'],[ROOT/'c/calypsi/image-info.s'],(),optimize,roots=['DiagnosticProbe','DiagnosticChecks'])
 source=out/'probe.act';source.write_text('MODULE FBDIAGNOSTICLAYOUT\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%f['symbols']['DiagnosticProbe'])
 p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,foreign_image=f,optimize=optimize,console=False,stack_checks=True)
 pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
 with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
  machine=verify_machine(b,rom,pin);runtime,_=execute(b,p,timeout=120,frame_limit=6000)
  result=data(b,p['image'],'result',True);require(result==[0,0],'Diagnostic layout assertion: '+str(result));ownership(b,p,p['output'])
  checks=b.peek16(f['symbols']['DiagnosticChecks'])
 report=dict(status='pass',tier='development',qualification=False,optimize=optimize,checks=checks,machine=machine,runtime=runtime,build=p['build'])
 (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--raw',action='store_true');args=a.parse_args();print(run(args.output.resolve(),not args.raw)['checks'])
