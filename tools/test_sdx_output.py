#!/usr/bin/env python3
"""Emitted SDX output: fragments, capacity, prompts, discard and failure cleanup."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN
import sdx_fixtures


def fixture(output, write_error):
    module = sdx_fixtures.assemble(output, 'output')
    (output/'sdxoutputprobe.act').write_text('''MODULE SDXOUTPUTPROBE
USE EXEC
USE HEAPCORE
USE CONSOLEDRIVER
USE CONSOLECORE
PUBLIC CARD calls

PUBLIC PROC BeforeKey()

  LET terminal=CONSOLEDRIVER.GetInstance()
  IF terminal.row<>7 OR terminal.column<>29 OR
      terminal.cells(CONSOLECORE.CellOffset(terminal,303))<>': OR
      terminal.cells(CONSOLECORE.CellOffset(terminal,307))<>'? THEN
    HEAPCORE.Abort($fae0)
  FI
  calls==+1

RETURN
ENDMODULE
''')
    # Observe the console before the ordinary read, without replacing it.
    files=(ROOT/'lib/dos/sdxfiles.act').read_text().replace('USE DOS\n','USE DOS\nUSE SDXOUTPUTPROBE\n',1)
    needle='  got=DOS.Read(DOS.Input(),@state.character,1)'
    require(files.count(needle)==1, 'Guest-key read changed')
    # Redirected output has no console prompt to observe.
    files=files.replace(needle,'  IF state.outputInteractive<>0 THEN\n'
        '    SDXOUTPUTPROBE.BeforeKey()\n  FI\n'+needle)
    (output/'sdxfiles.act').write_text(files)
    if write_error:
        text=(ROOT/'lib/dos/sdxprint.act').read_text()
        needle='    IF sent<=0 THEN'
        require(text.count(needle)==1, 'Native output write changed')
        text=text.replace(needle,'    DOS.SetIoErr(223)\n    sent=-1\n'+needle)
        (output/'sdxprint.act').write_text(text)
    calls='  Launch(1,0,20,223)\n' if write_error else '''  Launch(1,0,0,0)
  Launch(1,1,20,170)
  Launch(0,0,0,0)
  Discard()
'''
    source=output/'probe.act'
    source.write_text('''MODULE SDXOUTPUTTEST
USE EXEC
USE DOS
USE DOSCLIENT
USE HEAPCORE
USE PROCESS
USE PROGRAM
USE PROGRAMIMAGE
USE SDXSTATE
USE SDXPRINT
USE SDXABI
USE SDXOUTPUTPROBE
USE CONSOLEDRIVER
USE CONSOLECORE
USE FSBOOT

CARD checks,currentCase
LONGINT primary,secondary,reason
BYTE ARRAY raw(320),frame(14),prompt=[58 107 101 121 63 32]

PROC Check(BYTE okay)

  IF okay=0 THEN
    reason=DOS.IoErr()
    HEAPCORE.Abort($fa00+checks)
  FI
  checks==+1

RETURN

PROC Launch(BYTE interactive,failed LONGINT wantPrimary,wantSecondary)
  DOS.FileHandle POINTER console,input,output,previousInput,previousOutput,file
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  PROCESS.Result result
  LONGCARD identity
  CARD index
  BYTE POINTER arguments

  currentCase=checks
  SDXOUTPUTPROBE.calls=0
  console=DOS.Open(BYTE POINTER(c"CON:"),DOS.MODE_READWRITE)
  Check(console<>NULL)
  raw(0)=12
  Check(DOS.Write(console,@raw,1)=1)
  file=DOS.Open(BYTE POINTER(c"RAM:KEY"),DOS.MODE_NEWFILE)
  Check(file<>NULL)
  raw(0)='Y
  Check(DOS.Write(file,@raw,1)=1 AND DOS.Close(file)<>0)
  input=DOS.Open(BYTE POINTER(c"RAM:KEY"),DOS.MODE_OLDFILE)
  Check(input<>NULL)
  output=console
  IF interactive=0 THEN
    output=DOS.Open(BYTE POINTER(c"RAM:OUTPUT"),DOS.MODE_NEWFILE)
    Check(output<>NULL)
  FI
  previousInput=DOS.SelectInput(input)
  previousOutput=DOS.SelectOutput(output)
  image=PROGRAM.Load(BYTE POINTER(ADDRESS($300000)),MODULE_BYTES)
  Check(image<>NULL)
  state=SDXSTATE.Session POINTER(image.extension)
  arguments=BYTE POINTER(c"")
  IF failed<>0 THEN
    arguments=BYTE POINTER(c"F")
  FI
  identity=PROCESS.StartLoaded(BYTE POINTER(image),arguments,LONGCARD(failed),0)
  Check(identity<>0)
  Check(PROCESS.Wait(identity,@result)<>0)
  primary=result.primary
  secondary=result.secondary
  Check(primary=wantPrimary AND secondary=wantSecondary)
  Check(state.outputUsed=0 AND state.outputInteractive=interactive)
  Check(state.trapCount=0 AND state.overlayActive=0)
  IF wantSecondary=223 THEN
    Check(SDXOUTPUTPROBE.calls=0)
  ELSE
    Check(state.bank($500)='Y)
    IF interactive<>0 THEN
      BEGIN
        LET terminal=CONSOLEDRIVER.GetInstance()
        Check(SDXOUTPUTPROBE.calls=1)
        Check(terminal.row=8 AND terminal.column=4)
        Check(terminal.cells(CONSOLECORE.CellOffset(terminal,0))='A AND
            terminal.cells(CONSOLECORE.CellOffset(terminal,1))='B AND
            terminal.cells(CONSOLECORE.CellOffset(terminal,2))='C)
        FOR index=3 TO 302 DO
          Check(terminal.cells(CONSOLECORE.CellOffset(terminal,index))='x)
        OD
        Check(terminal.cells(CONSOLECORE.CellOffset(terminal,309))='Y)
        Check(terminal.cells(CONSOLECORE.CellOffset(terminal,320))='t AND
            terminal.cells(CONSOLECORE.CellOffset(terminal,323))='l)
      END
    FI
  FI
  PROGRAM.Unload(image)
  DOS.SelectInput(previousInput)
  DOS.SelectOutput(previousOutput)
  Check(DOS.Close(input)<>0)
  IF interactive=0 THEN
    Check(DOS.Close(output)<>0)
    file=DOS.Open(BYTE POINTER(c"RAM:OUTPUT"),DOS.MODE_OLDFILE)
    Check(file<>NULL)
    Check(DOS.Read(file,@raw,320)=315 AND DOS.Close(file)<>0)
    Check(raw(0)='A AND raw(1)='B AND raw(2)='C)
    FOR index=3 TO 302 DO
      Check(raw(index)='x)
    OD
    FOR index=0 TO 5 DO
      Check(raw(303+index)=prompt(index))
    OD
    Check(raw(309)='Y AND raw(310)=$9b AND raw(311)='t AND raw(314)='l)
  FI
  Check(DOS.Close(console)<>0)
  SDXSTATE.Guards()

RETURN

PROC Discard()
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  DOS.FileHandle POINTER console,previous

  image=PROGRAM.Load(BYTE POINTER(ADDRESS($300000)),MODULE_BYTES)
  Check(image<>NULL)
  state=SDXSTATE.Session POINTER(image.extension)
  console=DOS.Open(BYTE POINTER(c"CON:"),DOS.MODE_READWRITE)
  Check(console<>NULL)
  previous=DOS.SelectOutput(console)
  SDXPRINT.Begin(state)
  Check(SDXPRINT.Character(state,'A)=0 AND state.outputUsed=1)
  state.bank($5000)='D
  state.bank($5001)=$9b
  state.bank($5002)=0
  SDXSTATE.Word(@frame,SDXABI.FRAME_PC,$5000)
  state.discardOutput=1
  Check(SDXPRINT.Print(state,@frame)=0 AND state.outputUsed=1)
  state.discardOutput=0
  Check(SDXPRINT.Character(state,'B)=0 AND state.outputUsed=2)
  Check(SDXPRINT.Character(state,$9b)=0 AND state.outputUsed=0)
  DOS.SelectOutput(previous)
  Check(DOS.Close(console)<>0)
  PROGRAM.Unload(image)

RETURN

PROC Main()

  LET baseline=EXEC.AvailMem(0)
RUN_CASES
  Check(DOS.DeleteFile(BYTE POINTER(c"RAM:KEY"))<>0)
  IF DOS.DeleteFile(BYTE POINTER(c"RAM:OUTPUT"))=0 THEN
    Check(DOS.IoErr()=DOS.ERROR_OBJECT_NOT_FOUND)
  FI
  Check(DOS.ReleaseContext()<>0)
  Check(FSBOOT.Stop()<>0)
  Check(EXEC.AvailMem(0)=baseline)

RETURN
ENDMODULE
'''.replace('MODULE_BYTES',str(len(module['bytes']))).replace('RUN_CASES',calls))
    return source, [(0x300000,module['bytes'])]


def test(output, write_error=False):
    output.mkdir(parents=True,exist_ok=True)
    source,payload=fixture(output,write_error)
    original=sdx_fixtures.generate
    # Admit this source-audited probe only in this development fixture.
    with patch.object(sdx_fixtures,'generate',
            lambda out: original(out,('process','services','fail','options','console','rethrow','output'))):
        program=build(compiler(ROOT/'build/actionc',release=True),source,output,
            tasks=True,task_capacity=8,console=True,console_test=True,sdx=True,
            image_data=payload,dos_mounts=[dict(alias='RAM',format=3)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try: runtime,_=execute(b,program,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ('checks','currentCase','primary','secondary','reason')},flush=True)
            raise
        ownership(b,program,output)
        checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
    result=dict(status='pass',tier='development',qualification=False,checks=checks,
        write_error=write_error,runtime=runtime,machine=machine,build=program['build'],
        overrides={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (output/'sdxfiles.act',output/'sdxprint.act') if p.exists()})
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDX output:',checks,'checks passed; write_error=',write_error,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--write-error',action='store_true')
    args=parser.parse_args()
    test(args.output.resolve(),args.write_error)
