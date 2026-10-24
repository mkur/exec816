#!/usr/bin/env python3
"""P3 SDX file loading and ordinary Process ownership on the pinned platform."""
import argparse
import json
from pathlib import Path
import time

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from sdx_fixtures import assemble
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def fixture(out):
    module=assemble(out,'process')
    source=out/'probe.act'
    source.write_text('''MODULE SDXPROCESSPROBE
USE EXEC
USE DOS
USE DOSCLIENT
USE PROCESS
USE PROGRAM
USE PROGRAMFILE
USE PROGRAMIMAGE
USE SDXSTATE
USE SDXRUNTIME
USE HEAPCORE
USE FSBOOT

CARD checks
LONGINT reason
LONGCARD peer

PROC Require(BYTE okay)

  IF okay=0 THEN
    reason=DOS.IoErr()
    HEAPCORE.Abort($fa00+checks)
  FI
  checks==+1

RETURN

PROC Main()
  PROGRAMIMAGE.Image POINTER first,second,third
  DOS.FileHandle POINTER file,output,previous
  SDXSTATE.Session POINTER one,two
  PROCESS.Result result
  LONGCARD firstId,secondId,baseline
  BYTE POINTER bytes
  BYTE saved
  CARD round

  baseline=EXEC.AvailMem(0)
  bytes=BYTE POINTER(ADDRESS($240000))
  file=DOS.Open(BYTE POINTER(c"RAM:PROBE.COM"),DOS.MODE_NEWFILE)
  Require(file<>NULL)
  Require(DOS.Write(file,bytes,MODULE_BYTES)=MODULE_BYTES)
  Require(DOS.Close(file)<>0)
  output=DOS.Open(BYTE POINTER(c"RAM:OUT.TXT"),DOS.MODE_NEWFILE)
  Require(output<>NULL)
  previous=DOS.SelectOutput(output)
  FOR round=0 TO 2 DO
    first=PROGRAMFILE.Load(BYTE POINTER(c"RAM:PROBE.COM"))
    Require(first<>NULL)
    second=PROGRAM.Load(bytes,MODULE_BYTES)
    Require(second<>NULL)
    one=SDXSTATE.Session POINTER(first.extension)
    two=SDXSTATE.Session POINTER(second.extension)
    Require(one.slot<>two.slot AND first.text<>second.text)
    Require(one.bank($3000)=$ea AND two.bank($3000)=$ea)
    Require(PROGRAM.Load(bytes,MODULE_BYTES)=NULL)
    Require(DOS.IoErr()=308)
    ; Invalid arguments must roll back Attach without making the Image busy.
    Require(PROCESS.StartLoaded(BYTE POINTER(first),NULL,1,0)=0)
    Require(first.running=0 AND first.references=1)
    ; A held lease makes native child startup succeed but guest entry fail.
    Require(SDXRUNTIME.Acquire(CARD(one.slot))=1)
    firstId=PROCESS.StartLoaded(BYTE POINTER(first),NULL,0,0)
    Require(firstId<>0)
    secondId=PROCESS.StartLoaded(BYTE POINTER(second),NULL,0,0)
    Require(secondId<>0)
    Require(PROCESS.StartLoaded(BYTE POINTER(first),NULL,0,0)=0)
    Require(PROCESS.Wait(firstId,@result)<>0)
    Require(result.primary=20 AND result.secondary=202)
    Require(PROCESS.Wait(secondId,@result)<>0)
    Require(result.primary=20 AND result.secondary=202)
    SDXRUNTIME.Release()
    firstId=PROCESS.StartLoaded(BYTE POINTER(first),NULL,0,0)
    Require(firstId<>0)
    PROGRAM.Unload(first)
    ; The live child and the other loaded Image retain both private DP slots.
    Require(PROGRAM.Load(bytes,MODULE_BYTES)=NULL)
    peer==+1
    Require(PROCESS.Wait(firstId,@result)<>0)
    Require(result.primary=7 AND result.secondary=0)
    secondId=PROCESS.StartLoaded(BYTE POINTER(second),NULL,0,0)
    Require(secondId<>0)
    PROGRAM.Unload(second)
    Require(PROCESS.Wait(secondId,@result)<>0)
    Require(result.primary=7 AND result.secondary=0)
    third=PROGRAM.Load(bytes,MODULE_BYTES)
    Require(third<>NULL)
    IF round=2 THEN
      firstId=PROCESS.StartLoaded(BYTE POINTER(third),NULL,0,0)
      Require(firstId<>0)
      Require(PROCESS.Wait(firstId,@result)<>0 AND result.primary=7)
      firstId=PROCESS.StartLoaded(BYTE POINTER(third),NULL,0,0)
      Require(firstId<>0)
      Require(PROCESS.Wait(firstId,@result)<>0 AND result.primary=7)
    FI
    PROGRAM.Unload(third)
  OD
  saved=bytes(MODULE_BYTES-1)
  bytes(MODULE_BYTES-1)=saved XOR 1
  Require(PROGRAM.Load(bytes,MODULE_BYTES)=NULL)
  Require(DOS.IoErr()=307)
  bytes(MODULE_BYTES-1)=saved
  Require(PROGRAM.Load(bytes,MODULE_BYTES-1)=NULL)
  DOS.SelectOutput(previous)
  Require(DOS.Close(output)<>0)
  file=DOS.Open(BYTE POINTER(c"RAM:OUT.TXT"),DOS.MODE_OLDFILE)
  Require(file<>NULL)
  Require(DOS.Seek(file,0,DOS.OFFSET_END)=0)
  Require(DOS.Seek(file,0,DOS.OFFSET_CURRENT)=96)
  Require(DOS.Close(file)<>0)
  Require(DOS.DeleteFile(BYTE POINTER(c"RAM:OUT.TXT"))<>0)
  Require(DOS.DeleteFile(BYTE POINTER(c"RAM:PROBE.COM"))<>0)
  SDXSTATE.Guards()
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)

RETURN

ENDMODULE
'''.replace('MODULE_BYTES',str(len(module['bytes']))))
    return source,[(0x240000,module['bytes'])]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--return-probe',type=int,choices=(0,1,7,8),default=0)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running');started=time.monotonic()
    try:
        source,payload=fixture(out)
        program=build(compiler(ROOT/'build/actionc',release=True),source,out,
                      tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,sdx_return_probe=args.return_probe,image_data=payload,dos_mounts=[dict(alias='RAM',format=3)])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:
                runtime,_=execute(b,program,timeout=180,frame_limit=9000)
            except Exception:
                print('Process checks:',data(b,program['image'],'checks'),
                      'reason:',data(b,program['image'],'reason'),flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
        result=dict(status='pass',tier='development',checks=checks,runtime=runtime,
                    machine=machine,build=program['build'])
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDX Process:',checks,'checks passed',flush=True)


if __name__=='__main__':
    main()
