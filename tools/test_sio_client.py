#!/usr/bin/env python3
"""Focused raw/optimized client records and a real loaded SIO library consumer."""
import argparse
import json
import shutil
from pathlib import Path
from fujinet_peer import make_peer
from build_command import compile_command
from make_data_disk import make
from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_sio_device import PIN


def run(output, optimize=True, loaded=False, no_sio=False, lifetime=False):
    output.mkdir(parents=True, exist_ok=True)
    t = compiler(ROOT / 'build/actionc', release=True)
    peer = make_peer(output / 'peer', discovery=False)
    source = ROOT / 'tests/programs/sio_client.act'
    mounts = []
    if lifetime:
        source = ROOT / 'tests/programs/sio_client_lifetime.act'
    if no_sio:
        source = output / 'no-sio.act'
        source.write_text('''MODULE SIONOTAVAILABLE
USE EXEC
USE SIO
USE SIOCLIENT
SIO.Session session
BYTE completed
PROC Main()
LET baseline=EXEC.AvailMem(0)
LET error=SIOCLIENT.Open($70,1,BYTE POINTER(@session))
IF error=EXEC.IOERR_OPENFAIL AND EXEC.AvailMem(0)=baseline THEN
completed=1
FI
RETURN
ENDMODULE
''')
    if loaded:
        command = output / 'siocmd.act'
        command.write_text('''MODULE SIOCOMMAND
USE SIO
USE COMMAND
SIO.Session session
SIO.Transaction transaction
BYTE ARRAY payload(304)
LONGINT FUNC Main()
CARD index
IF SIO.Open($70,1,BYTE POINTER(@session))<>0 THEN RETURN(1) FI
transaction.command=1
transaction.aux1=48
transaction.aux2=1
transaction.direction=1
transaction.profile=5
transaction.length=304
transaction.data=payload
LET error=SIO.Transfer(BYTE POINTER(@session),BYTE POINTER(@transaction))
SIO.Close(BYTE POINTER(@session))
IF error<>0 OR transaction.actual<>304 THEN RETURN(2) FI
FOR index=0 TO 303 DO
IF payload(index)<>BYTE(index*37+11) THEN RETURN(3) FI
OD
RETURN(0)
ENDMODULE
''')
        compile_command(t, command, output / 'commands/SIOCMD', optimize)
        contents = output / 'contents'; contents.mkdir(exist_ok=True)
        shutil.copyfile(output / 'commands/SIOCMD', contents / 'SIOCMD')
        make(output / 'commands.atr', contents, filesystem='sdfs', sectors=720,
             sector_bytes=128, binary_names={'SIOCMD'})
        source = output / 'loaded.act'
        source.write_text('''MODULE SIOLOADEDTEST
USE EXEC
USE DOS
USE PROGRAM
USE PROGRAMFILE
USE PROCESS
USE FSBOOT
PROCESS.Result outcome
BYTE completed
PROC Main()
LET baseline=EXEC.AvailMem(0)
LET image=PROGRAMFILE.Load(BYTE POINTER(c"SYS:SIOCMD"))
IF image<>NULL THEN
BEGIN
LET identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
IF identity<>0 AND PROCESS.Wait(identity,@outcome)<>0 THEN
IF outcome.primary=0 THEN completed=1 FI
FI
PROGRAM.Unload(image)
END
FI
DOS.ReleaseContext()
FSBOOT.Stop()
IF EXEC.AvailMem(0)<>baseline THEN completed=0 FI
RETURN
ENDMODULE
''')
        mounts = [dict(alias='D1', unit=49, profile=4, format=2,
                       sectors=720, sector_bytes=128)]
    memory = None
    if loaded or lifetime:
        profile = json.loads((ROOT / 'platform/altirraos/memory-4m.json').read_text())
        profile['image_data_bytes'] = 4352
        memory = output / 'memory.json'
        memory.write_text(json.dumps(profile, indent=2) + '\n')
    p = build(t, source, output / 'program', optimize=optimize, tasks=True,
              task_capacity=8, console_deferred=not lifetime, console=lifetime, dos_mounts=mounts,
              system_mount='D1' if loaded else None, sio_enabled=not no_sio,
              memory_profile=memory)
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        if not no_sio:
            b.device_set('custom', path=str(peer))
        for k, v in PIN['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        if loaded:
            b.config('diskemu', 'generic56k'); b.mount(0, str(output / 'commands.atr'))
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, p, timeout=180, frame_limit=9000)
        except Exception:
            if lifetime:
                print({name: data(b, p['image'], name, name in ('checks', 'oom1', 'oom2'))
                       for name in ('checks', 'oom1', 'oom2', 'free1', 'free2', 'stage', 'same1', 'same2', 'expectedFree', 'restoredFree', 'localAfter', 'same3')}, flush=True)
            raise
        require(data(b, p['image'], 'completed') == [1], 'Client fixture incomplete')
        ownership(b, p, output / 'program')
        checks = None if loaded or no_sio else data(b, p['image'], 'checks', True)[0]
    return dict(status='pass', tier='development', mode='opt' if optimize else 'raw',
                loaded=loaded, sio_enabled=not no_sio, checks=checks, build=p['build'],
                runtime=runtime, machine=machine, peer_sha256=sha256(peer))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw', action='store_true')
    parser.add_argument('--loaded', action='store_true')
    parser.add_argument('--no-sio', action='store_true')
    parser.add_argument('--lifetime', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), not args.raw, args.loaded, args.no_sio, args.lifetime)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('SIO client passed', result['mode'], 'loaded' if args.loaded else 'native', result['checks'])
