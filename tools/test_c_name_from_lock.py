#!/usr/bin/env python3
"""Small raw/optimized C and native NIR canonical-name boundary cohorts."""
import argparse
from pathlib import Path
from native_program import ROOT
from test_qed_native import process_run

def run(out,optimize):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture=out/'names.act'
    fixture.write_text(prefix+'''
PROC Main()
  BYTE cycle

  LET parent=DOS.CreateDir(BYTE POINTER(c"RAM:NEST"))
  Require(parent<>NULL)
  LET previous=DOS.CurrentDir(parent)
  Require(DOS.AssignPath(BYTE POINTER(c"QW"),BYTE POINTER(c"RAM:NEST"))<>0)
  FOR cycle=0 TO 1 DO
    BEGIN
      LET image=Load()
      Collected(Start(image,BYTE POINTER(c"F")),-321)
      PROGRAM.Unload(image)
      IF cycle=0 THEN
        baseline=EXEC.AvailMem(0)
      ELSE
        Require(EXEC.AvailMem(0)=baseline)
      FI
    END
  OD

  baseline=EXEC.AvailMem(0)
  Bad(BYTE POINTER(c"SYS:VERSION.APP"),LONGINT(O65TYPES.ERROR_BAD_FORMAT))
  DOS.CurrentDir(previous)
  DOS.UnLock(parent)
  Require(DOS.AssignPath(BYTE POINTER(c"QW"),NULL)<>0)
  Require(DOS.DeleteFile(BYTE POINTER(c"RAM:NEST"))<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    return process_run(out,optimize,app_sources=[ROOT/'tests/programs/c_name_from_lock.c'],
        fixture_source=fixture,expected_completed=2,native_optimize=optimize,
        release_compiler=True,loader_failures=True,writable=True,ram=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--raw',action='store_true');a=p.parse_args();run(a.output,not a.raw)
