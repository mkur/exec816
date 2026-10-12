#!/usr/bin/env python3
"""Small C/native exact-query bridge and loaded COMMAND provider probe."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine
from calypsi_build import emit
from library_paths import read_source
from build_command import compile_command
from make_data_disk import make
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_sio_device import PIN


def run(out, optimize):
    out.mkdir(parents=True, exist_ok=True)
    t = compiler(ROOT/'build/actionc', release=True)
    foreign = emit(out/'c', [ROOT/'tests/programs/directory_metadata_abi.c',
                           ROOT/'c/calypsi/dos.c'],
                   [ROOT/'c/calypsi/dos.s', ROOT/'c/calypsi/image-info.s'],
                   (), optimize, roots=['ExecDosEntries'])
    media = out/'media'; media.mkdir(exist_ok=True)
    (media/'CHECK').write_bytes(b'abc')
    command = out/'exact.act'
    command.write_text('''MODULE EXACTCOMMAND
USE COMMAND
COMMAND.FileInfoBlock info
LONGINT FUNC Main()

  LET lock=COMMAND.Lock(BYTE POINTER(c"D1:CHECK"),COMMAND.SHARED_LOCK)
  IF lock=NULL THEN
    RETURN(1)
  FI

  LET result=COMMAND.ExamineExact(lock,BYTE POINTER(@info))
  COMMAND.UnLock(lock)
  IF result=0 OR info.fib_Size<>3 OR
      info.fib_InfoFlags<>COMMAND.FIB_SIZE_EXACT+COMMAND.FIB_BLOCKS_EXACT THEN
    RETURN(2)
  FI

RETURN(0)
ENDMODULE
''')
    compile_command(t, command, out/'native/EXACT', optimize)
    (media/'EXACT').write_bytes((out/'native/EXACT').read_bytes())
    make(out/'data.atr', media, filesystem='sdfs', sector_bytes=256,
         sectors=2880, binary_names={'CHECK', 'EXACT'})
    binding = read_source(ROOT/'c/calypsi/dos-bridge.inc').split('; A launched command')[0]
    binding += 'PROC BindDos()\n  LET entries=ADDRESS POINTER($%x)\n' % foreign['symbols']['ExecDosEntries']
    for index, name in ((5,'CLock'),(6,'CUnLock'),(9,'DOS.IoErr'),(20,'CExamineExact')):
        binding += f'  entries({index})=ADDRESS(@{name})\n'
    binding += '\nRETURN\n'
    source = out/'probe.act'
    source.write_text('''MODULE DIRECTORYMETADATAABI
USE EXEC
USE DOS
USE PROGRAM
USE PROGRAMFILE
USE PROCESS
USE CALYPSICALL
'''+binding+'''
LONGINT result,commandResult
PROC Main()
  PROCESS.Result outcome
  LONGCARD identity

  BindDos()
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
  LET image=PROGRAMFILE.Load(BYTE POINTER(c"D1:EXACT"))
  IF image=NULL THEN
    commandResult=1
  ELSE
    identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
    commandResult=1
    IF identity<>0 AND PROCESS.Wait(identity,@outcome)<>0 THEN
      commandResult=outcome.primary
    FI
    PROGRAM.Unload(image)
  FI

  DOS.ReleaseContext()

RETURN
ENDMODULE
''' % foreign['symbols']['main'])
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 4352
    memory = out/'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    p = build(t, source, out/'program', tasks=True, task_capacity=8,
              foreign_image=foreign, optimize=optimize, console_deferred=True,
              kernel_bank=18, memory_profile=memory,
              dos_mounts=[dict(alias='D1', unit=49, sectors=2880,
                               sector_bytes=256, format=2, profile=4)],
              image_data=[(0x2dffe0, bytes([0xa5])*292)])
    rom = ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/altirra-sio-multi', rom, out, pin=PIN) as b:
        machine = verify_machine(b, rom, PIN)
        b.config('diskemu', 'generic56k'); b.mount(0, str(out/'data.atr'))
        runtime, _ = execute(b, p, timeout=240, frame_limit=12000)
        require(data(b, p['image'], 'result', True)==[0,0], 'C exact bridge failed')
        require(data(b, p['image'], 'commandResult', True)==[0,0], 'Loaded exact provider failed')
        from banked_test_memory import read
        require(read(b,0x2dffe0,16,out)==read(b,0x2dfff0+260,16,out)==bytes([0xa5])*16,
                'Far FIB guards changed')
        ownership(b,p,p['output'])
    result = dict(status='pass',tier='development',optimize=optimize,
                  runtime=runtime,machine=machine,build=p['build'],
                  c_layout=foreign['provenance']['checked_layout'],
                  bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),not args.raw)
