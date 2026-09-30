#!/usr/bin/env python3
"""Per-command redirection, parser boundaries and real keys in both modes."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_shell_redirection import run
from test_shell_redirection_entry import run as physical
from test_shell_parser import run as parser

def cases():return [('basic-128','basic',128),('basic-256','basic',256),('large-256','large',256),('fault-read-128','fault-read',128),('fault-read-256','fault-read',256),('physical','physical',256),('parser','parser',128)]
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--only');a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--output',type=Path,default=ROOT/'build/shell-redirection');o=a.parse_args();t=compiler(o.compiler_dir)
    for name,scenario,size in cases():
        if o.only and name not in o.only.split(','):continue
        print('Shell redirection',o.case,name,flush=True);out=o.output/o.case/name;out.mkdir(parents=True,exist_ok=True)
        r=physical(t,out,o.case)if scenario=='physical'else parser(t,out,o.case)if scenario=='parser'else run(t,out,o.case,1,size,scenario)
        (out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Shell redirection matrix passed',o.case,flush=True)
