#!/usr/bin/env python3
"""Small UPDATE owner/contender/counter scene; selected development checks."""
import argparse,json
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout,layout
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,PIN,ROM
from stack_budget import stack_usage
from desktop_mouse import schedule
from generate_tasks import ABI as TASKS


def inputs():
    paths=[ROOT/'tests/programs/aes_migration.c']
    for folder in ('c','lib','abi','platform/altirraos','config','toolchain'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file()]
    paths += [ROOT/'tools'/n for n in ('native_program.py','generate_tasks.py','generate_aes_server.py','build_bitmap_console.py','test_aes_migration.py')]
    return {str(p.relative_to(ROOT)):sha256(p) for p in sorted(set(paths))}


def run(out,reuse=False,reuse_c=False):
    out.mkdir(parents=True,exist_ok=True)
    frozen=inputs()
    if reuse:
        require(json.loads((out/'inputs.json').read_text())==frozen,'Changed migration build inputs')
        p=read_build(out/'program');foreign=json.loads((out/'c-image.json').read_text())
    else:
        selected=drawing
        if reuse_c:
            cached=json.loads((out/'c-image.json').read_text())
            for name,digest in {**cached['provenance']['source_inputs'],
                                **cached['provenance']['header_inputs']}.items():
                require(sha256(ROOT/name)==digest,'Changed C input: '+name)
            selected=lambda *args,**kwargs:cached
        foreign=selected(out,True,desktop_style=True,client_sources=[
            ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
            ROOT/'tests/programs/aes_migration.c'],client_entries=['MigrationPeer','MigrationCounter'],
            client_roots=['AESRun','AESService','AESChecks','AESFailures'],
            client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout())])
        sy=foreign['symbols']
        bindings=''
        for name,field in [('AESUpdates','updates'),('AESMouseHolds','mouseHolds')]:
            bindings+=f'  BEGIN\n    LET cell=LONGCARD POINTER(${sy[name]:x})\n    cell^=LONGCARD(ADDRESS(@service.{field}))\n  END\n'
        source=out/'migration.act'
        offset=next(o for n,k,o in TASKS['context']['fields'] if n=='semaphoreOwned')
        source.write_text(f'''MODULE AESMIGRATION
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE AESLOCKS
USE AESDRAWSTATE
USE CONSOLEBITMAP
USE DESKSTATE
USE HEAPCORE
CARD checks
CARD FUNC POINTER entry()
PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fc40+checks)
  FI
  checks==+1

RETURN

PROC Main()

  LET service=AESSTATE.Get()
  LET port=LONGCARD POINTER(${sy['AESService']:x})
  port^=LONGCARD(ADDRESS(AESBOOT.Port()))
{bindings}
  LET owned=CARD POINTER(${sy['AESOwnedOffset']:x})
  owned^={offset}
  LET call=ADDRESS POINTER(@entry)
  call^=${sy['AESRun']:x}
  Require(AESDRAWSTATE.Packet()<>CONSOLEBITMAP.GetPacket())
  Require(entry()=0)
  BEGIN
    BYTE pending

    LET desktop=DESKSTATE.Get()
    DO
      AESLOCKS.ObtainUI()
      pending=desktop.scene.visibleDamage<>0 OR CONSOLEBITMAP.Pending()<>0
          OR AESCORE.Runnable(service)<>0
          OR desktop.scene.busy<>0
      AESLOCKS.ReleaseUI()
      IF pending=0 THEN
        EXIT
      FI
      EXEC.Yield()
    OD
  END
  Require(service.count=0 AND AESCORE.Idle(service)<>0)

RETURN
ENDMODULE
''')
        launcher=prepare(source,out,foreign,desktop=True,aes=True)
        from generate_memory import PROFILE
        memory=json.loads(PROFILE.read_text());memory['image_data_bytes']=8192
        profile=out/'fixture-memory.json'
        profile.write_text(json.dumps(memory,indent=2)+'\n')
        p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',
            optimize=True,tasks=True,task_capacity=8,foreign_image=foreign,
            console_deferred=True,memory_profile=profile)
        from generate_mouse_acceleration import metadata
        p['build']['desktop_mouse']=metadata(None)
        (p['output']/'build.json').write_text(json.dumps(p['build'],indent=2)+'\n')
        (out/'inputs.json').write_text(json.dumps(frozen,indent=2)+'\n')
    report=dict(status='running',tier='development',qualification=False,build=p['build'],
                pin=PIN,runner_sha256=sha256(Path(__file__)),reserved_bank_zero_delta=dict(
                    fixed=0,root=0,kernel=0,idle=0,per_public_task=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def before(_):
                sy=foreign['symbols']
                def reach(condition):
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    run_to(b,p['labels']['native_irq'],condition=condition,timeout=90,frame_limit=4500)
                def frames(count):reach(f'@frame>={b.eval_expr("@frame")+count}')
                b._cmd_ok('MOUSE ST')
                reach(f'dw(${sy["callbackReady"]:x})=1');frames(30)
                def cell(name):return b.eval_expr(f'dw(${sy[name]:x})')
                at=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
                current=[int.from_bytes(b.memdump(at(n),2),'little') for n in ('cursorX','cursorY')]
                target=schedule(b,p,current,(cell('callbackX'),cell('callbackY')))
                reach(f'(dw(${at("cursorX"):x})={target[0]})&(dw(${at("cursorY"):x})={target[1]})')
                frames(4);b._cmd_ok('MOUSE AT 2000 0 0 1');frames(4)
                b._cmd_ok('MOUSE AT 2000 0 0 0')
                reach(f'dw(${sy["keyboardReady"]:x})=1');frames(30)
                records=layout()
                inbox=int.from_bytes(b.memdump(sy['keyboardInbox'],4),'little')
                require(inbox!=0,'Missing registered keyboard inbox')
                tail=inbox+records['InputInbox']['fields']['keyTail']
                head=inbox+records['InputInbox']['fields']['keyHead']
                previous=b.memdump(tail,1)[0]
                prior_head=b.memdump(head,1)[0]
                # Observe publication before its recipient consumes the key.
                # IRQ rendezvous also covers native fast calls that do not
                # enter the slow COP policy dispatcher.
                marker=p['labels']['native_irq']
                condition=f'(db(${tail:x})={(previous+1)&255})&(db(${head:x})={prior_head})'
                report['keyboard_observer']=dict(inbox=inbox,
                    prior_head=prior_head,prior_tail=previous)
                held=next(d['address'] for d in p['image']['data']
                          if '_AESLOCKS_SYSTEMHELD_' in d['name'])
                depth=next(d['address'] for d in p['image']['data']
                           if '_AESLOCKS_SYSTEMDEPTH_' in d['name'])
                b.bp_clear_all();b.bp_set(marker,condition=condition)
                b._cmd_ok('KEY A down')
                run_to(b,marker,condition=condition,timeout=60,frame_limit=3000)
                report['keyboard_delivery']=dict(
                    presenter_held=b.memdump(held,1)[0],
                    presenter_depth=int.from_bytes(b.memdump(depth,2),'little'))
                require(report['keyboard_delivery']==dict(presenter_held=0,presenter_depth=0),
                        'Ordinary key delivery retained presenter UPDATE')
                b._cmd_ok('KEY A up')
                b.bp_clear_all()
            try:
                report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=6000)
            finally:
                for name in ('AESChecks','AESFailures','AESFirstFailure','progress','phase','callbackReady','keyboardReady'):
                    report[name]=b.eval_expr(f'dw(${foreign["symbols"][name]:x})')
                report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(report['AESFailures']==0 and report['AESChecks']>=35,'UPDATE migration fixture failed')
            require(report['progress']>0 and report['phase']==3 and report['callbackReady']==2,'Missing callback/peer/counter progress')
            require(report['keyboardReady']==2,'Missing key/UPDATE completion')
            ownership(b,p,p['output'])
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AES migration passed;',report['AESChecks'],'checks')
    return report


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--from-build',action='store_true')
    a.add_argument('--reuse-c',action='store_true')
    args=a.parse_args();run(args.output.resolve(),args.from_build,args.reuse_c)
