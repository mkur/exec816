#!/usr/bin/env python3
"""Observe reserved moves across preemption, quiescent failure and reset park."""
import argparse
import json
from pathlib import Path
import struct

import adapter_state as adapter
from build_bitmap_console import build_bitmap
from generate_aes_server import layout as aes_layout
from generate_desktop import ABI as DESKTOP_ABI, layout as desktop_layout
from generate_layers import layout as layers_layout
from generate_input_native import definitions as input_definitions
from library_paths import read_source
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def build(out,reuse_c=False):
    probe = '''MODULE WINDOWEFFECTPROBE
USE EXEC
USE AESGATE
USE AESTYPES
PUBLIC BYTE stage,release
PUBLIC LONGCARD guiEpochAddress,tokenAddress,windowAddress,requestAddress
PUBLIC PROC Pause(BYTE value AESTYPES.Request POINTER request)

  LET held=IF value<3 THEN AESGATE.Leave() ELSE BYTE(0) FI
  stage=value
  WHILE release<value DO
    EXEC.Yield()
  OD
  IF value<3 THEN
    AESGATE.Reenter(held,request)
  FI

RETURN
ENDMODULE
'''
    (out/'windoweffectprobe.act').write_text(probe)
    move = read_source(ROOT/'lib/desktop/deskmove.act')
    move = move.replace('USE AESTYPES\n', 'USE AESTYPES\nUSE WINDOWEFFECTPROBE\n', 1)
    needle='      AESFRAME.Apply(@packet,request)'
    require(move.count(needle)==1,'Caller copied-move fence boundary changed')
    move=move.replace(needle,"""      WINDOWEFFECTPROBE.tokenAddress=LONGCARD(ADDRESS(@token))
      WINDOWEFFECTPROBE.windowAddress=LONGCARD(ADDRESS(window))
      WINDOWEFFECTPROBE.requestAddress=LONGCARD(ADDRESS(request))
      WINDOWEFFECTPROBE.Pause(1,request)
"""+needle+'\n      WINDOWEFFECTPROBE.Pause(2,request)',1)
    (out/'deskmove.act').write_text(move)
    routes = read_source(ROOT/'lib/aes/aesroutes.act')
    routes = routes.replace('USE AESTYPES\n', 'USE AESTYPES\nUSE WINDOWEFFECTPROBE\n', 1)
    drain = '  LET held=AESGATE.Leave()'
    require(routes.count(drain) == 1, 'Close route retirement boundary changed')
    routes = routes.replace(drain, drain+'\n  WINDOWEFFECTPROBE.Pause(3,request)')
    (out/'aesroutes.act').write_text(routes)
    source = out/'window-effects.act'
    source.write_text('''MODULE WINDOWEFFECTS
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE AESGATE
USE AESLOCKS
USE DESKSTATE
USE CONSOLEBITMAP
USE HEAPCORE
USE WINDOWEFFECTPROBE
CARD FUNC POINTER run()
PROC Main()

  LET service=AESSTATE.Get()
  WINDOWEFFECTPROBE.guiEpochAddress=LONGCARD(ADDRESS(@service.nextGuiEpoch))
  LET endpoint=LONGCARD POINTER($AES_SERVICE)
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET entry=ADDRESS POINTER(@run)
  entry^=$AES_RUN
  LET result=run()
  IF result<>0 OR service.count<>0 THEN
    HEAPCORE.Abort($fc40)
  FI
  BEGIN
    BYTE pending

    LET bit=EXEC.AllocSignal(-1)
    LET desktop=DESKSTATE.Get()
    DO
      AESLOCKS.ObtainUI()
      AESGATE.EnterTask(EXEC.FindTask(NULL),LONGCARD(1) LSH bit)
      pending=(desktop.scene.visibleDamage<>0 AND CONSOLEBITMAP.Failed()=0)
          OR CONSOLEBITMAP.Pending()<>0
          OR desktop.scene.busy<>0 OR service.policyEffects<>0
          OR AESCORE.Runnable(service)<>0
      AESGATE.Release(0)
      AESLOCKS.ReleaseUI()
      IF pending=0 THEN
        EXIT
      FI
      EXEC.Yield()
    OD
    EXEC.FreeSignal(bit)
  END

RETURN
ENDMODULE
''')
    # Replace the two fixture symbols after the common C renderer is linked.
    import build_bitmap_console as builder
    original = builder.prepare
    original_emit=builder.emit
    original_drawing=builder.drawing

    def prepare(path, directory, foreign, *args):
        text = path.read_text().replace('$AES_SERVICE', f'${foreign["symbols"]["AESService"]:x}')
        text = text.replace('$AES_RUN', f'${foreign["symbols"]["AESRun"]:x}')
        path.write_text(text)
        launcher=original(path,directory,foreign,*args)
        text=launcher.read_text()
        needle='  IF CONSOLEDRIVER.Stop()=0 THEN\n    HEAPCORE.Abort($f732)\n  FI'
        require(text.count(needle)==1,'Console stop boundary changed')
        # A manager can be preempted in an otherwise empty UPDATE probe. Stop
        # legitimately reports busy; bounded fixture retries preserve that API.
        text=text.replace(needle,"""  BEGIN
    CARD attempts

    attempts=0
    WHILE CONSOLEDRIVER.Stop()=0 DO
      attempts==+1
      IF attempts=64 THEN
        HEAPCORE.Abort($f732)
      FI
      EXEC.Yield()
    OD
  END""",1)
        launcher.write_text(text)
        return launcher

    def emit(directory,sources,*args,**kwargs):
        # The move now uses synchronous typed copying. Inject after its actual
        # launch, keeping the existing watchdog and stop/recovery hooks.
        hardware=next(p for p in sources if p.name=='vbxe-fault.c')
        text=hardware.read_text()
        text=text.replace('static UWORD submit(',
            'static UBYTE effectCopyArmed;\nstatic UWORD submit(',1)
        needle='    launch(d,records,count);\n    return VbxeOwnerFence(d);'
        require(text.count(needle)==1,'Typed-copy fence boundary changed')
        text=text.replace(needle,'    launch(d,records,count);\n'
            '    if (effectCopyArmed) { effectCopyArmed=0; ConsoleFaultCopy(); }\n'
            '    return VbxeOwnerFence(d);',1)
        needle='        copy_record(bcb,&copy,rows);\n        return submit(d,bcb,1);'
        require(text.count(needle)==1,'Typed screen-copy admission changed')
        text=text.replace(needle,'        copy_record(bcb,&copy,rows);\n'
            '        effectCopyArmed=1;\n        return submit(d,bcb,1);',1)
        hardware.write_text(text)
        return original_emit(directory,sources,*args,**kwargs)

    import generate_tasks
    task_entries = generate_tasks.task_entries

    def entries(image):
        setup = {r['address'] for r in image['routines']
                 if r['name'].startswith('M_WINDOWEFFECTS_BIND')}
        return [entry for entry in task_entries(image) if entry not in setup]

    builder.prepare = prepare
    builder.emit=emit
    if reuse_c:
        from native_program import sha256
        cached=json.loads((out/'c-image.json').read_text())
        for name,digest in {**cached['provenance']['source_inputs'],
                            **cached['provenance']['header_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Changed cached C input: '+name)
        builder.drawing=lambda *args,**kwargs:cached
    generate_tasks.task_entries = entries
    try:
        return build_bitmap(source, out, desktop=True, aes=True, fault=True,
            release_compiler=True,
            client_sources=[ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c',
                            ROOT/'c/calypsi/aes-events.c', ROOT/'tests/programs/aes_window_effects.c'],
            client_entries=['EffectWorker'],
            client_roots=['AESRun', 'AESService', 'AESChecks', 'AESFailures',
                          'AESFirstFailure', 'EffectPhase', 'EffectGo', 'EffectVariant',
                          'EffectPeer', 'EffectView', 'EffectQueryArm',
                          'EffectQueryDone', 'EffectQueryResult', 'EffectQueryStatus',
                          'EffectQueryX', 'EffectQueryY'])
    finally:
        builder.prepare = original
        builder.emit=original_emit
        builder.drawing=original_drawing
        generate_tasks.task_entries = task_entries


def run(out, reuse=False, variants=(0, 3, 4), reuse_c=False):
    out.mkdir(parents=True, exist_ok=True)
    program = read_build(out/'program') if reuse else build(out,reuse_c)
    symbols = json.loads((out/'c-image.json').read_text())['symbols']
    at = lambda module, name: next(d['address'] for d in program['image']['data']
                                   if d['name'].startswith(f'M_{module}_{name.upper()}_'))
    report = dict(status='running', tier='development', qualification=False,
                  build=program['build'], cases=[])
    df, lf, af = desktop_layout(), layers_layout(), aes_layout()
    try:
        for variant in variants:
            folder = out/f'variant-{variant}'
            row = dict(variant=variant, boundaries=[])
            report['cases'].append(row)
            with emulator(BRIDGE, ROM, folder, pin=PIN) as bridge:
                report['machine'] = verify_machine(bridge, ROM, PIN)
                get = lambda address, size=4: int.from_bytes(bridge.memdump(address, size), 'little')
                scene = None

                def reach(condition):
                    bridge.bp_clear_all()
                    bridge.bp_set(program['labels']['native_irq'], condition=condition)
                    bridge.bp_set(program['labels']['done'], condition=adapter.STOPPED)
                    run_to(bridge, program['labels']['native_irq'], condition=condition,
                           timeout=120, frame_limit=6000)

                def phase(number):
                    reach(f'dw(${symbols["EffectPhase"]:x})={number}')

                def before(_):
                    nonlocal scene
                    bridge.poke16(symbols['EffectVariant'], variant)
                    phase(1)
                    desktop = get(at('DESKSTATE', 'service'), 3)
                    scene = desktop+df['Service']['fields']['scene']
                    epoch_at = get(at('WINDOWEFFECTPROBE', 'guiEpochAddress'))
                    epoch = get(epoch_at)
                    tags_at = program['build']['memory']['input_storage']['STATE']+input_definitions()[0]['STATE_TAGS']
                    tags = bridge.memdump(tags_at, 64)
                    bridge.memload(epoch_at, bytes(4))
                    bridge.poke16(symbols['EffectGo'], 1)
                    phase(2)
                    view = get(symbols['EffectView'])
                    windows = desktop+df['Service']['fields']['windows']
                    slot = next(i for i in range(DESKTOP_ABI['constants']['WINDOWS'])
                                if get(windows+i*df['Window']['size']
                                    +df['Window']['fields']['id'], 4) != 0)
                    window = windows+slot*df['Window']['size']
                    require(get(window+df['Window']['fields']['keyRoute']) == 0,
                            'Failed open published its route')
                    require(bridge.memdump(tags_at, 64) == tags,
                            'Failed open leaked an input route')
                    bridge.memload(epoch_at, epoch.to_bytes(4, 'little'))
                    bridge.poke16(symbols['EffectGo'], 2)
                    phase(3)
                    reach(f'@frame>={bridge.eval_expr("@frame")+100}')
                    bridge.poke16(symbols['EffectGo'], 3)
                    layer_id = get(window+df['Window']['fields']['layer'])
                    layers = scene+lf['Scene']['fields']['items']
                    layer = next(layers+i*lf['Layer']['size'] for i in range(9)
                                 if get(layers+i*lf['Layer']['size']) == layer_id)
                    old = struct.pack('<hhhh', 32, 32, 192, 128)
                    for boundary in (1, 2):
                        reach(f'db(${at("WINDOWEFFECTPROBE", "stage"):x})={boundary}')
                        require(get(scene+lf['Scene']['fields']['busy']) != 0,
                                'Move lost logical ownership')
                        require(get(at('WINDOWEFFECTPROBE','windowAddress')) == window
                                and get(at('WINDOWEFFECTPROBE','requestAddress')) != 0
                                and get(get(at('WINDOWEFFECTPROBE','tokenAddress'))) != 0,
                                'Move lost caller-owned window/request/token')
                        require(bridge.memdump(layer+lf['Layer']['fields']['bounds'], 8) == old,
                                'Effect published speculative layer geometry')
                        require(bridge.memdump(view+af['WindowView']['fields']['bounds'], 8) == old,
                                'Effect published speculative caller geometry')
                        bridge.poke16(symbols['EffectQueryDone'], 0)
                        bridge.poke16(symbols['EffectQueryArm'], 1)
                        reach(f'dw(${symbols["EffectQueryDone"]:x})=1')
                        query=get(symbols['EffectQueryResult'], 2)
                        require(query==get(view+af['WindowView']['fields']['handle'], 2)
                                and get(symbols['EffectQueryStatus'], 2)==0,
                                'Lookup waited for copy or observed speculative geometry')
                        start = get(symbols['EffectPeer'])
                        frame = bridge.eval_expr('@frame')
                        reach(f'@frame>={frame+4}')
                        require(get(symbols['EffectPeer']) != start, 'Peer stalled during effect')
                        row['boundaries'].append(dict(stage=boundary, frames=4,
                            peer_before=start, peer_after=get(symbols['EffectPeer']),
                            scene_token=get(scene+lf['Scene']['fields']['busy']),
                            committed_lookup=query,
                            copy_chunks=get(symbols['ConsoleCopyChunks'], 2)))
                        bridge.poke(at('WINDOWEFFECTPROBE', 'release'), boundary)
                        if variant == 4:
                            bridge.bp_clear_all()
                            return
                    phase(4)
                    bridge.poke16(symbols['EffectGo'], 4)
                    reach(f'db(${at("WINDOWEFFECTPROBE", "stage"):x})=3')
                    require(get(view+af['WindowView']['fields']['shown'], 2) == 0
                            and get(view+af['WindowView']['fields']['epoch']) == 0,
                            'Route drain retained a published open window')
                    require(get(window+df['Window']['fields']['keyRoute']) != 0,
                            'Close discarded its pending retirement tag')
                    bounds = view+af['WindowView']['fields']['bounds']
                    bridge.poke16(symbols['EffectQueryX'], get(bounds, 2)+8)
                    bridge.poke16(symbols['EffectQueryY'], get(bounds+2, 2)+8)
                    bridge.poke16(symbols['EffectQueryDone'], 0)
                    bridge.poke16(symbols['EffectQueryArm'], 1)
                    reach(f'dw(${symbols["EffectQueryDone"]:x})=1')
                    require(get(symbols['EffectQueryResult'], 2)==0
                            and get(symbols['EffectQueryStatus'], 2)==0,
                            'Lookup waited for route drain or found the withdrawn window')
                    start = get(symbols['EffectPeer'])
                    reach(f'@frame>={bridge.eval_expr("@frame")+4}')
                    require(get(symbols['EffectPeer']) != start, 'Peer stalled during route drain')
                    row['close_before_drain'] = dict(shown=0, epoch=0,
                        retained_route=True, committed_lookup=0, query_completed=True)
                    bridge.poke(at('WINDOWEFFECTPROBE', 'release'), 3)
                    bridge.bp_clear_all()

                try:
                    row['runtime'], _ = execute(bridge, program, before_run=before,
                        expected_status=0xff93 if variant == 4 else 0, timeout=120, frame_limit=6000)
                except Exception:
                    # Private layout diagnostics, never a production access path.
                    row['failure_state']={name:get(symbols[name],size) for name,size in
                        [('EffectPhase',2),('peerDone',2),('EffectPeer',4),('AESChecks',2),('AESFailures',2)]}
                    row['failure_state'].update(boot_cause=get(adapter.BOOT_CAUSE,2),systemHeld=get(at('AESLOCKS','systemHeld'),1),
                        systemDepth=get(at('AESLOCKS','systemDepth'),2))
                    rf=af['Request']['fields']
                    row['failure_state']['requests']=[]
                    for index in range(8):
                        context=get(symbols['contexts']+4*index)
                        if context:
                            row['failure_state']['requests'].append({name:get(context+rf[name],size)
                                for name,size in [('owner',3),('client',4),('operation',2),('status',2)]})
                    raise
                row['checks'] = get(symbols['AESChecks'], 2)
                row['failures'] = get(symbols['AESFailures'], 2)
                row['first_failure'] = get(symbols['AESFirstFailure'], 2)
                require(row['failures'] == 0, 'Window effect C assertion failed')
                if variant == 4:
                    require(get(scene+lf['Scene']['fields']['busy']) != 0
                            and get(get(at('WINDOWEFFECTPROBE','tokenAddress'))) != 0
                            and get(at('WINDOWEFFECTPROBE','windowAddress')) != 0
                            and get(at('WINDOWEFFECTPROBE','requestAddress')) != 0,
                            'Unquiesced copy released retained operation storage')
                else:
                    ownership(bridge, program, program['output'])
                    minimum_checks = 29 if variant == 0 else 24
                    require(row['checks'] >= minimum_checks, 'Incomplete window effect fixture')
                row['copy_chunks'] = get(symbols['ConsoleCopyChunks'], 2)
                row['stop_count'] = get(symbols['ConsoleStopCount'], 2)
                # Later frame repair also submits copies. Measure the move
                # between its reserved effect and completion boundaries.
                copies_after_move = row['copy_chunks']
                if variant != 4:
                    copies_after_move = row['boundaries'][1]['copy_chunks']
                row['move_copy_chunks'] = copies_after_move-row['boundaries'][0]['copy_chunks']
                require(row['move_copy_chunks'] == 1,
                        'Expected one move copy, observed '+str(row['move_copy_chunks']))
                require(row['stop_count'] == (1 if variant else 0),
                        'Unexpected watchdog stop count')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('AES window effect boundaries passed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--reuse-c',action='store_true')
    parser.add_argument('--variant', type=int, choices=(0, 3, 4), action='append')
    args = parser.parse_args()
    run(args.output.resolve(), args.reuse, args.variant or (0, 3, 4),args.reuse_c)
