#!/usr/bin/env python3
"""Focused emitted-code checks for the native QED foundation."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from prepare_qed import inventory
from test_c_process import run as process_run

def abi(out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/qed_native_abi.c'
    options=dict(definitions={source.name:['--char-is-unsigned']},probes=[(source,[
        ('huge pointer',4),('native pointer',3),('legacy word',2),('long',4),
        ('OBJECT',24),('OBJECT spec',12),('TEDINFO',28)])])
    # Keep the raw cohort to the ABI boundary, not the complete Process matrix.
    fixture=None;completed=12
    if not optimize:
        fixture=out/'qed-abi.act'
        prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
        fixture.write_text(prefix+'''
PROC Main()

  LET first=Load()
  Collected(Start(first,BYTE POINTER(c"F")),-321)
  PROGRAM.Unload(first)
  baseline=EXEC.AvailMem(0)
  LET second=Load()
  Collected(Start(second,BYTE POINTER(c"F")),-321)
  PROGRAM.Unload(second)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
        completed=2
    record=process_run(out,optimize,app_sources=[source],app_options=options,
        fixture_source=fixture,expected_completed=completed,native_optimize=True,release_compiler=True)
    require(record['runtime']['native_nmi_count']>0 and record['runtime']['native_irq_count']>0,
            'QED ABI probe missed native asynchronous entries')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--group',choices=('abi','sources'),required=True)
    p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    result=abi(out,a.case=='opt') if a.group=='abi' else inventory(out,a.case=='opt')
    print('QED native',a.group,a.case,'passed' if a.group=='abi' else 'inventoried',flush=True)
