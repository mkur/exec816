#!/usr/bin/env python3
"""Physical redirection through the current shipped entry and matching disk."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_shell_entry import run as entry

def run(t,out,mode,no_mount=False):
    return entry(t,out,mode,no_mount=no_mount,paced=True,redirection=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=('raw','opt'),required=True)
    p.add_argument('--no-mount',action='store_true')
    p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    r=run(compiler(a.compiler_dir),out,a.case,a.no_mount)
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Shell physical redirection passed',a.case,flush=True)
