#!/usr/bin/env python3
"""Focused raw/optimized C and loaded COMMAND mount/unmount calls."""
import argparse
import json
import shutil
from pathlib import Path

from calypsi_build import emit
from build_command import compile_command
from library_paths import read_source
from make_data_disk import make
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(output, optimize):
    output.mkdir(parents=True, exist_ok=True)
    t = compiler(ROOT / 'build/actionc', release=True)
    foreign = emit(output / 'c', [ROOT / 'tests/programs/mount_api_abi.c',
                   ROOT / 'c/calypsi/dos.c'], [ROOT / 'c/calypsi/dos.s',
                   ROOT / 'c/calypsi/image-info.s'], (), optimize,
                   roots=['ExecDosEntries'])
    command = output / 'mountcmd.act'
    command.write_text('''MODULE MOUNTCOMMAND
USE COMMAND
COMMAND.SioMountSpec spec
LONGINT FUNC Main()

  spec.drive=2
  spec.format=COMMAND.MOUNT_MYDOS
  spec.profile=4
  spec.access=COMMAND.MOUNT_READONLY
  IF COMMAND.MountVolume(BYTE POINTER(c"CMDAPI"),BYTE POINTER(@spec))=0 THEN
    RETURN(1)
  FI

  LET lock=COMMAND.Lock(BYTE POINTER(c"CMDAPI:"),COMMAND.SHARED_LOCK)
  IF lock=NULL THEN
    RETURN(2)
  FI

  IF COMMAND.UnmountVolume(BYTE POINTER(c"CMDAPI"))<>0 OR
      COMMAND.IoErr()<>COMMAND.ERROR_OBJECT_IN_USE THEN
    RETURN(3)
  FI

  COMMAND.UnLock(lock)
  IF COMMAND.UnmountVolume(BYTE POINTER(c"CMDAPI"))=0 THEN
    RETURN(4)
  FI

RETURN(0)
ENDMODULE
''')
    compile_command(t, command, output / 'native/MOUNTCMD', optimize)
    contents = output / 'contents'; contents.mkdir(exist_ok=True)
    shutil.copyfile(output / 'native/MOUNTCMD', contents / 'MOUNTCMD')
    make(output / 'commands.atr', contents, filesystem='sdfs', sectors=720,
         sector_bytes=128, binary_names={'MOUNTCMD'})
    shutil.copyfile(ROOT / 'tests/fixtures/mydos/mydos450-128.atr', output / 'data.atr')
    binding = read_source(ROOT / 'c/calypsi/dos-bridge.inc')
    binding = f'CONST C_EXECDOSENTRIES=${foreign["symbols"]["ExecDosEntries"]:x}\n' + binding
    source = output / 'probe.act'
    source.write_text('''MODULE MOUNTBRIDGES
USE EXEC
USE DOS
USE PROGRAM
USE PROGRAMIMAGE
USE PROGRAMFILE
USE PROCESS
USE CALYPSICALL
USE FSBOOT
'''+binding+'''
LONGINT cResult,commandResult
BYTE finished
PROC Main()
  PROCESS.Result outcome

  LET baseline=EXEC.AvailMem(0)
  BindDos(0)
  FSBOOT.Ensure()
  cResult=CALYPSICALL.Invoke(ADDRESS($%x),0)
  LET image=PROGRAMFILE.Load(BYTE POINTER(c"D1:MOUNTCMD"))
  commandResult=20
  IF image<>NULL THEN
    BEGIN
      LET identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
      IF identity<>0 AND PROCESS.Wait(identity,@outcome)<>0 THEN
        commandResult=outcome.primary
      FI

      PROGRAM.Unload(image)
    END
  FI

  DOS.ReleaseContext()
  FSBOOT.Stop()
  IF EXEC.AvailMem(0)=baseline THEN
    finished=1
  FI

RETURN
ENDMODULE
''' % foreign['symbols']['main'])
    profile = json.loads((ROOT / 'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 4352
    memory = output / 'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    p = build(t, source, output / 'program', tasks=True, task_capacity=8,
              optimize=optimize, console_deferred=True, kernel_bank=18,
              foreign_image=foreign, memory_profile=memory,
              dos_mounts=[dict(alias='D1', unit=49, profile=4, format=2,
                               sectors=720, sector_bytes=128)])
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        for k, v in PIN['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        b.config('diskemu', 'generic56k')
        b.mount(0, str(output / 'commands.atr'))
        b.mount(1, str(output / 'data.atr'))
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=240, frame_limit=12000)
        require(data(b, p['image'], 'cResult', True) == [0, 0], 'C mount bridge failed')
        require(data(b, p['image'], 'commandResult', True) == [0, 0], 'COMMAND mount provider failed')
        require(data(b, p['image'], 'finished') == [1], 'Mount bridge leaked resources')
        ownership(b, p, p['output'])
    result = dict(status='pass', tier='development', optimize=optimize,
                  runtime=runtime, machine=machine, build=p['build'],
                  c_layout=foreign['provenance']['checked_layout'],
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output / 'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Mount bridges passed:', 'opt' if optimize else 'raw', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), not args.raw)
