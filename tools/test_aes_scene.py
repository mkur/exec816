#!/usr/bin/env python3
"""GF3: input delivery, deferred fences and ownership through real Task preemption."""
import argparse
import json
import re
from pathlib import Path

import adapter_state as adapter
from build_bitmap_console import build_bitmap
from desktop_mouse import schedule
from generate_tasks import ABI as TASK_ABI
from generate_aes_server import layout as aes_layout
from library_paths import read_source
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN
from stack_budget import stack_usage


def build(out):
    source = out/'scene.act'
    source.write_text('''MODULE SCENETEST
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE DESKSTATE
USE HEAPCORE
USE SCENEPROBE
CARD FUNC POINTER run()
PROC Main()

  LET service=AESSTATE.Get()
  LET desktop=DESKSTATE.Get()
  SCENEPROBE.gateAddress=LONGCARD(ADDRESS(@service.policyGate))
  SCENEPROBE.waitAddress=LONGCARD(ADDRESS(@service.policyWaiting))
  SCENEPROBE.ownerAddress=LONGCARD(ADDRESS(@service.sceneOwner))
  SCENEPROBE.taskAddress=LONGCARD(ADDRESS(@service.owner))
  SCENEPROBE.tokenAddress=LONGCARD(ADDRESS(@desktop.scene.busy))
  SCENEPROBE.effectsAddress=LONGCARD(ADDRESS(@service.policyEffects))
  SCENEPROBE.waitersAddress=LONGCARD(ADDRESS(@service.sceneWaiters))
  LET endpoint=LONGCARD POINTER($AESService)
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET entry=ADDRESS POINTER(@run)
  entry^=$AESRun
  LET result=run()
  IF result<>0 OR service.count<>0 OR AESCORE.Idle(service)=0
      OR service.sceneWaiters<>NULL OR service.policyEffects<>0 THEN
    HEAPCORE.Abort($fc80)
  FI

RETURN
ENDMODULE
''')
    probe = '''MODULE SCENEPROBE
USE EXEC
USE AESSTATE
USE AESSNAPSHOT
USE HEAPCORE
PUBLIC LONGCARD gateAddress,waitAddress,ownerAddress,taskAddress
PUBLIC LONGCARD tokenAddress,effectsAddress
PUBLIC LONGCARD waitersAddress
PUBLIC LONGCARD sceneChecks,physicalChecks
PUBLIC LONGCARD deferredCalls,seenBits,lastConsumed,rootInbox,routeEpoch
PUBLIC CARD keyTail,buttonTail,eligible
PUBLIC CARD cursorX,cursorY
PUBLIC BYTE FUNC PointerCase()

  LET variant=CARD POINTER($SceneVariant)

RETURN(variant^=2)

PUBLIC PROC Observe(LONGCARD consumed,bits)
  BYTE index
  AESSNAPSHOT.WindowRoute route

  deferredCalls==+1
  lastConsumed=consumed
  seenBits=seenBits OR bits
  FOR index=0 TO 3 DO
    IF AESSNAPSHOT.Default(index,@route)<>0 THEN
      IF route.client=1 THEN
        rootInbox=LONGCARD(ADDRESS(route.endpoint.input))
        routeEpoch=route.epoch
        keyTail=route.endpoint.input.keyTail
        buttonTail=route.endpoint.input.buttonTail
        eligible=route.endpoint.input.eligible
      FI
      AESSNAPSHOT.Drop(route.endpoint)
    FI
  OD

RETURN
PUBLIC PROC Check(BYTE physical)

  LET service=AESSTATE.Get()
  IF service<>NULL AND service.live=1 THEN
    IF physical<>0 THEN
      IF service.policyGate=0 THEN
        HEAPCORE.Abort($fc81)
      FI
      physicalChecks==+1
    ELSE
      IF service.sceneOwner<>EXEC.FindTask(NULL) THEN
        HEAPCORE.Abort($fc82)
      FI
      sceneChecks==+1
    FI
  FI

RETURN
PUBLIC PROC Pause(BYTE kind LONGCARD client)

  LET identity=LONGCARD POINTER($SceneHoldClient)
  IF kind=1 THEN
    BEGIN
      LET held=CARD POINTER($SceneHeld)
      LET go=CARD POINTER($SceneHoldGo)
      IF identity^<>0 AND client=identity^ AND held^=0 THEN
        held^=1
        WHILE go^=0 DO
          EXEC.Yield()
        OD
      FI
    END
  ELSE
    BEGIN
      LET arm=CARD POINTER($SceneEffectArm)
      LET held=CARD POINTER($SceneEffectHeld)
      LET go=CARD POINTER($SceneEffectGo)
      IF arm^<>0 AND held^=0 THEN
        held^=1
        WHILE go^=0 DO
          EXEC.Yield()
        OD
      FI
    END
  FI

RETURN
ENDMODULE
'''

    def shadow(name, routines):
        path = ROOT/'lib'/('aes' if name.startswith('aes') else 'desktop')/(name+'.act')
        text = read_source(path)
        text = text.replace('MODULE '+name.upper()+'\n',
                            'MODULE '+name.upper()+'\nUSE SCENEPROBE\n', 1)
        for routine in routines:
            match = re.search(r'(?m)^(?:PUBLIC )?(?:[^;\n]+ FUNC|PROC) '+routine+r'\(', text)
            require(match is not None, 'Scene boundary changed: '+name+'.'+routine)
            at = text.index('\n\n', match.start())+2
            text = text[:at]+'  SCENEPROBE.Check(0)\n'+text[at:]
        (out/(name+'.act')).write_text(text)

    for name, routines in (
        ('aeswindowstate', ('Publish', 'BeginUpdate', 'EndUpdate', 'Sync')),
        ('aeswindow', ('Request', 'Lifecycle', 'SetBounds')),
        ('aeslocks', ('Attempt',)),
        ('aeshost', ('Settled', 'Settle')),
        ('deskhost', ('Controls', 'Runnable', 'Cache', 'Ready', 'PaintReady')),
        ('deskpaint', ('Pump', 'Ready', 'Runnable', 'Sync')),
        ('deskcache', ('Pump', 'Capture', 'Patch', 'Restore')),
    ):
        shadow(name, routines)
    local = read_source(ROOT/'lib/aes/aeslocal.act').replace('USE AESGATE\n',
        'USE AESGATE\nUSE SCENEPROBE\n', 1)
    needle = '  LET client=AESSTATE.Find(service,request.client)'
    require(local.count(needle) == 1, 'Local scene admission boundary changed')
    local = local.replace(needle, needle+'\n  SCENEPROBE.Pause(1,client.id)')
    (out/'aeslocal.act').write_text(local)
    bitmap = read_source(ROOT/'lib/console/consolebitmap.act').replace('USE AESGATE\n',
        'USE AESGATE\nUSE SCENEPROBE\n', 1)
    needle = '  LET held=AESGATE.Suspend()\n  Call(state.entry)'
    require(bitmap.count(needle) == 1, 'Bitmap physical boundary changed')
    bitmap = bitmap.replace(needle, '  LET held=AESGATE.Suspend()\n'
        '  SCENEPROBE.Check(1)\n  Call(state.entry)\n'
        '  IF operation=OP_POINTER AND packet.status=DISPLAY.OK THEN\n'
        '    SCENEPROBE.cursorX=packet.x\n    SCENEPROBE.cursorY=packet.y\n  FI')
    bitmap = bitmap.replace('  AESGATE.Resume(held)',
        '  IF held<>0 AND ((operation=OP_COPY_START AND SCENEPROBE.PointerCase()=0)\n'
        '      OR (operation=OP_POINTER AND SCENEPROBE.PointerCase()<>0)) THEN\n'
        '    SCENEPROBE.Pause(2,0)\n  FI\n  AESGATE.Resume(held)', 1)
    (out/'consolebitmap.act').write_text(bitmap)
    deferred = read_source(ROOT/'lib/aes/aesdefer.act').replace('USE EXEC\n',
        'USE EXEC\nUSE SCENEPROBE\n', 1)
    deferred = deferred.replace('\nRETURN\n',
        '\n  SCENEPROBE.Observe(consumed,bits)\nRETURN\n', 1)
    (out/'aesdefer.act').write_text(deferred)

    import build_bitmap_console as builder
    import generate_tasks
    original, task_entries = builder.prepare, generate_tasks.task_entries
    original_policy = generate_tasks.policy_modules

    def prepare(path, directory, foreign, *args):
        def bind(text):
            return re.sub(r'\$(AESService|AESRun|Scene\w+)',
                          lambda m: f'${foreign["symbols"][m[1]]:x}', text)
        path.write_text(bind(path.read_text()))
        (out/'sceneprobe.act').write_text(bind(probe))
        return original(path, directory, foreign, *args)

    def entries(image):
        setup = {r['address'] for r in image['routines']
                 if r['name'].startswith('M_SCENETEST_BIND')}
        return [entry for entry in task_entries(image) if entry not in setup]

    def policy(*args, **kwargs):
        directory = original_policy(*args, **kwargs)
        text = bitmap.replace('"console-storage-action.inc"',
            '"'+str(directory.parent/'console-storage-action.inc')+'"')
        (directory/'consolebitmap.act').write_text(text)
        return directory

    builder.prepare, generate_tasks.task_entries = prepare, entries
    generate_tasks.policy_modules = policy
    roots = ['AESRun', 'AESService', 'AESChecks', 'AESFailures', 'AESFirstFailure',
             'SceneVariant', 'ScenePhase', 'SceneGo', 'SceneHolderGo', 'SceneHeld',
             'SceneHoldGo', 'SceneEffectArm', 'SceneEffectHeld', 'SceneEffectGo',
             'SceneReady', 'SceneSeen', 'SceneSend', 'SceneSent', 'SceneStop',
             'SceneHoldClient', 'ScenePeer', 'SceneView', 'SceneWaiterTask', 'SceneWaiterGo']
    try:
        return build_bitmap(source, out, desktop=True, aes=True, fault=True,
            release_compiler=True,
            client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c',
                            ROOT/'c/calypsi/aes-events.c', ROOT/'tests/programs/aes_scene.c'],
            client_entries=['SceneHolder', 'SceneWorker', 'SceneWaiter'], client_roots=roots)
    finally:
        builder.prepare, generate_tasks.task_entries = original, task_entries
        generate_tasks.policy_modules = original_policy


def run(out, reuse=False, variants=(0, 1, 2)):
    out.mkdir(parents=True, exist_ok=True)
    program = read_build(out/'program') if reuse else build(out)
    sy = json.loads((out/'c-image.json').read_text())['symbols']
    at = lambda module, name: next(d['address'] for d in program['image']['data']
        if d['name'].startswith(f'M_{module}_{name.upper()}_'))
    report = dict(status='running', tier='development', qualification=False,
                  build=program['build'], cases=[])
    try:
        for variant in variants:
            row = dict(variant=variant)
            report['cases'].append(row)
            with emulator(BRIDGE, ROM, out/f'variant-{variant}', pin=PIN) as b:
                report['machine'] = verify_machine(b, ROM, PIN)
                get = lambda p, n=4: int.from_bytes(b.memdump(p, n), 'little')

                def reach(condition, frame_limit=6000):
                    b.bp_clear_all()
                    b.bp_set(program['labels']['native_irq'], condition=condition)
                    b.bp_set(program['labels']['done'], condition=adapter.STOPPED)
                    run_to(b, program['labels']['native_irq'], condition=condition,
                           timeout=120, frame_limit=frame_limit)

                def frames(n):
                    reach(f'@frame>={b.eval_expr("@frame")+n}')

                def before(_):
                    b.poke16(sy['SceneVariant'], variant)
                    b._cmd_ok('MOUSE ST')
                    reach(f'dw(${sy["ScenePhase"]:x})=1')
                    frames(100)
                    current = [get(at('DESKINPUT', v), 2) for v in ('cursorX', 'cursorY')]
                    target = schedule(b, program, current, (100, 80))
                    reach(f'(dw(${at("DESKINPUT", "cursorX"):x})={target[0]})&'
                          f'(dw(${at("DESKINPUT", "cursorY"):x})={target[1]})')
                    frames(4)
                    b.poke16(sy['SceneGo'], 1)
                    if variant:
                        if variant == 2:
                            reach(f'dw(${sy["ScenePhase"]:x})=2')
                            schedule(b, program, target, (120, 90))
                        reach(f'dw(${sy["SceneEffectHeld"]:x})=1')
                        if variant == 1:
                            require(get(at('CONSOLEBITMAP', 'drawingPending'), 1) == 1,
                                    'Move did not retain an asynchronous copy')
                        b.poke16(sy['SceneHolderGo'], 1)
                    reach(f'dw(${sy["SceneHeld"]:x})=1')
                    gate = get(at('SCENEPROBE', 'gateAddress'))
                    token = get(at('SCENEPROBE', 'tokenAddress'))
                    require(get(gate, 1) == 2, 'Caller did not retain scene ownership')
                    b.poke16(sy['SceneWaiterGo'], 1)
                    waiters = get(at('SCENEPROBE', 'waitersAddress'))
                    reach(f'dw(${waiters:x})>0', frame_limit=100)
                    state = next(f[2] for f in TASK_ABI['task']['fields'] if f[0] == 'tc_State')
                    waiter_task=get(sy['SceneWaiterTask'])
                    reach(f'db(${waiter_task+state:x})={TASK_ABI["states"]["WAIT"]}',
                          frame_limit=100)
                    require(get(get(sy['SceneWaiterTask'])+state, 1) == TASK_ABI['states']['WAIT'],
                            'Contended caller did not sleep after publishing its waiter')
                    row['caller_waiting'] = True
                    start = get(sy['ScenePeer'])
                    if variant:
                        b.poke16(sy['SceneEffectGo'], 1)
                    if variant == 1:
                        row['retained_token'] = get(token)
                        require(row['retained_token'] != 0, 'Copy lost its Layers token')
                        reach(f'db(${at("CONSOLEBITMAP", "drawingPending"):x})=0')
                        require(get(token) == row['retained_token'],
                                'Physical completion committed unowned scene metadata')
                        require(get(at('CONSOLEBITMAP', 'physicalCompleted'), 1) == 1,
                                'Physical completion was not retained for scene adoption')
                        row['fence_retired_without_scene'] = True
                        view = get(sy['SceneView'])
                        bounds = aes_layout()['WindowView']['fields']['bounds']
                        require(get(view+bounds, 2) == 32 and get(view+bounds+2, 2) == 32,
                                'DMA completion published speculative caller geometry')
                    if variant == 2:
                        # A pause changes capture coalescing/acceleration. Let
                        # each electrical motion finish, then compare rendering
                        # with the actual captured position rather than a
                        # predicted acceleration result.
                        frames(20)
                        current = [get(at('DESKINPUT', v), 2) for v in ('cursorX', 'cursorY')]
                        schedule(b, program, current, (140, 100))
                        frames(20)
                        target = [get(at('DESKINPUT', v), 2) for v in ('cursorX', 'cursorY')]
                        drawn = [get(at('SCENEPROBE', v), 2) for v in ('cursorX', 'cursorY')]
                        require(target != drawn, 'Cursor case captured no newer position')
                        row['captured_pointer'] = target
                    b._cmd_ok('KEY A down')
                    frames(3)
                    b._cmd_ok('KEY A up')
                    b._cmd_ok('MOUSE AT 2000 0 0 1')
                    frames(4)
                    b._cmd_ok('MOUSE AT 2000 0 0 0')
                    frames(4)
                    if not variant:
                        reach(f'dw(${sy["ScenePhase"]:x})=3', frame_limit=300)
                        row['delivered_event_bits'] = get(sy['SceneSeen'], 2)
                        require(row['delivered_event_bits'] == 51,
                                'Missing keyboard/button/message/timer during scene contention')
                    require(get(gate, 1) == 2, 'Input work stole caller scene ownership')
                    require(get(sy['ScenePeer']) != start, 'Headless peer stalled')
                    owner = get(get(at('SCENEPROBE', 'taskAddress')), 3)
                    state = next(f[2] for f in TASK_ABI['task']['fields'] if f[0] == 'tc_State')
                    reach(f'db(${owner+state:x})={TASK_ABI["states"]["WAIT"]}',
                          frame_limit=100)
                    require(get(owner+state, 1) == TASK_ABI['states']['WAIT'],
                            'Deferred presenter spins on pending work')
                    row['presenter_waiting'] = True
                    row['peer_progress'] = get(sy['ScenePeer'])-start
                    b.poke16(sy['SceneHoldGo'], 1)
                    if variant == 2:
                        reach(f'(dw(${at("SCENEPROBE", "cursorX"):x})={target[0]})&'
                              f'(dw(${at("SCENEPROBE", "cursorY"):x})={target[1]})',
                              frame_limit=100)
                        row['cursor_redrawn_without_new_input'] = True
                    reach(f'dw(${sy["ScenePhase"]:x})=3')
                    b.poke16(sy['SceneGo'], 3)
                    b.bp_clear_all()

                try:
                    row['runtime'], _ = execute(b, program, before_run=before,
                        timeout=120, frame_limit=6000)
                except Exception:
                    row['diagnostic'] = {name: get(sy[name], 4 if name in
                        ('SceneHoldClient', 'ScenePeer', 'SceneWaiterTask') else 2)
                        for name in ('ScenePhase', 'SceneHeld', 'SceneSeen', 'SceneSent',
                                     'SceneHoldClient', 'ScenePeer', 'SceneWaiterTask')}
                    row['checks'] = get(sy['AESChecks'], 2)
                    row['failures'] = get(sy['AESFailures'], 2)
                    row['first_failure'] = get(sy['AESFirstFailure'], 2)
                    row['dispatcher'] = {name: get(at('SCENEPROBE', name),
                        2 if name in ('keyTail', 'buttonTail', 'eligible') else 4)
                        for name in ('deferredCalls', 'seenBits', 'lastConsumed',
                                     'rootInbox', 'routeEpoch', 'keyTail', 'buttonTail', 'eligible')}
                    row['pointer'] = {name: get(at('DESKINPUT', name), n)
                        for name, n in (('pending', 1), ('acquired', 1), ('cursorX', 2), ('cursorY', 2))}
                    row['independent_mask'] = get(at('AESGATE', 'independentMask'))
                    row['pointer_mask'] = get(at('DESKINPUT', 'wakeMask'))
                    owner = get(get(at('SCENEPROBE', 'taskAddress')), 3)
                    offset = next(f[2] for f in TASK_ABI['task']['fields'] if f[0] == 'tc_SigRecvd')
                    row['presenter_signals'] = get(owner+offset)
                    row['waiter_root'] = get(get(at('SCENEPROBE', 'waitersAddress')), 3)
                    raise
                ownership(b, program, program['output'])
                row['stacks'] = stack_usage(b, program['build']['memory'])
                require(all(s['remaining_above_floor'] >= 0
                            for s in row['stacks'].values()),
                        'Scene fixture exceeded its interrupt floor')
                row['checks'] = get(sy['AESChecks'], 2)
                row['failures'] = get(sy['AESFailures'], 2)
                row['first_failure'] = get(sy['AESFirstFailure'], 2)
                require(row['checks'] >= 25 and row['failures'] == 0,
                        'Incomplete scene fixture: '+str(row))
                row['scene_checks'] = get(at('SCENEPROBE', 'sceneChecks'))
                row['physical_checks'] = get(at('SCENEPROBE', 'physicalChecks'))
                require(row['scene_checks'] > 0 and row['physical_checks'] > 0,
                        'Missing emitted scene/physical ownership assertions')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES scene phases passed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--variant', type=int, choices=(0, 1, 2), action='append')
    args = parser.parse_args()
    run(args.output.resolve(), args.reuse, args.variant or (0, 1, 2))
