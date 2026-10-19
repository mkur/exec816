#!/usr/bin/env python3
"""Bounded, emitted resident report formatting and exact Write counts."""
import argparse
import json
import re
import struct
from pathlib import Path

from generate_program import fault_messages
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def expanded(path, inputs):
    inputs[str(path.relative_to(ROOT))] = sha256(path)
    return re.sub(r'(?m)^INCLUDE "([^"]+)"',
                  lambda match: expanded(path.parent/match[1], inputs),
                  path.read_text())


def cases():
    source, expected = [], []

    def case(label, code, output, writes=None):
        source.append('  MarkCase()\n'+code+'\n')
        expected.append(dict(label=label, output=output,
                             writes=writes if writes is not None else len(output.splitlines())))

    case('tasks-empty', '  ShellTasks(@context,NULL)', b'SLOT STATE    NAME\n')
    setup = '''  taskCount=5
  taskRows(0).slot=0
  taskRows(0).state=TASKINSPECT.STATE_RUNNING
  STR.strlcpy(taskRows(0).name,c"main",24)
  taskRows(1).slot=9
  taskRows(1).state=TASKINSPECT.STATE_READY
  taskRows(2).slot=10
  taskRows(2).state=TASKINSPECT.STATE_SIGNAL_WAIT
  STR.strlcpy(taskRows(2).name,c"waiter",24)
  taskRows(3).slot=14
  taskRows(3).state=TASKINSPECT.STATE_SLEEPING
  STR.strlcpy(taskRows(3).name,c"abcdefghijklmnopqrstuvw",24)
  taskRows(4).slot=15
  taskRows(4).state=255
  STR.strlcpy(taskRows(4).name,c"unknown",24)
  ShellTasks(@context,NULL)'''
    case('task-states-names-slots', setup,
         b'SLOT STATE    NAME\n0    RUNNING  main\n9    READY    (unnamed)\n'
         b'10   WAITING  waiter\n14   SLEEPING abcdefghijklmnopqrstuvw\n15   UNKNOWN  unknown\n')
    case('devices-empty', '  ShellDevices(@context,NULL)', b'DEVICE          STATE\n')
    case('devices', '''  deviceCount=4
  deviceRows(0).kind=DEVICEINSPECT.CONSOLE
  deviceRows(0).state=DEVICEINSPECT.READY
  deviceRows(1).kind=DEVICEINSPECT.SIO
  deviceRows(1).state=DEVICEINSPECT.OFFLINE
  deviceRows(2).kind=DEVICEINSPECT.TIMER
  deviceRows(2).state=DEVICEINSPECT.INACTIVE
  deviceRows(3).kind=DEVICEINSPECT.IDEPLUS
  deviceRows(3).state=255
  ShellDevices(@context,NULL)''',
         b'DEVICE          STATE\nconsole.device  ready\nsio.device      offline\n'
         b'timer.device    inactive\nideplus.device  unknown\n')
    case('mounts-empty', '  ShellMounts(@context,NULL)',
         b'MOUNT FILESYSTEM ACCESS    STATE DEVICE/UNIT\nNo mounted filesystems\n')
    case('mount-types-access-offline-long-name', '''  mountCount=4
  STR.strlcpy(mountRows(0).name,c"SYS",32)
  mountRows(0).format=FSFORMATS.MYDOS
  mountRows(0).readOnly=1
  mountRows(0).unit=49
  STR.strlcpy(mountRows(1).name,c"WORK",32)
  mountRows(1).format=FSFORMATS.SDFS
  mountRows(1).backend=BLOCKTYPES.BACKEND_IDEPLUS
  mountRows(1).unit=15
  mountRows(1).offline=1
  mountRows(1).error=205
  STR.strlcpy(mountRows(2).name,c"RAM",32)
  mountRows(2).format=FSFORMATS.RAM
  STR.strlcpy(mountRows(3).name,c"ABCDEFGHIJKLMNOPQRSTUVWXYZ12345",32)
  mountRows(3).format=255
  mountRows(3).readOnly=1
  mountRows(3).unit=56
  ShellMounts(@context,NULL)''',
         b'MOUNT FILESYSTEM ACCESS    STATE DEVICE/UNIT\n'
         b'SYS:  MyDOS      read-only mounted sio.device/D1\n'
         b'WORK: SDFS       writable  offline ideplus.device/15\n  '+
         f'{fault_messages()[205]} (205)\n'.encode()+
         b'RAM:  RAM        writable  mounted\n'
         b'ABCDEFGHIJKLMNOPQRSTUVWXYZ12345: unknown    read-only mounted sio.device/D8\n')
    case('mount-failure-numeric', '''  failurePresent=1
  mountFailure.error=5
  mountFailure.stage=FSTYPES.MOUNT_CONFIG
  ShellMountFailureReport(@context,NULL)''',
         b'MOUNT FAILED  =filesystem service\nMOUNT PHASE   =invalid configuration\nMOUNT ERROR   =error 5\n')
    case('mount-failure-geometry', '''  STR.strlcpy(mountFailure.name,c"ABCDEFGHIJKLMNOPQRSTUVWXYZ12345",32)
  mountFailure.backend=BLOCKTYPES.BACKEND_IDEPLUS
  mountFailure.unit=15
  mountFailure.stage=BLOCKTYPES.ADMIT_BYTES
  mountFailure.error=205
  mountFailure.sectors=12345
  mountFailure.bytes=256
  partitions(15).reason=IDEPLUS.SLOT_READY
  partitions(15).sectors=1440
  partitions(15).bytes=512
  ShellMountFailureReport(@context,NULL)''',
         b'MOUNT FAILED  =\nABCDEFGHIJKLMNOPQRSTUVWXYZ12345:\nMOUNT PHASE   =sector size mismatch\n'
         b'MOUNT ERROR   ='+f'{fault_messages()[205]} (205)\n'.encode()+
         b'MOUNT DEVICE  =ideplus.device/15\n  expected 12345 x 256B\n  actual   1440 x 512B\n')
    case('mount-discovery-conflict', '''  STR.strlcpy(mountFailure.name,c"DATA",32)
  mountFailure.backend=0
  mountFailure.unit=50
  mountFailure.stage=FSTYPES.MOUNT_DISCOVERY
  mountFailure.error=225
  mountFailure.reason=FSDISCOVER.BAD_DENSITY
  mountFailure.status(0)=$20
  mountFailure.percom(0)=40
  mountFailure.percom(3)=18
  mountFailure.percom(7)=128
  ShellMountFailureReport(@context,NULL)
  mountFailure.reason=0
  mountFailure.source=0''',
         b'MOUNT FAILED  =DATA:\nMOUNT PHASE   =disk geometry\n'
         b'MOUNT ERROR   ='+f'{fault_messages()[225]} (225)\n'.encode()+
         b'MOUNT DEVICE  =sio.device/D2\nMOUNT REASON  =STATUS/PERCOM conflict\n'
         b'MOUNT STATUS  =20 00 00 00 \nMOUNT PERCOM  =28 00 00 12 00 00 \n'
         b'MOUNT PERCOM  =00 80 00 00 00 00 \n')
    case('mount-effective-geometry', '''  STR.strlcpy(mountRows(0).name,c"DATA",32)
  mountRows(0).unit=50
  mountRows(0).format=FSFORMATS.SDFS
  mountRows(0).sectors=2880
  mountRows(0).bytes=256
  mountRows(0).profile=EXEC.SIO_PROFILE_GENERIC57600
  mountRows(0).source=FSDISCOVER.PERCOM
  ShellMountDetails(@context,NULL,@mountRows(0))''',
         b'DATA:\n  D2 SpartaDOS read-only\n  2880 x 256B GENERIC57600\n  geometry: PERCOM\n')
    case('mount-open-reason', '''  mountFailure.stage=BLOCKTYPES.ADMIT_OPEN
  partitions(15).reason=IDEPLUS.SLOT_DELETED
  ShellMountOpenReason(@context,NULL,15)''', b'MOUNT REASON  =deleted APT slot\n')
    case('ide-unattempted-visible', '  ShellIdeReport(@context,NULL,1)', b'IDE CTRL      =UNATTEMPTED\n')
    case('ide-unattempted-hidden', '  ShellIdeReport(@context,NULL,0)', b'', 0)
    case('ide-ready-partitions', '''  ideInfo.attempted=1
  ideInfo.controller=1
  ideInfo.disk=1
  ideInfo.apt=1
  ideInfo.stage=IDEPLUS.STAGE_READY
  ideInfo.state=2
  ideInfo.generation=$ffffffff
  ideInfo.boardStatus=$10
  ideInfo.sectors=2097152
  ideInfo.durable=1
  partitions(1).reason=IDEPLUS.SLOT_READY
  partitions(1).flags=IDEPLUS.FLAG_READONLY
  partitions(1).start=128
  partitions(1).sectors=1440
  partitions(2).reason=IDEPLUS.SLOT_READY
  partitions(2).start=1568
  partitions(2).sectors=1440
  ShellIdeReport(@context,NULL,1)''',
         b'IDE CTRL      =DETECTED (PBI ID 0)\nIDE PHASE     =ready\nIDE STATE     =2 GEN -1\n'
         b'IDE CARD      =$10\nIDE SECTORS   =2097152\nIDE CAPACITY  =1024 MiB (512B)\n'
         b'IDE WRITES    =BOARD PROTECTED\nAPT STATUS    =VALID\n'
         b'APT UNIT      =1 RO 512B\n  LBA 128 SECTORS 1440\n'
         b'APT UNIT      =2 RW 512B\n  LBA 1568 SECTORS 1440\nAPT UNIT      =15 SKIPPED: deleted\n')
    case('ide-ata-failure', '''  ideInfo.reason=IDEPLUS.REASON_TIMEOUT
  ideInfo.stage=IDEPLUS.STAGE_TRANSFER
  ideInfo.status=$80
  ideInfo.ataError=$04
  ideInfo.lba=268435455
  ideInfo.slot=15
  ideInfo.boardStatus=0
  ideInfo.durable=0
  ShellIdeReport(@context,NULL,1)''',
         b'IDE CTRL      =DETECTED (PBI ID 0)\nIDE PHASE     =ATA transfer\nIDE STATE     =2 GEN -1\n'
         b'IDE CARD      =$00\nIDE SECTORS   =2097152\nIDE CAPACITY  =1024 MiB (512B)\n'
         b'IDE WRITES    =NO DURABLE SUPPORT\nIDE ERROR     =ATA readiness timeout\n'
         b'IDE ATA       =STATUS $80 ERROR $04\nIDE FAULT LBA =268435455 UNIT 15\nAPT STATUS    =VALID\n'
         b'APT UNIT      =1 RO 512B\n  LBA 128 SECTORS 1440\nAPT UNIT      =2 RW 512B\n'
         b'  LBA 1568 SECTORS 1440\nAPT UNIT      =15 SKIPPED: deleted\n')
    case('ide-controller-absent', '''  ideInfo.controller=0
  ideInfo.disk=0
  ideInfo.apt=0
  ideInfo.stage=IDEPLUS.STAGE_CONTROLLER
  ideInfo.reason=IDEPLUS.REASON_CONTROLLER_ABSENT
  ShellIdeReport(@context,NULL,1)''',
         b'IDE CTRL      =NOT DETECTED (PBI ID 0)\nIDE PHASE     =controller detection\n'
         b'IDE STATE     =2 GEN -1\nIDE CARD      =$00\nIDE DISK      =NOT IDENTIFIED\n'
         b'IDE ERROR     =controller absent\nAPT STATUS    =NOT CHECKED\n')
    case('jobs-empty', '  ShellJobs(@context)', b'No background jobs\n')
    for state, label in [('JOB_RUNNING', b'running'), ('JOB_STOPPING', b'stopping')]:
        case('job-'+label.decode(), f'  context.job.identity=$ffffffff\n  context.job.state={state}\n  ShellJobReport(@context,NULL)',
             b'Job 4294967295 '+label+b'\n')
    case('job-signed-results', '''  context.job.state=JOB_DONE
  context.job.outcome.primary=$80000000
  context.job.outcome.secondary=$7fffffff
  ShellJobs(@context)''', b'Job 4294967295 finished (-2147483648, 2147483647)\n')
    case('alias-maximum', '''  STR.strlcpy(context.aliases(0).name,c"ABCDEFGHIJKLMNO",16)
  STR.strlcpy(context.aliases(0).text,CSTRING(longText),128)
  ShellAliasShow(@context,0)''', b'ABCDEFGHIJKLMNO -> '+b'X'*127+b'\n', 2)
    case('path-maximum', '''  context.shell.argc=1
  context.shell.pathCount=1
  STR.strlcpy(ShellPathEntry(@context,0),CSTRING(longText),256)
  ShellPath(@context)''', b'Current directory\n'+b'X'*255+b'\n', 3)
    case('echo-empty-argument', '''  context.shell.command=CMD_ECHO
  context.shell.argc=4
  context.shell.words(1).text=BYTE POINTER(c"")
  context.shell.words(2).text=BYTE POINTER(c"one")
  context.shell.words(3).text=BYTE POINTER(c"two")
  ShellDispatch(@context)''', b' one two\n')
    case('echo-maximum', '''  context.shell.argc=2
  context.shell.words(1).text=longText
  ShellDispatch(@context)''', b'X'*255+b'\n', 2)
    for length in (0, 127, 128, 255):
        case('draw-boundary-'+str(length), f'  Boundary({length})', b'X'*length+b'\n', (length+1+127)//128)
    case('number-boundary', '''  used=ShellRowBytes(@context,NULL,0,longText,116)
  used=ShellRowNumber(@context,NULL,used,LONGINT($80000000))
  ShellRowEnd(@context,NULL,used)''', b'X'*116+b'-2147483648\n', 1)
    case('unsigned-boundary', '''  used=ShellRowBytes(@context,NULL,0,longText,118)
  used=ShellRowUnsigned(@context,NULL,used,$ffffffff)
  ShellRowEnd(@context,NULL,used)''', b'X'*118+b'4294967295\n', 2)
    case('mem-flags', '''  memoryValues(0)=EXEC.AvailMem(0)
  memoryValues(1)=EXEC.AvailMem(EXEC.MEMF_LARGEST)
  memoryValues(2)=EXEC.AvailMem(EXEC.MEMF_LINEAR)
  memoryValues(3)=EXEC.AvailMem(EXEC.MEMF_LINEAR OR EXEC.MEMF_LARGEST)
  ShellMem(@context)''', b'', 4)
    return '\n'.join(source), expected


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    inputs = {}
    source = expanded(ROOT/'examples/shell/shell-session.inc', inputs)
    source = source.replace('PROC ShellWrite(', 'PROC NativeShellWrite(')
    for before, after in [('TASKINSPECT.Snapshot(', 'ReportTasks('),
                          ('DEVICEINSPECT.Snapshot(', 'ReportDevices('),
                          ('FSINSPECT.Snapshot(', 'ReportMounts('),
                          ('FSINSPECT.LastFailure(', 'ReportFailure('),
                          ('IDEPLUSDRIVER.Diagnostics(', 'ReportIde('),
                          ('IDEPLUSDRIVER.PartitionStatus(', 'ReportPartition(')]:
        require(before in source, 'Missing inspection boundary: '+before)
        source = source.replace(before, after)
    (out/'shell-observed.inc').write_text(source)
    fixture = ROOT/'tests/programs/shell_reports.act'
    code, expected = cases()
    (out/'probe.act').write_text(fixture.read_text().replace(
        '  INCLUDE "report-cases.inc"', code))
    (out/'report-cases.inc').write_text(code)
    profile = json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    # Test-only capture storage, inspection inputs and output oracles are upper RAM.
    profile['image_data_bytes'] = 16384
    (out/'memory.json').write_text(json.dumps(profile))
    p = build(compiler(ROOT/'build/actionc', release=True), out/'probe.act', out,
              optimize=True, tasks=True, task_capacity=8, console=True,
              dos_mounts=[], memory_profile=out/'memory.json')
    rom = ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge', rom, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, rom, PIN)
        runtime, _ = execute(b, p, timeout=120, frame_limit=6000)
        require(data(b, p['image'], 'finished') == [1], 'Reports fixture incomplete')
        ownership(b, p, out)
        marks = list(struct.iter_unpack('<HH', bytes(data(b, p['image'], 'marks'))))
        count = int.from_bytes(bytes(data(b, p['image'], 'caseCount')), 'little')
        actual = bytes(data(b, p['image'], 'captured'))
        memory = struct.unpack('<4I', bytes(data(b, p['image'], 'memoryValues')))
        require(count == len(expected)+1, 'Missing report cases')
    expected[-1]['output'] = b''.join(label+str(value).encode()+b'\n' for label, value in zip(
        (b'ordinary total ', b'ordinary largest ', b'linear total ', b'linear largest '), memory))
    for i, item in enumerate(expected):
        start, writes = marks[i]
        end, next_writes = marks[i+1]
        require(actual[start:end] == item['output'], 'Output differs: '+item['label']+
                '\nActual: '+repr(actual[start:end])+'\nExpected: '+repr(item['output']))
        require(next_writes-writes == item['writes'], 'Write count differs: '+item['label'])
        item['output_bytes'] = len(item.pop('output'))
    return dict(status='pass', tier='development', mode='opt', cases=expected,
                runtime=runtime, machine=machine, build=p['build'], source_inputs=inputs,
                fixture_sha256=sha256(fixture), runner_sha256=sha256(Path(__file__)),
                bank_zero_delta=dict(fixed=0, per_task=0, private_idle=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve())
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell reports passed:', len(result['cases']), 'optimized emitted cases', flush=True)
