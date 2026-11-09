#!/usr/bin/env python3
"""Focused common C runtime components in ordinary loaded Processes."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from generate_c_runtime import expected_layout
from c_program import ABI
from test_c_process import run as process_run


def fixture(out,group):
    out.mkdir(parents=True,exist_ok=True)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    path=out/'runtime.act'
    body='''
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
'''
    if group!='abi':
        body='''
PROC Main()
  PROGRAMIMAGE.Image POINTER first,second
  LONGCARD one,two

  first=Load()
  Collected(Start(first,BYTE POINTER(c"F")),-321)
  PROGRAM.Unload(first)
  baseline=EXEC.AvailMem(0)
  first=Load()
  second=Load()
  one=Start(first,BYTE POINTER(c"F"))
  two=Start(second,BYTE POINTER(c"F"))
  Collected(one,-321)
  Collected(two,-321)
  Collected(Start(first,BYTE POINTER(c"F")),-322)
  PROGRAM.Unload(first)
  PROGRAM.Unload(second)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
'''
    path.write_text(prefix+body)
    return path


def run(out,group,mode,reuse=False):
    abi=group=='abi'
    source=ROOT/('tests/programs/c_runtime_abi.c' if abi else
        'tests/programs/c_runtime_prefix.c' if mode=='raw' else 'tests/programs/c_runtime_allocation.c')
    components=['lifecycle.c'] if abi else ['allocation.c','arguments.c']
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[source,*[ROOT/'c/runtime'/name for name in components]],
        app_options=dict(minimum_stack=ABI['stack_floor_bytes'],includes=[ROOT/'c/runtime'],probes=[
            (ROOT/'c/runtime/layout.c',expected_layout())],
            definitions={'allocation.c':['-DEXEC_CRT_TEST']}),
        fixture_source=fixture(out,group),expected_completed=2 if abi else 4,native_optimize=True,
        release_compiler=True,loader_failures=False,observe_stacks=not abi)
    require(record['runtime']['native_irq_count']>0 and record['runtime']['native_nmi_count']>0,
            'Missing asynchronous entry evidence')
    record['c_runtime_component']=dict(group=group,mode=mode,
        production_app_abi=record['app']['abi']['version'])
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record



if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=['abi','allocation','arguments'],required=True)
    parser.add_argument('--case',choices=['raw','opt'],default='opt')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.group,args.case,args.from_build)
