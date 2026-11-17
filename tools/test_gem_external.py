#!/usr/bin/env python3
"""Focused emitted external GEM handoff, redraw ownership and visible move."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    p=build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/gem_external.act',out/'program',tasks=True,optimize=True)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN);runtime,_=execute(b,p,timeout=90,frame_limit=900)
        ownership(b,p,p['output']);checks=data(b,p['image'],'checks',True)[0]
        require(checks==20,'Incomplete external GEM checks')
    r=dict(status='pass',tier='development',qualification=False,checks=checks,native_sha256=sha256(p['xex']),machine=machine,runtime=runtime)
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('External GEM checks:',checks)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    run(a.parse_args().output.resolve())
