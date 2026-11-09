#!/usr/bin/env python3
"""Focused common C runtime components in ordinary loaded Processes."""
import argparse
from pathlib import Path
from native_program import ROOT
from generate_c_runtime import expected_layout
from test_c_process import run as process_run


def fixture(out):
    out.mkdir(parents=True,exist_ok=True)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    path=out/'runtime.act'
    path.write_text(prefix+'''
PROC Main()
  BYTE index

  FOR index=0 TO 1 DO
    BEGIN
      LET image=Load()
      Collected(Start(image,BYTE POINTER(c"F")),-321)
      PROGRAM.Unload(image)
    END
  OD
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    return path


def run(out,group,mode,reuse=False):
    source=ROOT/'tests/programs/c_runtime_abi.c'
    return process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[source,ROOT/'c/runtime/lifecycle.c'],
        app_options=dict(includes=[ROOT/'c/runtime'],probes=[
            (ROOT/'c/runtime/layout.c',expected_layout())]),
        fixture_source=fixture(out),expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=['abi'],required=True)
    parser.add_argument('--case',choices=['raw','opt'],default='opt')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.group,args.case,args.from_build)
