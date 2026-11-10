#!/usr/bin/env python3
"""Actual GemARC startup rollback at each of its nine allocations."""
import argparse,json
from pathlib import Path
from native_program import ROOT
from prepare_gemarc import prepare,PORT
from test_c_process import run as process_run


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);prepare(out/'prepared')
    source=out/'prepared/source/src/apps'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture=out/'allocations.act'
    fixture.write_text(prefix+'''
PROC Main()
  BYTE index

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  LET image=Load()
  Collected(Start(image,BYTE POINTER(c"F")),-321)
  baseline=EXEC.AvailMem(0)
  FOR index=1 TO 9 DO
    Collected(Start(image,BYTE POINTER(c"F")),-321)
    Require(EXEC.AvailMem(0)=baseline)
  OD

  PROGRAM.Unload(image)
  LET service=AESSTATE.Get()
  Require(service.count=0 AND AESCORE.Idle(service)<>0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    result=process_run(out,True,app_sources=[ROOT/'tests/programs/gemarc_allocation.c',
        *[source/name for name in ('gemarc.c','arcfile.c','arccodec.c')],
        *[PORT/'native'/name for name in ('io.c','path.c','metadata.c')],ROOT/'c/calypsi/file-list.c'],
        app_options=dict(main_signature='args',minimum_stack=2560,
            includes=[source,PORT/'native',ROOT/'c/calypsi'],
            definitions={str(source/'gemarc.c'):['-Dmain=GemArcApplication',
                '-Dmalloc=GemArcTestMalloc','-Dform_alert=GemArcTestAlert']}),
        fixture_source=fixture,expected_completed=10,native_optimize=True,release_compiler=True,
        task_capacity=12,loader_failures=False,
        media_files={'GEMARC.RSC':(out/'prepared/GEMARC.RSC').read_bytes()})
    result['partial_allocation']=dict(failed_allocations=list(range(1,10)),executions=10,
        actual_application=True,alert_response='test acknowledgement',exact_heap_restoration=True)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
