#!/usr/bin/env python3
"""Focused emitted AES protocol, presenter and C application checks."""
import argparse
import json
from pathlib import Path

from build_bitmap_console import drawing, prepare, build_bitmap
from generate_aes_server import ABI, expected_layout, files, layout
from native_program import ROOT, build, compiler, read_build, require, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN
from test_cooperative import data
from library_paths import read_source


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


def applications(out, suite, replay=False):
    registration = suite == "registration"
    out.mkdir(parents=True, exist_ok=True)
    if replay:
        program = read_build(out/'program')
        foreign = json.loads((out/'c-image.json').read_text())
    else:
        foreign = drawing(out, True, widgets=True,
            client_sources=[ROOT/'c/calypsi/aes.c', ROOT/f'tests/programs/aes_{suite}.c'],
            client_entries=['AESClient'+n for n in (('One', 'Two', 'Three', 'Four', 'Five') if registration else ('One', 'Two'))],
            client_roots=['AESRun', 'AESService', 'AESChecks', 'AESFailures']+(['AESExhausted'] if registration else []),
            client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())])
        sy = foreign['symbols']
        source = out/(suite+'.act')
        exhaustion = f'''  service.nextClient=0
  entry^=${sy['AESExhausted']:x}
  Require(run()=0)
  service.nextClient=100
  service.nextGem=0
  Require(run()=0)
''' if registration else ''
        source.write_text(f'''MODULE AESPROBE
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE HEAPCORE
CARD checks
CARD FUNC POINTER run()

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fc40+checks)
  FI

  checks==+1

RETURN

PROC Main()

  LET endpoint=LONGCARD POINTER(${sy['AESService']:x})
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  Require(endpoint^<>0)
  LET entry=ADDRESS POINTER(@run)
  entry^=${sy['AESRun']:x}
  Require(run()=0)
  LET service=AESSTATE.Get()
  Require(service.count=0)
  Require(AESCORE.Idle(service)<>0)
{exhaustion}
RETURN
ENDMODULE
''')
        from generate_memory import PROFILE
        profile = json.loads(PROFILE.read_text())
        profile['image_data_bytes'] = 8192
        memory = out/'fixture-memory.json'
        memory.write_text(json.dumps(profile, indent=2)+'\n')
        launcher = prepare(source, out, foreign, desktop=True, aes=True)
        program = build(compiler(ROOT/'build/actionc'), launcher, out/'program',
            tasks=True, task_capacity=8, foreign_image=foreign,
            console_deferred=True, memory_profile=memory)
    report = dict(status='running', tier='development', qualification=False,
        slice='AS0c' if registration else 'AS1', build=program['build'],
        reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=6000)
            finally:
                for name in ('AESChecks', 'AESFailures', 'AESReady', 'AESDone'):
                    report[name] = int.from_bytes(bridge.memdump(foreign['symbols'][name], 2), 'little')
                report['native_checks'] = data(bridge, program['image'], 'checks', True)[0]
            ownership(bridge, program, program['output'])
            require(report['AESFailures'] == 0 and report['AESChecks'] >= (160 if registration else 1000),
                    'Incomplete application checks')
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES', suite, 'checks passed', flush=True)
    return report


def alarm(out, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    if replay:
        program = read_build(out/'program')
    else:
        for name in ('aes_alarm', 'aesalarmprobe', 'aesalarmrace'):
            (out/(name+'.act')).write_text(read_source(ROOT/f'tests/programs/{name}.act'))
        host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESTIMER',
            'USE AESTIMER\nUSE AESALARMPROBE')
        host = host.replace('AESTIMER.Target(service,0,0,0)', 'AESALARMPROBE.Tick(service)')
        (out/'aeshost.act').write_text(host)
        timer = read_source(ROOT/'lib/aes/aestimer.act').replace('USE HEAPCORE',
            'USE HEAPCORE\nUSE AESALARMRACE')
        for number, target, call in (
            (1, 'state.port', 'EXEC.CreateMsgPort()'),
            (2, 'state.query', 'TIMER.TimerClockRequest POINTER(EXEC.CreateIORequest(\n        state.port,SIZEOF(TIMER.TimerClockRequest)))'),
            (3, 'state.alarm', 'TIMER.TimerClockRequest POINTER(EXEC.CreateIORequest(\n          state.port,SIZEOF(TIMER.TimerClockRequest)))')):
            needle = target+'='+call
            require(timer.count(needle) == 1, 'Timer allocation boundary changed')
            timer = timer.replace(needle, f'IF AESALARMRACE.fault={number} THEN\n    {target}=NULL\n  ELSE\n    {needle}\n  FI')
        timer = timer.replace('TIMER.UNIT_VBLANK,', 'LONGCARD(IF AESALARMRACE.fault=4 THEN 0 ELSE TIMER.UNIT_VBLANK FI),')
        timer = timer.replace('state.query.tc_Request.io_Command=TIMER.TD_READCLOCK',
            'state.query.tc_Request.io_Command=IF AESALARMRACE.fault=5 THEN 0 ELSE TIMER.TD_READCLOCK FI')
        timer = timer.replace('  EXEC.SendIO(@state.alarm.tc_Request)',
            '  AESALARMRACE.sends==+1\n  EXEC.SendIO(@state.alarm.tc_Request)')
        timer = timer.replace('      EXEC.AbortIO(@state.alarm.tc_Request)',
            '      AESALARMRACE.BeforeAbort(service)\n      AESALARMRACE.aborts==+1\n      EXEC.AbortIO(@state.alarm.tc_Request)')
        timer = timer.replace('  LET error=state.alarm.tc_Request.io_Error',
            '  AESALARMRACE.collections==+1\n  LET error=state.alarm.tc_Request.io_Error')
        (out/'aestimer.act').write_text(timer)
        driver = read_source(ROOT/'lib/io/timerdriver.act').replace('USE HEAPCORE',
            'USE HEAPCORE\nUSE AESALARMRACE')
        driver = driver.replace('  IF state.count=TIMERMETA.PENDING_CAPACITY THEN',
            '  IF state.count=TIMERMETA.PENDING_CAPACITY OR AESALARMRACE.fault=6 THEN')
        (out/'timerdriver.act').write_text(driver)
        program = build_bitmap(out/'aes_alarm.act', out, desktop=True, aes=True)
    report = dict(status='running', tier='development', qualification=False,
        slice='AS2a', build=program['build'],
        reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=6000)
            finally:
                report['checks'] = data(bridge, program['image'], 'checks', True)[0]
                for name in ('sends', 'aborts', 'collections', 'races'):
                    report[name] = data(bridge, program['image'], name, True)[0]
            ownership(bridge, program, program['output'])
            require(report['checks'] >= 70 and report['races'] == 1, 'Incomplete alarm checks')
            require(report['sends'] == report['collections'], 'Alarm ownership leaked')
            base = program['build']['memory']['timer_device_storage']['BASE']
            state = bridge.memdump(base, 24)
            require(state[16:18] == bytes(2) and state[20:24] == bytes([0, 0, 255, 0]),
                    'Timer remained active after AES shutdown')
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES alarm lifecycle checks passed', flush=True)
    return report


def intake(out, failure=0, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    if replay:
        program = read_build(out/'program')
    else:
        source = out/'intake.act'
        source.write_text(read_source(ROOT/'tests/programs/aes_intake.act').replace(
            'CONST FAILURE=0', f'CONST FAILURE={failure}'))
        (out/'aesintakeprobe.act').write_text(read_source(ROOT/'tests/programs/aesintakeprobe.act'))
        host = read_source(ROOT/'lib/desktop/deskhost.act').replace('USE AESHOST',
            'USE AESHOST\nUSE AESINTAKEPROBE')
        host = host.replace('    count=0\n', '    count=0\n    AESINTAKEPROBE.StartTurn()\n')
        for port, call in enumerate(('DESKCORE.Pump(service,1)', 'AESHOST.Pump(1)')):
            host = host.replace('admitted='+call, 'admitted='+call+
                f'\n        AESINTAKEPROBE.Admission({port},admitted)')
        host = host.replace('    DESKCORE.Wake(service)',
            '    AESINTAKEPROBE.FinishTurn(count)\n    DESKCORE.Wake(service)')
        (out/'deskhost.act').write_text(host)
        if failure == 1:
            boot = read_source(ROOT/'lib/aes/aesboot.act').replace(
                'EXEC.AllocMem(SIZEOF(AESSTATE.Service),', 'EXEC.AllocMem(0,')
            (out/'aesboot.act').write_text(boot)
        elif failure in (2, 3):
            aes_host = read_source(ROOT/'lib/aes/aeshost.act')
            aes_host = aes_host.replace('bit=EXEC.AllocSignal(-1)', 'bit=$ff') if failure == 2 else aes_host.replace(
                'AESCORE.Init(service,bit)', 'AESCORE.Init(service,32)')
            (out/'aeshost.act').write_text(aes_host)
        import generate_tasks
        original = generate_tasks.policy_modules

        def instrument(*args, **kwargs):
            directory = original(*args, **kwargs)
            path = directory/'consoledriver.act'
            driver = path.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE AESINTAKEPROBE\n', 1)
            wait = 'bits=EXEC.Wait($e0000000 OR displayMask OR desktopMask)'
            require(driver.count(wait) == 2, 'Presenter wait boundaries changed')
            path.write_text(driver.replace(wait, 'AESINTAKEPROBE.Boundary()\n        '+wait))
            return directory

        generate_tasks.policy_modules = instrument
        try:
            program = build_bitmap(source, out, desktop=True, aes=True)
        finally:
            generate_tasks.policy_modules = original
    report = dict(status='running', tier='development', qualification=False,
        slice='AS0b', failure=failure, build=program['build'],
        reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            bridge._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(bridge, ROM, PIN)
            try:
                report['runtime'], _ = execute(bridge, program, timeout=120, frame_limit=6000)
            except Exception:
                report['checks'] = data(bridge, program['image'], 'checks', True)[0]
                raise
            ownership(bridge, program, program['output'])
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            if not failure:
                def probe(name, size):
                    at = next(d['address'] for d in program['image']['data']
                              if '_AESINTAKEPROBE_'+name.upper()+'_' in d['name'])
                    return list(bridge.memdump(at, size))
                report['admission_ports'] = probe('ports', 24)
                report['admission_turns'] = probe('turns', 24)
                report['maximum_per_turn'] = probe('maximum', 1)[0]
                require(report['checks'] >= 90, 'Incomplete intake fixture')
            else:
                require(report['checks'] == 6, 'Incomplete failure fixture')
            report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES intake passed; injected failure', failure, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--suite', choices=('context', 'intake', 'registration', 'messages', 'alarm'), default='context')
    parser.add_argument('--failure', type=int, choices=(0, 1, 2, 3), default=0)
    args = parser.parse_args()
    if args.suite == 'context':
        run(args.output.resolve(), args.mode, args.replay)
    elif args.suite in ('registration', 'messages'):
        applications(args.output.resolve(), args.suite, args.replay)
    elif args.suite == 'alarm':
        alarm(args.output.resolve(), args.replay)
    else:
        require(args.mode == 'opt', 'Routine intake checks use optimized builds')
        intake(args.output.resolve(), args.failure, args.replay)
