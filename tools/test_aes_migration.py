#!/usr/bin/env python3
"""Small UPDATE owner/contender/counter scene; selected development checks."""
import argparse,json
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,PIN,ROM
from stack_budget import stack_usage
from desktop_mouse import schedule


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
        for name,field in [('AESUpdates','updates'),('AESMouseHolds','mouseHolds'),
                           ('AESLockCount','lockCount'),('AESPolicyGate','policyGate')]:
            bindings+=f'  BEGIN\n    LET cell=LONGCARD POINTER(${sy[name]:x})\n    cell^=LONGCARD(ADDRESS(@service.{field}))\n  END\n'
        source=out/'migration.act'
        source.write_text(f'''MODULE AESMIGRATION
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE AESGATE
USE DESKPAINT
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
  LET call=ADDRESS POINTER(@entry)
  call^=${sy['AESRun']:x}
  Require(entry()=0)
  BEGIN
    BYTE pending

    LET desktop=DESKSTATE.Get()
    LET bit=EXEC.AllocSignal(-1)
    Require(bit>=0)
    DO
      AESGATE.EnterTask(EXEC.FindTask(NULL),LONGCARD(1) LSH bit)
      pending=DESKPAINT.Runnable() OR CONSOLEBITMAP.Pending()<>0
          OR service.policyEffects<>0 OR AESCORE.Runnable(service)<>0
          OR desktop.scene.busy<>0
      AESGATE.Release(0)
      IF pending=0 THEN
        EXIT
      FI
      EXEC.Yield()
    OD
    EXEC.FreeSignal(bit)
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
                b.bp_clear_all()
            try:
                report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=6000)
            finally:
                for name in ('AESChecks','AESFailures','AESFirstFailure','progress','phase','callbackReady'):
                    report[name]=b.eval_expr(f'dw(${foreign["symbols"][name]:x})')
                report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(report['AESFailures']==0 and report['AESChecks']>=35,'UPDATE migration fixture failed')
            require(report['progress']>0 and report['phase']==3 and report['callbackReady']==2,'Missing callback/peer/counter progress')
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
