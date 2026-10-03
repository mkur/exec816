#!/usr/bin/env python3
"""Native keyboard delivery and translation using the slice-1 wire oracle."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,read_build,require
from test_console_coexistence import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=('raw','opt'),default='opt');p.add_argument('--mode',type=int,choices=(0,1,2,3,4,5),default=1)
    p.add_argument('--order',type=int,choices=(0,1),default=0);p.add_argument('--sector-size',type=int,choices=(128,256),default=128)
    p.add_argument('--paced',action='store_true',help='Use the pinned paced keyboard bridge')
    p.add_argument('--from-build',type=Path,help='Reuse an unchanged native input fixture')
    p.add_argument('--nmi',action='store_true');p.add_argument('--trace',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:
        program=read_build(a.from_build) if a.from_build else None
        if program:
            require(program['build']['optimize']==(a.case=='opt') and program['build']['console_test'],'Wrong reused fixture')
            require(program['build']['signal_irq_probe']==int(a.nmi),'Reused NMI probe differs')
            require(a.mode!=5,'Masked overrun requires its own instrumented build')
            require(out==program['output'],'Replay output must be the original build directory')
        r=run(compiler(ROOT/'build/actionc'),out,a.case=='opt',a.mode,a.order,a.sector_size,a.trace,program=program,native=True,nmi=a.nmi,paced=a.paced)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console input passed',a.case,a.mode,a.order,a.sector_size,flush=True)
