"""Actual current APP entry and resident retirement, with native result checks."""
from pathlib import Path
import json
from native_program import ROOT,require
from build_c_program import build as application
from test_c_process import run as process_run
from c_program import ABI


def fixture(out,raw=False):
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    prefix=prefix.replace('LONGINT lastPrimary','LONGINT lastPrimary,lastSecondary,expectedPrimary,expectedSecondary')
    body='''
INCLUDE "runtime-observe.inc"
TYPE RuntimeReport=[CARD callbacks,order,writes,closes LONGCARD title,runs]
LONGCARD held

PROC Waited(PROGRAMIMAGE.Image POINTER image LONGCARD id LONGINT primary,secondary
    CARD callbacks,order,writes,closes LONGCARD runs)
  PROCESS.Result result

  Require(id<>0 AND PROCESS.Wait(id,@result)<>0)
  lastPrimary=result.primary
  lastSecondary=result.secondary
  expectedPrimary=primary
  expectedSecondary=secondary
  Require(result.primary=primary AND result.secondary=secondary)
  LET report=RuntimeReport POINTER(ADDRESS(LONGCARD(ADDRESS(image.text))+REPORT_OFFSET))
  Require(report.callbacks=callbacks AND report.order=order)
  Require(report.writes=writes AND report.closes=closes AND report.runs=runs)
  completed==+1

RETURN

PROC RunCase(PROGRAMIMAGE.Image POINTER image BYTE POINTER args LONGINT primary,secondary
    CARD callbacks,order,writes,closes LONGCARD runs)

  Waited(image,Start(image,args),primary,secondary,callbacks,order,writes,closes,runs)
  Require(EXEC.AvailMem(0)=held)

RETURN

PROC Main()
  PROGRAMIMAGE.Image POINTER image,second
  LONGCARD one,two

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  image=Load()
  Waited(image,Start(image,BYTE POINTER(c"R")),0,0,3,321,1,1,1)
  PROGRAM.Unload(image)
  baseline=EXEC.AvailMem(0)
  image=Load()
  held=EXEC.AvailMem(0)
'''
    cases=[('R',0,0,3,321,1,1),('N',-321,0,3,321,1,1),('X',7,0,0,0,0,1)]
    if not raw:cases += [('A',20,304,0,0,0,1),('T',20,311,0,0,0,1),
        ('H',0,0,32,0,1,1),('F',20,0xc219,3,321,1,1),
        ('C',20,0xc219,3,321,1,1),('P',-7,205,3,321,1,1),('B',0,0,1,9,0,1)]
    else:cases += [('C',20,0xc219,3,321,1,1)]
    for ordinal,(mode,*values) in enumerate(cases,1):
        cause=f'LONGINT(CARD({values[1]}))' if values[1]>32767 else str(values[1])
        body+='  RunCase(image,BYTE POINTER(c"'+mode+'"),'+','.join([str(values[0]),cause,*map(str,[*values[2:],ordinal])])+')\n'
    count=len(cases);last=cases[-1][3:]
    # INIT failure and early stop leave unrelated application globals intact.
    for mode,cause in [('I',103),('Q',311)]:
        argument='BYTE POINTER(c"I")' if mode=='I' else 'BYTE POINTER(c"\"" )'
        # Use a one-byte native array for the unmatched quote; no source escaping.
        if mode=='Q':argument='@quote(0)'
        body+='  RunCase(image,'+argument+',20,'+str(cause)+','+','.join(map(str,[*last,count]))+')\n'
    body+='''  one=Start(image,BYTE POINTER(c"E"))
  Require(PROCESS.RequestStop(one)<>0)
'''
    body+='  Waited(image,one,0,0,'+','.join(map(str,[*last,count]))+')\n'
    body+='  Require(EXEC.AvailMem(0)=held)\n'
    body+='  RunCase(image,BYTE POINTER(c"R"),0,0,3,321,1,1,'+str(count+1)+')\n'
    body+='''  PROGRAM.Unload(image)
  Require(EXEC.AvailMem(0)=baseline)
'''
    if not raw:
        body+='''  image=Load()
  second=Load()
  one=Start(image,BYTE POINTER(c"R"))
  two=Start(second,BYTE POINTER(c"H"))
  Waited(image,one,0,0,3,321,1,1,1)
  Waited(second,two,0,0,32,0,1,1,1)
  PROGRAM.Unload(image)
  PROGRAM.Unload(second)
  Require(EXEC.AvailMem(0)=baseline)
'''
    body+='''  LET service=AESSTATE.Get()
  Require(service.count=0 AND AESCORE.Idle(service)<>0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
'''
    body=body.replace('LONGCARD held','BYTE ARRAY quote=[34 0]\nLONGCARD held')
    path=out/'lifecycle.act';path.write_text(prefix+body)
    return path,1+len(cases)+4+(0 if raw else 2)


def run(out,mode,reuse=False):
    source=ROOT/'tests/programs/c_runtime_lifecycle.c'
    def build(destination):
        app=application(destination,[source],mode=='opt',main_signature='args',
            minimum_stack=ABI['stack_floor_bytes'],includes=[ROOT/'c/runtime'],
            definitions={name:['-DEXEC_CRT_TEST'] for name in ('allocation.c','files.c')},
            probes=[(source,[('report size',16),('report title',8),('report runs',12)])])
        offset=app['image']['symbols']['report']-(ABI['link_bank']<<16)
        (out/'runtime-observe.inc').write_text('PUBLIC CONST REPORT_OFFSET=LONGCARD($'+format(offset,'x')+')\n')
        return app
    path,completed=fixture(out,mode=='raw')
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,app_builder=build,
        fixture_source=path,expected_completed=completed,native_optimize=True,
        release_compiler=True,loader_failures=False,observe_stacks=True)
    require(record['runtime']['native_irq_count']>0 and record['runtime']['native_nmi_count']>0,
            'Missing asynchronous context evidence')
    record['c_runtime_lifecycle']=dict(mode=mode,actual_entry=ABI['entry'],completed=completed)
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
