#!/usr/bin/env python3
"""Small loaded raw/optimized VDI record and call-boundary checks."""
import argparse
from pathlib import Path
from native_program import ROOT, require
from generate_vdi_client import expected_layout
from test_qed_native import process_run
from test_c_process import variant


def run(out, optimize, reuse=False, native_from=None):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:
        variant(native_from.resolve(),out,'sdfs');reuse=True
    fixture=out/'vdi-modes.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+'''
PROC Main()
  BYTE cycle

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

  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    result=process_run(out,optimize,reuse=reuse,rebuild_app=reuse,
        app_sources=[ROOT/'tests/programs/vdi_modes_abi.c'],
        app_options=dict(includes=[ROOT/'c/calypsi'],
            probes=[(ROOT/'c/calypsi/vdi-layout.c',expected_layout())]),
        fixture_source=fixture,expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=False)
    require(result['runtime']['native_irq_count']>0 and result['runtime']['native_nmi_count']>0,
            'VDI boundary check missed asynchronous native entries')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['raw','opt'],default='opt')
    parser.add_argument('--from-build',action='store_true')
    parser.add_argument('--native-from',type=Path)
    args=parser.parse_args()
    result=run(args.output,args.mode=='opt',args.from_build,args.native_from)
    print(result['status'],result['completed'])
