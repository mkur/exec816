#!/usr/bin/env python3
"""Focused emitted-code checks for the native QED foundation."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from prepare_qed import inventory,prepare,PORT
from test_c_process import run as process_run

def abi(out,optimize,focused=False,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/qed_native_abi.c'
    options=dict(definitions={source.name:['--char-is-unsigned']},probes=[(source,[
        ('huge pointer',4),('native pointer',3),('legacy word',2),('long',4),
        ('OBJECT',24),('OBJECT spec',12),('TEDINFO',28)])])
    # Keep the raw cohort to the ABI boundary, not the complete Process matrix.
    fixture=None;completed=12
    if not optimize or focused:
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
    record=process_run(out,optimize,reuse=reuse,rebuild_app=reuse,app_sources=[source],app_options=options,
        fixture_source=fixture,expected_completed=completed,native_optimize=True,release_compiler=True)
    require(record['runtime']['native_nmi_count']>0 and record['runtime']['native_irq_count']>0,
            'QED ABI probe missed native asynchronous entries')
    return record


def runtime(out,optimize,reuse=False,stop=False):
    require(optimize,'The runtime ownership cohort uses optimized C; raw is reserved for ABI probes')
    prepare(out/'inputs')
    qed=out/'inputs/source/qed/src';cflib=out/'inputs/source/cflib'
    source=ROOT/'tests/programs/qed_native_runtime.c'
    native=PORT/'native'
    sources=[source,native/'allocation.c',native/'entry.c',qed/'memory.c']
    options=dict(includes=[native,qed,cflib],definitions={
        path.name:['--char-is-unsigned','-DQED_BANKED_MALLOC=1',
                   '-Werror=implicit-function-declaration']+
                  (['-DAllocMem=QedFixtureAlloc'] if path.name=='allocation.c' else [])
        for path in sources})
    fixture=None;completed=12
    if stop:
        fixture=out/'qed-stop.act'
        prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
        prefix=prefix.replace('USE AESSTATE\n','USE AESSTATE\nUSE AESTYPES\nUSE TIMER\n')
        fixture.write_text(prefix+'''
; Observe the existing AES window state; no private launch/stop protocol.
PROC WindowReady()
  CARD attempt
  BYTE index,shown

  LET port=EXEC.CreateMsgPort()
  Require(port<>NULL)
  LET clock=TIMER.TimerClockRequest POINTER(EXEC.CreateIORequest(port,
      SIZEOF(TIMER.TimerClockRequest)))
  Require(clock<>NULL)
  Require(EXEC.OpenDevice(BYTE POINTER(c"timer.device"),TIMER.UNIT_VBLANK,
      @clock.tc_Request,0)=0)
  LET service=AESSTATE.Get()
  FOR attempt=0 TO 499 DO
    EXEC.Forbid()
    shown=0
    FOR index=0 TO AESTYPES.WINDOWS-1 DO
      BEGIN
        LET view=service.windows(index).view
        IF view<>NULL AND view.shown<>0 THEN
          shown=1
          EXIT
        FI
      END
    OD

    EXEC.Permit()
    IF shown<>0 THEN
      EXIT
    FI

    clock.tc_Request.io_Command=TIMER.TD_READCLOCK
    Require(EXEC.DoIO(@clock.tc_Request)=0)
    Require(TIMER.Deadline(clock,0)<>0)
    clock.tc_Request.io_Command=TIMER.TD_WAITUNTIL
    Require(EXEC.DoIO(@clock.tc_Request)=0)
  OD

  EXEC.CloseDevice(@clock.tc_Request)
  EXEC.DeleteIORequest(@clock.tc_Request)
  EXEC.DeleteMsgPort(port)
  Require(shown<>0)

RETURN

PROC Main()

  LET warm=Load()
  Collected(Start(warm,BYTE POINTER(c"X")),-124)
  PROGRAM.Unload(warm)
  baseline=EXEC.AvailMem(0)
  LET image=Load()
  LET child=Start(image,BYTE POINTER(c"S"))
  Require(child<>0)
  WindowReady()
  Require(PROCESS.RequestStop(child)<>0)
  PROGRAM.Unload(image)
  Collected(child,-124)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
        completed=2
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=sources,app_options=options,
                       native_optimize=True,release_compiler=True,fixture_source=fixture,
                       expected_completed=completed)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--group',choices=('abi','sources','runtime','stop'),required=True)
    p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--from-build',action='store_true',help='Reuse the matched emitted provider and rebuild the probe APP')
    p.add_argument('--focused-abi',action='store_true',help='Two ABI/return cycles in either C mode')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    result=abi(out,a.case=='opt',a.focused_abi,a.from_build) if a.group=='abi' else runtime(out,a.case=='opt',a.from_build,a.group=='stop') if a.group in ('runtime','stop') else inventory(out,a.case=='opt')
    print('QED native',a.group,a.case,'passed' if a.group!='sources' else 'inventoried',flush=True)
