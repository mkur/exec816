#!/usr/bin/env python3
"""Emitted RAWCON cell/span behavior with counted public-write fault injection."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    screen=(ROOT/'lib/dos/sdxscreen.act').read_text()
    needle='sent=DOS.ConsoleIO(state.outputHandle,CONSOLETYPES.CONCMD_WRITE_CELL_SPANS,'
    require(screen.count(needle)==1,'Changed public span write boundary')
    screen=screen.replace('USE DOS\n','USE DOS\nUSE SCREENPROBE\n',1)
    screen=screen.replace(needle,'sent=SCREENPROBE.Write(state.outputHandle,CONSOLETYPES.CONCMD_WRITE_CELL_SPANS,')
    (out/'sdxscreen.act').write_text(screen)
    (out/'screenprobe.act').write_text('''MODULE SCREENPROBE
USE DOS
USE CONSOLETYPES
PUBLIC CARD calls,count
PUBLIC LONGCARD offset
PUBLIC BYTE failure
PUBLIC BYTE ARRAY model(2400)
PUBLIC LONGINT FUNC Write(DOS.FileHandle POINTER file BYTE command
    LONGCARD position BYTE POINTER cells LONGINT length)
  CONSOLETYPES.CellSpan POINTER span
  CARD at,index,limit

  calls==+1
  count=CARD(length)
  span=CONSOLETYPES.CellSpan POINTER(cells)
  offset=(LONGCARD(span.row) LSH 16) OR LONGCARD(span.column)
  at=0
  WHILE at<CARD(length) DO
    span=CONSOLETYPES.CellSpan POINTER(cells+SIZE(at))
    limit=span.length
    IF failure=1 AND at+10>=CARD(length) THEN
      limit=1
    ELSEIF failure=2 AND at+10>=CARD(length) THEN
      limit=0
      IF span.length>1 THEN
        limit=1
      FI
    FI
    IF limit<>0 THEN
      FOR index=0 TO limit-1 DO
        model(span.row*80+span.column+index)=span.data(index)
      OD
    FI
    at==+10
  OD
  IF failure=1 THEN
    DOS.SetIoErr(205)
    RETURN(-1)
  FI
  IF failure=2 THEN
    DOS.SetIoErr(304)
    RETURN(length-10)
  FI
  IF failure=3 THEN
    DOS.SetIoErr(205)
    RETURN(length)
  FI
  DOS.SetIoErr(0)

RETURN(length)
ENDMODULE
''')
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=16384
    memory=out/'memory-profile.json';memory.write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/sdx_screen.act',out,
            tasks=True,task_capacity=12,console=True,sdx=True,sio_enabled=False,
            dos_mounts=[dict(alias='RAM',format=3)],memory_profile=memory)
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        runtime,_=execute(b,p,timeout=90,frame_limit=4500)
        ownership(b,p,out)
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
    return dict(status='pass',tier='development',qualification=False,checks=checks,
                runtime=runtime,machine=machine,build=p['build'],
                injected_boundary='Synchronous public WRITE_CELL_SPANS: complete, hidden-prefix error, BREAK prefix and full-count late error',
                override_sha256=sha256(out/'sdxscreen.act'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:result=run(out)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RAWCON spans:',result['checks'],'checks passed')
