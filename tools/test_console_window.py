#!/usr/bin/env python3
"""WB7: application-owned console, actual guest input and physical GUI control."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine


def prepare(out,reuse_provider=False):
    from build_c_program import build as application
    from build_bitmap_console import drawing,prepare as launcher
    from build_fastbasic import build as fastbasic,compile_program
    from c_program import ABI,binding
    from generate_memory import PROFILE
    from make_data_disk import make
    out.mkdir(parents=True,exist_ok=True)
    if reuse_provider:
        app=json.loads((out/'app/app.json').read_text())
        require(app['abi']==ABI,'Stale console application ABI')
        for path,digest in app['inputs'].items():require(sha256(Path(path))==digest,'Changed APP source: '+path)
    else:app=application(out/'app',[ROOT/'tests/programs/console_window.c'])
    source,_=fastbasic(ROOT/'build/fastbasic')
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'CONTROL.APP').write_bytes((out/'app/program.app').read_bytes())
    for name,text in [('CWKEY','PRINT "NUMBER"\nINPUT A\nPRINT A\nPRINT "GET"\nGET K\nPRINT K\nPRINT "KEY"\nREPEAT\nUNTIL KEY()\nGET K\nPRINT K\nPRINT "BUSY"\nDO\nLOOP\n'),
                      ('CWREAD','PRINT "WAITING"\nINPUT A\nPRINT A\n')]:
        path=out/(name+'.bas');path.write_text(text)
        target=out/'compiled'/(name+'.COM')
        target.parent.mkdir(exist_ok=True)
        compile_program(source,path,target)
        (media/target.name).write_bytes(target.read_bytes())
    for path in media.iterdir():
        if path.name not in ('CONTROL.APP','CWKEY.COM','CWREAD.COM'):path.unlink()
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names={p.name for p in media.iterdir()})
    if reuse_provider:
        f=json.loads((out/'c-image.json').read_text())
        for path,digest in f['provenance']['source_inputs'].items():require(sha256(ROOT/path)==digest,'Changed provider: '+path)
    else:
        raw=out/'console-raw.c'
        text=(ROOT/'c/calypsi/console.c').read_text().replace(
            'void EXEC_PTR *ExecConsoleEntries[5];','extern void EXEC_PTR *ExecConsoleEntries[5];')
        for name in ('Create','Destroy','Mode','GetMode'):text=text.replace('ExecConsole'+name,'ConsoleRaw'+name)
        raw.write_text(text)
        f=drawing(out,True,widgets=True,client_sources=[ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',
            ROOT/'c/calypsi/aes-events.c',ROOT/'c/calypsi/program.c',raw,ROOT/'tests/programs/console_calls.c'],
            client_roots=['ExecProgramRun','CWABIProbe','CWABIChecks',*ABI['imports']],
            client_optimization={'console-raw.c':False})
    binding(f,out)
    sy=app['image']['symbols'];base=ABI['link_bank']<<16
    reads='\n'.join('    '+line for line in [
        f'LET pointer{name}=CARD POINTER(ADDRESS(appBase+${sy["CW"+name]-base:x}))'
        for name in ('Checks','Stage','Saves','Stopped')])
    native=out/'probe.act';body=('''MODULE CONSOLEWINDOWTEST
USE EXEC
USE DOS
USE PROGRAM
USE PROGRAMFILE
USE PROGRAMLOAD
USE PROGRAMIMAGE
USE PROCESS
USE AESSTATE
USE AESCORE
USE HEAPCORE
USE CALYPSICALL
CARD checks,stage,cycle,observedChecks,observedStage,observedSaves,observedStopped
LONGCARD appBase,identity,baseline,peerProgress
LONGINT primary,secondary,abiResult
BYTE peerDone
PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fba0+checks)
  FI
  checks==+1

RETURN

LONGINT FUNC Peer()

  WHILE peerDone=0 DO
    peerProgress==+1
    EXEC.Yield()
  OD

RETURN(0)

PROC Main()
  PROCESS.Result result

  abiResult=CALYPSICALL.Invoke(ADDRESS($CWABIPROBE),0)
  Require(abiResult=0)
  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  LET peerId=PROCESS.StartBackground(@Peer,NULL,0)
  Require(peerId<>0)
  LET warm=PROGRAMFILE.Load(BYTE POINTER(c"SYS:CONTROL.APP"))
  Require(warm<>NULL)
  PROGRAM.Unload(warm)
  baseline=EXEC.AvailMem(0)
  FOR cycle=0 TO 1 DO
  BEGIN
    LET image=PROGRAMFILE.Load(BYTE POINTER(c"SYS:CONTROL.APP"))
    Require(image<>NULL)
    appBase=LONGCARD(ADDRESS(image.text))
    identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
    Require(identity<>0)
    stage=1
    Require(PROCESS.Wait(identity,@result)<>0)
    primary=result.primary
    secondary=result.secondary
'''+reads+'''
    observedChecks=pointerChecks^
    observedStage=pointerStage^
    observedSaves=pointerSaves^
    observedStopped=pointerStopped^
    Require(primary=0 AND secondary=0)
    Require(observedChecks>=90 AND observedStage=5)
    PROGRAM.Unload(image)
    LET service=AESSTATE.Get()
    WHILE AESCORE.Runnable(service)<>0 DO
      EXEC.Yield()
    OD
    Require(service.count=0 AND EXEC.AvailMem(0)=baseline)
    stage=2
  END
  OD
  peerDone=1
  Require(PROCESS.Wait(peerId,@result)<>0 AND result.primary=0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)
  stage=3

RETURN
ENDMODULE
''')
    native.write_text(body.replace('$CWABIPROBE','$%x'%f['symbols']['CWABIProbe']))
    native=launcher(native,out,f,desktop=True,aes=True)
    memory=out/'fixture-memory.json';profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192;memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),native,out/'program',tasks=True,task_capacity=8,
        foreign_image=f,console_deferred=True,memory_profile=memory,system_mount='D1',stack_checks=True,
        sdx=True,sdx_drive_a='RAM:',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2),dict(alias='RAM',format=3)])
    from generate_mouse_acceleration import metadata
    p['build']['desktop_mouse']=metadata(None)
    (p['output']/'build.json').write_text(json.dumps(p['build'],indent=2)+'\n')
    return p


def exercise(out):
    from console_window_interaction import exercise as physical
    return physical(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true');p.add_argument('--build-only',action='store_true')
    p.add_argument('--reuse-provider',action='store_true')
    a=p.parse_args();out=a.output.resolve()
    if not a.from_build:prepare(out,a.reuse_provider)
    if not a.build_only:exercise(out)
