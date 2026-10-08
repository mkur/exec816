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
    from generate_display import expected_layout as display_layout
    foreign = drawing(out, True, probe=True, widgets=True,
        client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c', ROOT/'c/calypsi/aes-events.c', ROOT/'tests/programs/aes_context.c'],
        client_entries=['AESClientOne', 'AESClientTwo'],
        client_roots=['AESContextProbe', 'AESWireProbe', 'AESProbePacket',
                      'AESChecks', 'AESFailures'],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout()),
                       (ROOT/'c/calypsi/display-layout.c', display_layout())],
        client_optimization={n: optimize for n in ('display.c', 'aes.c', 'aes-events.c', 'aes_context.c')})
    sy = foreign['symbols']
    checks = []
    for name, fields in ABI['records'].items():
        variable = 'record'+name
        checks += [f'  LET {variable}=AESTYPES.{name} POINTER(packet)',
                   f'  Require(SIZEOF(AESTYPES.{name})=AESTYPES.{name.upper()}_SIZE)']
        for field, kind, *counts in fields:
            access = field+'(0)' if counts else field
            checks += [f'  Require(ADDRESS(@{variable}.{access})-ADDRESS(packet)={layout()[name]["fields"][field]})']
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
  FOR index=0 TO AESTYPES.RPC_INTIN_WORDS-1 DO
    packet.intin(index)=-100-INT(index)
  OD

  FOR index=0 TO AESTYPES.GLOBAL_WORDS-1 DO
    packet.global(index)=INT(600+index)
  OD

  LET entry=ADDRESS POINTER(@cProbe)
  entry^=${sy['AESWireProbe']:x}
  result=cProbe()
  Require(result=0)
  FOR index=0 TO AESTYPES.RPC_INTIN_WORDS-1 DO
    Require(packet.intin(index)=INT(300+index))
  OD

  FOR index=0 TO AESTYPES.GLOBAL_WORDS-1 DO
    Require(packet.global(index)=-500-INT(index))
  OD

  Require(packet.intout(0)=-200)

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
            require(all(n == 1045 for n in report['client_checks']), 'Incomplete C contexts: '+str(report['client_checks']))
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


def caller_probes(out, timer=False):
    (out/'aeshybridprobe.act').write_text('MODULE AESHYBRIDPROBE\nPUBLIC BYTE park\nENDMODULE\n')
    core = read_source(ROOT/'lib/aes/aescore.act').replace('USE HEAPCORE', 'USE HEAPCORE\nUSE AESHYBRIDPROBE')
    needle='  IF request.message.mn_Length<>AESTYPES.REQUEST_SIZE THEN'
    require(core.count(needle)==1,'Missing AES dispatch boundary')
    core=core.replace(needle, '  IF request.operation=AESTYPES.OP_WRITE OR request.operation=AESTYPES.OP_MESAG\n      OR request.operation=AESTYPES.OP_TIMER OR request.operation=AESTYPES.OP_MULTI THEN\n    HEAPCORE.Abort($fcbe)\n  FI\n\n'+needle)
    core=core.replace('  count=0', '  IF AESHYBRIDPROBE.park<>0 THEN\n    RETURN(0)\n  FI\n\n  count=0')
    (out/'aescore.act').write_text(core)
    if not timer:
        return
    binding = (ROOT/'c/calypsi/aes-events.c').read_text().replace(
        '#include "aes-private.h"', '#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\nextern UWORD AESFault;\nvoid AESBeforeSend(struct ExecAESContext *c);\nvoid AESAfterRead(struct ExecAESContext *c);\nvoid AESBeforeWait(struct ExecAESContext *c, ULONG mask);')
    binding = binding.replace('t->query->tc_Request.io_Command = TD_READCLOCK;',
        't->query->tc_Request.io_Command = AESFault == 4 ? 0 : TD_READCLOCK;')
    needle='    return TRUE;\nfailure:'
    require(binding.count(needle)==1,'Missing caller clock boundary')
    binding=binding.replace(needle, '    AESAfterRead(c);\n'+needle)
    binding = binding.replace('    SendIO(&t->alarm->tc_Request);',
        '    AESBeforeSend(c);\n    SendIO(&t->alarm->tc_Request);')
    binding=binding.replace('        Wait(mask);', '        AESBeforeWait(c, mask);\n        Wait(mask);')
    (out/'aes-events.c').write_text(binding)


def applications(out, suite, replay=False, mode='opt', video='PAL', from_build=None, filesystem='sdfs'):
    gui = suite == 'gui'
    inbox = suite == 'inbox'
    keyboard = suite == 'keyboard'
    pointer = suite == 'pointer'
    input_events = suite == 'input_events'
    windows = suite == 'windows'
    borrowed = suite == 'display'
    vdi = suite == 'vdi'
    registration = suite == "registration"
    events = suite == 'events'
    locks = suite == 'locks'
    timers = suite == 'timers'
    out.mkdir(parents=True, exist_ok=True)
    if replay or from_build:
        recorded = from_build or out
        program = read_build(recorded/'program')
        foreign = json.loads((recorded/'c-image.json').read_text())
    else:
        if locks:
            (out/'aeslockprobe.act').write_text('MODULE AESLOCKPROBE\nPUBLIC BYTE busy\nENDMODULE\n')
            policy = read_source(ROOT/'lib/aes/aeslocks.act').replace('USE AESTYPES', 'USE AESTYPES\nUSE AESLOCKPROBE')
            policy = policy.replace('PUBLIC BYTE FUNC NativeReady()\n', 'PUBLIC BYTE FUNC NativeReady()\n\n  IF AESLOCKPROBE.busy<>0 THEN\n    RETURN(0)\n  FI\n')
            (out/'aeslocks.act').write_text(policy)
        if input_events:
            from test_aes_input_events import caller
            caller(out)
        if events or timers or suite == 'messages':
            caller_probes(out, timer=events or timers)
        entries = ['AESClient'+n for n in
                   (('One', 'Two', 'Three', 'Four', 'Five') if registration else
                    ('One', 'Two', 'Three', 'Four') if events or timers else
                    ('One', 'Two', 'Three') if locks else ('One', 'Two'))]
        if events or timers:
            entries.append('AESBurn')
        renderer = None
        extra_probes = []
        if borrowed:
            from test_display_borrow import instrument
            from generate_display import expected_layout as display_layout
            renderer = instrument(out)
            extra_probes = [(ROOT/'c/calypsi/display-layout.c', display_layout())]
        import build_bitmap_console as bitmap_builder
        original_extract=bitmap_builder.extract
        if vdi:
            from test_vdi_client import extract_with_preemption
            bitmap_builder.extract=extract_with_preemption
        try:
            foreign = drawing(out, True, widgets=True, fault=borrowed, renderer_source=renderer,
                client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c', (out/'aes-events.c' if events or timers or input_events else ROOT/'c/calypsi/aes-events.c'), ROOT/('tests/programs/display_borrow.c' if borrowed else f'tests/programs/aes_{suite}.c')]+([ROOT/'tests/programs/aes_peer_binding.c'] if registration else []),
                client_entries=entries,
                client_roots=['AESRun', 'AESService', 'AESChecks', 'AESFailures']+(['AESExhausted'] if registration else [])+(['AESVisible', 'AESVisibleCount', 'AESPhysical', 'AESPhysicalGo', 'AESView', 'AESWindow', 'AESControl'] if windows else [])+(['AESPark'] if events or timers or suite == 'messages' else []),
                client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())]+extra_probes,
                client_optimization={n: mode == 'opt' for n in ('aes.c', 'aes-objects.c', 'aes-resource.c', 'dos.c', f'aes_{suite}.c')})
        finally:
            bitmap_builder.extract=original_extract
        sy = foreign['symbols']
        if borrowed:
            from test_display_borrow import producer
            producer(out, sy)
        if gui:
            from test_aes_gui import producer
            producer(out, sy)
        if inbox:
            from test_aes_inbox import producer
            producer(out, sy)
        if input_events:
            from test_aes_input_events import producer
            producer(out, sy)
        if pointer:
            from test_aes_pointer import producer
            producer(out, sy)
        if keyboard:
            from test_aes_keyboard import producer
            producer(out, sy)
        source = out/('display-fixture.act' if borrowed else suite+'.act')
        exhaustion = f'''  service.nextClient=0
  entry^=${sy['AESExhausted']:x}
  Require(run()=0)
  service.nextClient=100
  service.nextGem=0
  Require(run()=0)
''' if registration else ''
        setup = '  LET service=AESSTATE.Get()\n'
        if suite == 'menus':
            setup += f'  BEGIN\n    LET item=LONGCARD POINTER(${sy["AESMenuNext"]:x})\n    item^=LONGCARD(ADDRESS(@service.nextMenuEpoch))\n  END\n'
        if timers or events:
            setup += f'  BEGIN\n    LET item=LONGCARD POINTER(${sy["AESClock"]:x})\n    item^=TIMERMETA.BASE+4\n  END\n'
        if events or timers or suite == 'messages':
            setup += f'  BEGIN\n    LET item=LONGCARD POINTER(${sy["AESPark"]:x})\n    item^=LONGCARD(ADDRESS(@AESHYBRIDPROBE.park))\n  END\n'
        if locks:
            for name, field in (('AESUpdates', 'updates'), ('AESMouseHolds', 'mouseHolds'),
                    ('AESLockCount', 'lockCount')):
                setup += f'  BEGIN\n    LET item=LONGCARD POINTER(${sy[name]:x})\n    item^=LONGCARD(ADDRESS(@service.{field}))\n  END\n'
        if locks:
            setup += f'  BEGIN\n    LET item=LONGCARD POINTER(${sy["AESNativeBusy"]:x})\n    item^=LONGCARD(ADDRESS(@AESLOCKPROBE.busy))\n  END\n'
        source.write_text(f'''MODULE AESPROBE
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE HEAPCORE
{'USE AESHYBRIDPROBE'+chr(10)+'USE TIMERMETA' if events or timers or suite == 'messages' else 'USE AESLOCKPROBE' if locks else ''}
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
{setup}
  LET entry=ADDRESS POINTER(@run)
  entry^=${sy['AESRun']:x}
  Require(run()=0)
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
            console_deferred=True, memory_profile=memory,
            **(dict(dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=2 if filesystem=='sdfs' else 1)]) if suite=='resources' else {}))
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse'] = metadata(None)
    pin = json.loads(json.dumps(PIN))
    pin['machine']['video'] = video
    report = dict(status='running', tier='development', qualification=False,
        slice='AI5' if input_events else 'AI4' if pointer else 'AI3' if keyboard else 'AI2' if inbox else 'WA4' if vdi else 'WA3' if borrowed else 'WA2' if windows else 'WA1' if gui else 'HY3', suite=suite, c_mode=mode,
        native_mode='opt', video=video, filesystem=filesystem if suite=='resources' else None, build=program['build'],
        reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8))
    if borrowed:
        from test_display_borrow import trace_setup, trace_result, trace_restore
        tracing=trace_setup(program,foreign,out)
    try:
        with emulator(BRIDGE, ROM, out, pin=pin) as bridge:
            report['machine'] = verify_machine(bridge, ROM, pin)
            if suite=='resources':
                from build_gem_resource import resource
                from make_data_disk import make
                media=out/'media';media.mkdir(exist_ok=True)
                payload=resource();(media/'DESKTOP.RSC').write_bytes(payload)
                bad=bytearray(payload);bad[72:76]=b'\xff'*4
                (media/'BAD.RSC').write_bytes(bad);(media/'SHORT.RSC').write_bytes(payload[:35])
                from prepare_calculator import resource_cases
                cases=resource_cases(out/'calculator')
                for name,payload in cases.items():(media/name).write_bytes(payload)
                make(out/'resources.atr',media,binary_names={'DESKTOP.RSC','BAD.RSC','SHORT.RSC',*cases},filesystem=filesystem,sector_bytes=128,sectors=720)
                bridge.mount(0,str(out/'resources.atr'))

            try:
                before = None
                if borrowed:
                    from test_display_borrow import physical
                    before = lambda b: physical(b, program, foreign, report)
                if suite=='objects':
                    from test_tedinfo import physical
                    before = lambda b: physical(b, program, foreign, report)
                if vdi:
                    from test_vdi_client import physical
                    before = lambda b: physical(b, program, foreign, report)
                if keyboard:
                    from test_aes_keyboard import physical
                    before = lambda b: physical(b, program, foreign, report)
                if windows:
                    from test_aes_windows import physical
                    before = lambda b: physical(b, program, foreign, report)
                report['runtime'], _ = execute(bridge, program, before_run=before,
                                              timeout=120, frame_limit=6000)
            finally:
                for name in (('AESChecks', 'AESFailures') if gui or inbox or input_events or suite in ('objects','resources','mouse_profile', 'menus') else
                             ('AESChecks', 'AESFailures', 'AESReady', 'AESDone')):
                    report[name] = int.from_bytes(bridge.memdump(foreign['symbols'][name], 2), 'little')
                if 'AESFirstFailure' in foreign['symbols']:
                    report['AESFirstFailure'] = int.from_bytes(bridge.memdump(foreign['symbols']['AESFirstFailure'], 2), 'little')
                if suite=='resources':
                    report['resource_status']=int.from_bytes(bridge.memdump(foreign['symbols']['ResourceStatus'],2),'little')
                    report['resource_error']=int.from_bytes(bridge.memdump(foreign['symbols']['ResourceError'],4),'little')
                report['native_checks'] = data(bridge, program['image'], 'checks', True)[0]
            ownership(bridge, program, program['output'])
            if borrowed: bridge.profile_stop()
            from stack_budget import stack_usage
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            require(report['AESFailures'] == 0 and report['AESChecks'] >= (25 if suite in ('objects','resources','mouse_profile', 'menus') else 160 if registration or inbox else 100 if events or locks or timers or keyboard or pointer or input_events else 60 if gui or windows or borrowed or vdi else 1000),
                    'Incomplete application checks')
            if windows:
                count = int.from_bytes(bridge.memdump(foreign['symbols']['AESVisibleCount'], 2), 'little')
                raw = bridge.memdump(foreign['symbols']['AESVisible'], count*8)
                import struct
                rectangles = [struct.unpack_from('<hhhh', raw, i*8) for i in range(count)]
                actual = set()
                for x, y, w, h in rectangles:
                    pixels = {(px, py) for px in range(x, x+w) for py in range(y, y+h)}
                    require(not actual.intersection(pixels), 'Visible rectangles overlap')
                    actual.update(pixels)
                expected = {(x, y) for x in range(17, 201) for y in range(25, 121)
                            if not (89 <= x < 209 and 49 <= y < 149)}
                require(actual == expected, 'Visible work region differs from independent pixel oracle')
                report['visible_rectangles'] = rectangles
                report['visible_pixels'] = len(actual)
            if events or timers:
                report['cpu_peer_iterations'] = int.from_bytes(bridge.memdump(foreign['symbols']['AESBurns'], 4), 'little')
            report['status'] = 'pass'
        if borrowed:
            report['access_timing']=trace_result(out,tracing)
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        if borrowed: trace_restore(tracing[2])
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES', suite, 'checks passed', flush=True)
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
            require(host.count('admitted='+call)==1, 'Admission wrapper changed')
            host = host.replace('admitted='+call, 'admitted='+call+
                f'\n  AESINTAKEPROBE.Admission({port},admitted)')
        # Finish after the deferred admission too: the budget covers the entire
        # presenter turn, not just the Controls prefix.
        host = host.replace('    lateAES=0\n    remaining=1',
            '    AESINTAKEPROBE.lateCount==+AESINTAKEPROBE.enabled\n    lateAES=0\n    remaining=1')
        needle = '    Events()\n  FI\n\nRETURN\n\nPUBLIC BYTE FUNC Runnable()'
        require(host.count(needle) == 1, 'Deferred admission boundary changed')
        host = host.replace(needle, '    Events()\n  FI\n  AESINTAKEPROBE.FinishTurn()\n\nRETURN\n\nPUBLIC BYTE FUNC Runnable()')
        (out/'deskhost.act').write_text(host)
        core=read_source(ROOT/'lib/desktop/deskcore.act').replace(
            'USE HEAPCORE', 'USE HEAPCORE\nUSE AESINTAKEPROBE',1)
        needle='      EXECLISTS.AddTail(@service.deferred,@request.message.mn_Node)'
        require(core.count(needle)==1, 'Native deferral boundary changed')
        (out/'deskcore.act').write_text(core.replace(needle,
            needle+'\n      AESINTAKEPROBE.deferred==+1'))
        pointer=read_source(ROOT/'lib/desktop/deskinput.act').replace(
            'USE HEAPCORE', 'USE HEAPCORE\nUSE AESINTAKEPROBE',1)
        needle='    IF AESLOCKS.MouseBlocked()=0 AND AESINPUT.Pop(@sample)<>0 THEN\n'
        require(pointer.count(needle)==1, 'Retained input boundary changed')
        (out/'deskinput.act').write_text(pointer.replace(needle,
            needle+'      AESINTAKEPROBE.ObserveInput()\n'))
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
                report['deferred_admissions'] = probe('lateCount', 1)[0]
                report['input_injected'] = probe('injected', 1)[0]
                report['input_consumed'] = probe('consumed', 1)[0]
                report['native_deferred'] = probe('deferred', 1)[0]
                require(report['input_injected'] == report['input_consumed'] >= 61
                        and report['native_deferred'] > 0,
                        'Missing admission/late-wake input coverage')
                require(report['maximum_per_turn'] <= 4 and report['deferred_admissions'] > 0,
                        'Missing bounded paint-before-AES admissions')
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


def plain_console(out):
    """Presenter hooks remain harmless when neither desktop nor AES is bound."""
    out.mkdir(parents=True,exist_ok=True)
    source=read_source(ROOT/'tests/programs/native_console_startup.act')
    source=source.replace('USE HEAPCORE','USE HEAPCORE\nUSE DESKINPUT\nUSE DESKSTATE\nUSE AESSTATE\nUSE AESHOST')
    source=source.replace('  port=EXEC.CreateMsgPort()', '''  IF DESKSTATE.Get()<>NULL OR AESSTATE.Get()<>NULL OR AESHOST.Mask()<>0 THEN
    HEAPCORE.Abort($f8e3)
  FI

  DESKINPUT.Advance()
  port=EXEC.CreateMsgPort()''')
    fixture=out/'plain.act';fixture.write_text(source)
    report=dict(status='running',tier='development',qualification=False)
    try:
        program=build(compiler(ROOT/'build/actionc'),fixture,out/'program',tasks=True,
            task_capacity=8,console=True,stack_checks=True)
        report['build']=program['build']
        with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,ROM,PIN)
            def before(b):
                b.poke(next(d['address'] for d in program['image']['data'] if '_ENABLED_' in d['name']),1)
            report['runtime'],_=execute(bridge,program,before_run=before,timeout=120,frame_limit=8000)
            require(data(bridge,program['image'],'checkpoint')==[1],'Plain console client did not finish')
            ownership(bridge,program,program['output'])
        report.update(status='pass',ownership='restored')
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Plain console with unbound GUI/AES hooks passed',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--video', choices=('PAL', 'NTSC'), default='PAL')
    parser.add_argument('--suite', choices=('context', 'intake', 'registration', 'messages', 'gui', 'inbox', 'keyboard', 'pointer', 'input_events', 'windows', 'display', 'objects', 'resources', 'mouse_profile', 'menus', 'vdi', 'events', 'timers', 'locks', 'console'), default='context')
    parser.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs',help='Resources fixture disk format')
    parser.add_argument('--failure', type=int, choices=(0, 1, 2, 3), default=0)
    args = parser.parse_args()
    if args.suite == 'context':
        run(args.output.resolve(), args.mode, args.replay)
    elif args.suite in ('registration', 'messages', 'gui', 'inbox', 'keyboard', 'pointer', 'input_events', 'windows', 'display', 'objects', 'resources', 'mouse_profile', 'menus', 'vdi', 'events', 'timers', 'locks'):
        applications(args.output.resolve(), args.suite, args.replay, args.mode,
                     args.video, args.from_build.resolve() if args.from_build else None,args.filesystem)
    elif args.suite == 'console':
        plain_console(args.output.resolve())
    else:
        require(args.mode == 'opt', 'Routine intake checks use optimized builds')
        intake(args.output.resolve(), args.failure, args.replay)
