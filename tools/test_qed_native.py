#!/usr/bin/env python3
"""Focused emitted-code checks for the native QED foundation."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from prepare_qed import inventory,prepare,PORT
from test_c_process import run as _process_run

def process_run(*args,**options):
    options.setdefault('observe_stacks',True)
    return _process_run(*args,**options)

def abi(out,optimize,focused=False,reuse=False,layout=False,masks=False):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/qed_native_abi.c'
    options=dict(includes=[PORT/'native'],definitions={source.name:['--char-is-unsigned']},probes=[(source,[
        ('huge pointer',4),('native pointer',3),('legacy word',2),('long',4),
        ('OBJECT',24),('OBJECT spec',12),('TEDINFO',28),
        ('size_t',2),('fpos_t',4),('time_t',8)])])
    sources=[source]
    if layout:
        native=PORT/'native'
        prepare(out/'inputs')
        cflib=out/'inputs/source/cflib'
        sources=[ROOT/'tests/programs/qed_native_layout.c',native/'support.c',native/'gem-helpers.c']
        sources += [cflib/'nkccinit.c',cflib/'nkccgton.c']
        options['definitions'][sources[0].name]=['-DQED_BAD_FORMAT='+str(
            json.loads((ROOT/'abi/program.json').read_text())['errors']['BAD_FORMAT'])]
        if optimize:options['definitions'][sources[0].name].append('-DQED_TEST_LIMITS=1')
        options['includes']=[native,cflib]
        assembly=[]
        for name in ('QedLayoutFirst','QedLayoutLast'):
            path=out/(name+'.s')
            path.write_text('              .section farcode,text\n              .public '+name+'\n'+
                            name+':\n              rtl\n              .space 65535\n')
            assembly.append(path)
        path=out/'QedLayoutTable.s'
        path.write_text('              .section gemtables,rodata\n              .public QedLayoutTable\n'+
                        'QedLayoutTable:\n              .word 0xabcd\n')
        assembly.append(path)
        options['extra_assembly']=assembly
        focused=True
    if masks:
        prepare(out/'inputs')
        native=PORT/'native';qed=out/'inputs/source/qed/src';cflib=out/'inputs/source/cflib'
        sources=[ROOT/'tests/programs/qed_native_masks.c',qed/'find.c',cflib/'nkccinit.c',cflib/'nkccuppr.c']
        options.update(includes=[native,qed,cflib],definitions={str(path):[
            '--char-is-unsigned','-DQED_INITIAL_SCOPE=1','--no-cross-call',
            '--no-interprocedural-cross-jump'] for path in sources})
        focused=True
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
    record=process_run(out,optimize,reuse=reuse,rebuild_app=reuse,app_sources=sources,app_options=options,
        fixture_source=fixture,expected_completed=completed,native_optimize=True,release_compiler=True,
        boundary_limits=layout and optimize)
    require(record['runtime']['native_nmi_count']>0 and record['runtime']['native_irq_count']>0,
            'QED ABI probe missed native asynchronous entries')
    if layout:
        app=json.loads((out/'app/app.json').read_text())
        require(4*65536<app['span']<=327680 and len(app['segments'])==6 and
                app['image']['symbols']['main']>>16==16,
                'Probe did not execute the newly admitted final code bank')
    return record


def runtime(out,optimize,reuse=False,stop=False):
    require(optimize,'The runtime ownership cohort uses optimized C; raw is reserved for ABI probes')
    prepare(out/'inputs')
    qed=out/'inputs/source/qed/src';cflib=out/'inputs/source/cflib'
    source=ROOT/'tests/programs/qed_native_runtime.c'
    native=PORT/'native'
    sources=[source,native/'allocation.c',native/'entry.c',native/'files.c',native/'library.c',qed/'memory.c']
    options=dict(includes=[native,qed,cflib],runtime_attributes={'printf':'nofloat'},definitions={
        path.name:['--char-is-unsigned','-DQED_BANKED_MALLOC=1',
                   '-Werror=implicit-function-declaration','--no-cross-call','--no-interprocedural-cross-jump']+
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
                       expected_completed=completed,stack_observation_index=1 if stop else 0)

def files(out,optimize,reuse=False,filesystem='sdfs'):
    require(optimize,'File/runtime behavior uses optimized C')
    out.mkdir(parents=True,exist_ok=True)
    native=PORT/'native';source=ROOT/'tests/programs/qed_native_files.c'
    sources=[source,native/'allocation.c',native/'entry.c',native/'files.c',native/'library.c']
    options=dict(includes=[native],runtime_attributes={'printf':'nofloat'},probes=[(source,[('size_t',2),('fpos_t',4),('time_t',8),('BPTR',4)])],
        definitions={path.name:['--char-is-unsigned','-Werror=implicit-function-declaration','--no-cross-call','--no-interprocedural-cross-jump']+
            (['-DAllocMem=QedFixtureAlloc'] if path.name=='allocation.c' else [])+
            (['-DClose=QedFixtureClose','-DWrite=QedFixtureWrite'] if path.name=='files.c' else [])
            for path in sources})
    fixture=out/'qed-files.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    prefix=prefix.replace('LONGINT lastPrimary','LONGINT lastPrimary,lastSecondary')
    fixture.write_text(prefix+'''
PROC FileCollected(LONGCARD id LONGINT primary,secondary)
  PROCESS.Result result

  Require(id<>0)
  Require(PROCESS.Wait(id,@result)<>0)
  lastPrimary=result.primary
  lastSecondary=result.secondary
  Require(result.primary=primary)
  Require(result.secondary=secondary)
  completed==+1

RETURN

PROC Main()

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET previousInput=DOS.SelectInput(input)
  LET previousOutput=DOS.SelectOutput(output)
  LET directory=DOS.Lock(BYTE POINTER(c"SYS:"),DOS.SHARED_LOCK)
  Require(directory<>NULL)
  LET previousDirectory=DOS.CurrentDir(directory)
  LET image=Load()
  FileCollected(Start(image,BYTE POINTER(c"X")),-321,0)
  baseline=EXEC.AvailMem(0)
  FileCollected(Start(image,BYTE POINTER(c"X")),-321,0)
  Require(EXEC.AvailMem(0)=baseline)
  PROGRAM.Unload(image)
  baseline=EXEC.AvailMem(0)
  LET failed=Load()
  LET child=Start(failed,BYTE POINTER(c"E"))
  PROGRAM.Unload(failed)
  FileCollected(child,20,DOS.ERROR_DISK_FULL)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.CurrentDir(previousDirectory)=directory)
  DOS.UnLock(directory)
  DOS.SelectInput(previousInput)
  DOS.SelectOutput(previousOutput)
  Require(DOS.Close(input)<>0)
  Require(DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    record=process_run(out,True,reuse=reuse,rebuild_app=reuse,filesystem=filesystem,
        app_sources=sources,app_options=options,fixture_source=fixture,expected_completed=3,
        native_optimize=True,release_compiler=True,writable=True,ram=True)
    from filesystem_audit import Audit
    audit=Audit((out/'system.atr').read_bytes());report=getattr(audit,filesystem)()
    require(audit.files['SAVED.BIN']==bytes([97,128,255,13,10,98,0,99,10]),
            'Persisted native QED fixture bytes changed')
    record['persisted_file']=dict(name='SAVED.BIN',bytes=9,audit=report)
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

def admission(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    fixture=out/'qed-admission.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+'''
PROC Main()
  BYTE slot,index
  EXEC.Task POINTER task
  LONGCARD nextIdentity,available

  LET small=PROGRAMFILE.Load(BYTE POINTER(c"SYS:SMALL.APP"))
  Require(small<>NULL AND small.minimumStack=0)
  LET ordinary=Start(small,BYTE POINTER(c"B"))
  Require(ordinary<>0)
  LET table=PROCESSSTATE.Registry()
  slot=0
  FOR index=1 TO PROCESSSTATE.CAPACITY-1 DO
    IF table.entries(index).identity=ordinary THEN
      slot=index
    FI
  OD

  task=EXEC.Task POINTER(@table.entries(slot).task(0))
  Require(slot<>0 AND task.tc_SPUpper-task.tc_SPLower=1312)
  Collected(ordinary,-124)
  PROGRAM.Unload(small)
  baseline=EXEC.AvailMem(0)

  LET image=Load()
  LET other=Load()
  Require(image.minimumStack=2560)
  LET first=Start(image,BYTE POINTER(c"B"))
  Require(first<>0)
  slot=0
  FOR index=1 TO PROCESSSTATE.CAPACITY-1 DO
    IF table.entries(index).identity=first THEN
      slot=index
    FI
  OD

  task=EXEC.Task POINTER(@table.entries(slot).task(0))
  Require(slot<>0 AND task.tc_SPUpper-task.tc_SPLower=2560)
  nextIdentity=table.nextIdentity
  available=EXEC.AvailMem(0)
  Require(Start(other,BYTE POINTER(c"F"))=0)
  Require(DOS.IoErr()=DOS.ERROR_NO_FREE_STORE)
  Require(other.running=0 AND other.references=1)
  Require(table.nextIdentity=nextIdentity AND EXEC.AvailMem(0)=available)
  Collected(first,-124)
  PROGRAM.Unload(image)
  Collected(Start(other,BYTE POINTER(c"F")),-321)
  PROGRAM.Unload(other)
  Require(EXEC.AvailMem(0)=baseline)

  LET tall=PROGRAMFILE.Load(BYTE POINTER(c"SYS:TALL.APP"))
  Require(tall<>NULL AND tall.minimumStack=3008)
  nextIdentity=table.nextIdentity
  available=EXEC.AvailMem(0)
  Require(Start(tall,BYTE POINTER(c"F"))=0)
  Require(DOS.IoErr()=DOS.ERROR_NO_FREE_STORE)
  Require(tall.running=0 AND tall.references=1)
  Require(table.nextIdentity=nextIdentity AND EXEC.AvailMem(0)=available)
  PROGRAM.Unload(tall)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    source=out/'qed-admission.c'
    source.write_text((ROOT/'tests/programs/c_process.c').read_text().replace(
        '    if (strcmp(FindTask(NULL)->tc_Node.ln_Name,"PROBE.APP")) return 56;\n','').replace(
        '    if (strcmp(FindTask(NULL)->tc_Node.ln_Name,"PROBE.APP")) return 57;\n',''))
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=[source],
        app_options=dict(minimum_stack=2560),fixture_source=fixture,expected_completed=3,
        native_optimize=True,release_compiler=True,stack_media=True,observe_stacks=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--group',choices=('abi','layout','sources','runtime','stop','files','admission','masks'),required=True)
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--from-build',action='store_true',help='Reuse the matched emitted provider and rebuild the probe APP')
    p.add_argument('--focused-abi',action='store_true',help='Two ABI/return cycles in either C mode')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if a.group in ('abi','layout','masks'):result=abi(out,a.case=='opt',a.focused_abi,a.from_build,a.group=='layout',a.group=='masks')
    elif a.group in ('runtime','stop'):result=runtime(out,a.case=='opt',a.from_build,a.group=='stop')
    elif a.group=='admission':result=admission(out,a.from_build)
    elif a.group=='files':result=files(out,a.case=='opt',a.from_build,a.filesystem)
    else:result=inventory(out,a.case=='opt')
    print('QED native',a.group,a.case,'passed' if a.group!='sources' else 'inventoried',flush=True)
