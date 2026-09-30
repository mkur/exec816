#!/usr/bin/env python3
"""Native keyboard delivery and translation using the slice-1 wire oracle."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_console_coexistence import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=('raw','opt'),default='opt');p.add_argument('--mode',type=int,choices=(0,1,2,3,4,5),default=1)
    p.add_argument('--order',type=int,choices=(0,1),default=0);p.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    p.add_argument('--nmi',action='store_true');p.add_argument('--trace',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(compiler(ROOT/'build/actionc'),out,a.case=='opt',a.mode,a.order,a.sector_size,a.trace,native=True,nmi=a.nmi)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console input passed',a.case,a.mode,a.order,a.sector_size,flush=True)
