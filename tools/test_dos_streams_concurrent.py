#!/usr/bin/env python3
"""Public DOS streams in the existing eight-Task console/SIO timing workload."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_console_concurrent import run

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    a.add_argument('--speed',type=int,choices=(0,1),default=0)
    a.add_argument('--bank',type=int,choices=(1,3),default=1)
    a.add_argument('--trace',action='store_true');a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(out,args.case,args.sector_size,args.speed,args.bank,args.trace,compiler(args.compiler_dir),streams=True)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS streams concurrency passed',args.case,args.sector_size,args.speed,args.bank,flush=True)
