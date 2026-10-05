#!/usr/bin/env python3
"""Focused emitted AES protocol, presenter and C application checks."""
import argparse
import json
from pathlib import Path

from build_bitmap_console import drawing, prepare
from generate_aes_server import ABI, expected_layout, files, layout
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def context_program(out, optimize):
    out.mkdir(parents=True, exist_ok=True)
    for path, content in files().items():
        require(path.read_text() == content, 'Stale AES output: '+str(path))
    # Keep the existing renderer optimized in both small ABI probes. A raw
    # whole-desktop C image exceeds its existing code bank; the code under
    # test and native bridge are independently exercised raw and optimized.
    foreign = drawing(out, True, probe=True, widgets=True,
        client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'tests/programs/aes_context.c'],
        client_entries=['AESClientOne', 'AESClientTwo'],
        client_roots=['AESContextProbe', 'AESWireProbe', 'AESProbePacket',
                      'AESChecks', 'AESFailures'],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())],
        client_optimization={n: optimize for n in ('aes.c', 'aes_context.c')})
    sy = foreign['symbols']
    checks = ['  Require(SIZEOF(AESTYPES.Request)=AESTYPES.REQUEST_SIZE)']
    for field, kind, *counts in ABI['records']['Request']:
        access = field+'(0)' if counts else field
        checks += [f'  Require(ADDRESS(@packet.{access})-ADDRESS(packet)={layout()["Request"]["fields"][field]})']
    source = out/'context.act'
    source.write_text('''MODULE AESPROBE
USE EXEC
USE AESTYPES
USE HEAPCORE
USE CONSOLEBITMAP
CARD checks,result
CARD FUNC POINTER cProbe()

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fc00+checks)
  FI

  checks==+1

RETURN

PROC Main()
  CARD index
  LONGCARD location

  LET memory=EXEC.AllocMem(LONGCARD(131072),EXEC.MEMF_LINEAR)
  Require(memory<>NULL)
  location=(LONGCARD(ADDRESS(memory)) & $ffff0000)+$ffc0
  IF location<LONGCARD(ADDRESS(memory)) THEN
    location==+$10000
  FI

  LET packet=AESTYPES.Request POINTER(ADDRESS(location))
'''+ '\n'.join(checks)+f'''
  LET packetAddress=LONGCARD POINTER(${sy['AESProbePacket']:x})
  packetAddress^=LONGCARD(ADDRESS(packet))
  packet.version=AESTYPES.VERSION
  packet.bytes=SIZEOF(AESTYPES.Request)
  packet.sequence=$87654321
  packet.owner=EXEC.FindTask(NULL)
  packet.binding=BYTE POINTER(packet)
  FOR index=0 TO AESTYPES.INTIN_WORDS-1 DO
    packet.intin(index)=-100-INT(index)
  OD

  FOR index=0 TO AESTYPES.GLOBAL_WORDS-1 DO
    packet.global(index)=INT(600+index)
  OD

  LET entry=ADDRESS POINTER(@cProbe)
  entry^=${sy['AESWireProbe']:x}
  result=cProbe()
  Require(result=0)
  FOR index=0 TO AESTYPES.INTIN_WORDS-1 DO
    Require(packet.intin(index)=INT(300+index))
  OD

  FOR index=0 TO AESTYPES.GLOBAL_WORDS-1 DO
    Require(packet.global(index)=-500-INT(index))
  OD

  FOR index=0 TO AESTYPES.MESSAGE_WORDS-1 DO
    Require(packet.words(index)=-200-INT(index))
  OD

  EXEC.FreeMem(memory,LONGCARD(131072))
  entry^=${sy['AESContextProbe']:x}
  result=cProbe()
  Require(result=0)
  LET native=LONGCARD POINTER(${sy['ConsoleProbeNative']:x})
  native^=LONGCARD(ADDRESS(@CONSOLEBITMAP.Call))
  CONSOLEBITMAP.Call(${sy['ConsoleBridgeProbe']:x})

RETURN
ENDMODULE
''')
    from generate_memory import PROFILE
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 8192
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    launcher = prepare(source, out, foreign, desktop=True)
    program = build(compiler(ROOT/'build/actionc'), launcher, out/'program',
        optimize=optimize, tasks=True, task_capacity=8, foreign_image=foreign,
        console_deferred=True, memory_profile=memory)
    return program, foreign


def run(out, mode, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    if replay:
        program = read_build(out/'program')
        foreign = json.loads((out/'c-image.json').read_text())
    else:
        program, foreign = context_program(out, mode == 'opt')
    report = dict(status='running', tier='development', qualification=False,
                  slice='AS0a', mode=mode, build=program['build'],
                  reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=6000)
            ownership(bridge, program, program['output'])
            sy = foreign['symbols']
            report['packet_address'] = int.from_bytes(bridge.memdump(sy['AESProbePacket'], 4), 'little')
            require((report['packet_address'] & 65535)+layout()['Request']['size'] > 65536,
                    'Wire probe did not cross a bank boundary')
            report['client_checks'] = [int.from_bytes(bridge.memdump(sy['AESChecks']+i*2, 2), 'little') for i in range(2)]
            require(all(n == 1041 for n in report['client_checks']), 'Incomplete C contexts: '+str(report['client_checks']))
            require(bridge.memdump(sy['AESFailures'], 4) == bytes(4), 'C context corruption')
            raw = bridge.memdump(sy['ConsoleProbeResults'], 80)
            report['bridge_words'] = [int.from_bytes(raw[i:i+2], 'little') for i in range(0, 80, 2)]
            # The existing bridge probe captures full native registers, DP and
            # lower C workspace on both stack parities; use its shared oracle.
            check_bridge(report['bridge_words'], program['labels']['console_bitmap_call'])
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES', mode, 'context/layout checks passed', flush=True)
    return report


def check_bridge(words, entry):
    for offset in (0, 20):
        row = words[offset:offset+20]
        require(row[0:3] == [(entry-1) & 65535, 0x5678, 0x9abc], 'Bridge A/X/Y changed')
        require(row[3] == row[16] and row[4] == row[17], 'Bridge S/D changed')
        require(row[5] == 0, 'Bridge P/DBR changed')
        require(row[6:16] == list(range(0x5a00, 0x5a0a)), 'C DP workspace changed')
    require((words[3] ^ words[23]) & 1, 'Missing opposite bridge stack parities')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.replay)
