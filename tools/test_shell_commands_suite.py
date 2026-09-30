#!/usr/bin/env python3
"""Run the shell-command compiler/media/bank and content matrix."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_shell_commands import run

def cases():
    return [(f'basic-bank{bank}-{size}','basic',bank,size)for bank in (1,3)for size in (128,256)]+[('large-256','large',1,256)]+[(f'{scenario}-{size}',scenario,1,size)for scenario in ('raw-text','fault-read','fault-enumeration')for size in (128,256)]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--only');p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,default=ROOT/'build/shell-commands');a=p.parse_args();t=compiler(a.compiler_dir)
    for name,scenario,bank,size in cases():
        if a.only and name not in a.only.split(','):continue
        print('Shell commands',a.case,name,flush=True);out=a.output/a.case/name;out.mkdir(parents=True,exist_ok=True)
        r=run(t,out,a.case,bank,size,scenario);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Shell command matrix passed',a.case,flush=True)
