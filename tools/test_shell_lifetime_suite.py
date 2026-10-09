#!/usr/bin/env python3
"""Resident shell cleanup, stream races, headless/reuse and real serial faults."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler
from test_shell_lifetime import run as shell
from shell_stream_races import run as races
from shell_serial_recovery import run as serial
from test_dos_directory import directory
import test_dos_client as client
from native_program import build
from test_dos_stack import execute,ownership
from test_shell_entry import run as entry

def reuse(t,p,mode):
 old_build,old_execute,old_clean=client.build,client.execute,client.clean_ownership
 client.build=lambda *args,**kwargs:build(*args,**kwargs,task_capacity=8)
 client.execute=execute;client.clean_ownership=ownership
 try:return client.run(t,p,mode=='opt','reuse')
 finally:client.build,client.execute,client.clean_ownership=old_build,old_execute,old_clean

def cases(t,mode):return [
 ('basic-bank1',lambda p:shell(t,p,mode)),('filesystem-first-bank3',lambda p:shell(t,p,mode,3,4)),
 ('restore-failure',lambda p:shell(t,p,mode,2,1)),('close-failure',lambda p:shell(t,p,mode,2,2)),('removal-guard',lambda p:shell(t,p,mode,2,3)),
 ('stream-races-bank1',lambda p:races(t,p,mode)),('stream-races-bank3',lambda p:races(t,p,mode,3,1)),('stream-no-mount',lambda p:races(t,p,mode,2,3)),
 ('headless',lambda p:directory(t,p,mode)),('reuse',lambda p:reuse(t,p,mode)),('shell-no-mount',lambda p:entry(t,p,mode,True,True)),
 ('serial-128',lambda p:serial(t,p,mode,128)),('serial-256',lambda p:serial(t,p,mode,256))]
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--only');a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--output',type=Path,default=ROOT/'build/shell-lifetime');o=a.parse_args();t=compiler(o.compiler_dir)
 for name,action in cases(t,o.case):
  if o.only and name not in o.only.split(','):continue
  print('Shell lifetime',o.case,name,flush=True);out=o.output/o.case/name;out.mkdir(parents=True,exist_ok=True);r=action(out);(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
 print('Shell lifetime matrix passed',o.case,flush=True)
