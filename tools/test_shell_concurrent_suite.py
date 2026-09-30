#!/usr/bin/env python3
"""Seven resident-shell workloads, five with identical-image/key replay."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_shell_concurrent import run
MATRIX=[('target128-raw','raw',128,0,1,True),('target128-opt','opt',128,0,1,True),('target256-raw','raw',256,0,1,True),('target256-opt','opt',256,0,1,True),('stock128-opt','opt',128,1,1,True),('bank3-raw','raw',128,0,3,False),('bank3-opt','opt',128,0,3,False)]
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--only');a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--output',type=Path,default=ROOT/'build/shell-concurrency');o=a.parse_args();t=compiler(o.compiler_dir)
 for name,mode,size,speed,bank,trace in MATRIX:
  if o.only and name not in o.only.split(','):continue
  print('Shell concurrency',name,flush=True);out=o.output/name;out.mkdir(parents=True,exist_ok=True)
  r=run(out,mode,size,speed,bank,trace,t);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
 print('Shell concurrency matrix passed',flush=True)
