#!/usr/bin/env python3
"""Cold frame/VDI admission while the real frontend sleeps on caller UPDATE."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
import build_bitmap_console as builder
from gem_render_oracle import DESKTOP_PALETTE
from generate_aes_server import layout as aes_layout
from library_paths import read_source
from native_program import ROOT, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def build(out,reuse_c=False):
    source=out/'admission.act'
    source.write_text('''MODULE ADMISSIONTEST
USE EXEC
USE AESBOOT
USE AESSTATE
USE AESCORE
USE AESLOCKS
USE CONSOLEBITMAP
USE DESKSTATE
USE HEAPCORE
CARD FUNC POINTER run()
PROC Main()

  LET endpoint=LONGCARD POINTER($AESService)
  endpoint^=LONGCARD(ADDRESS(AESBOOT.Port()))
  LET service=AESSTATE.Get()
  LET entry=ADDRESS POINTER(@run)
  entry^=$AESRun
  IF run()<>0 OR service.count<>0 THEN
    HEAPCORE.Abort($fc70)
  FI
  BEGIN
    BYTE pending

    LET desktop=DESKSTATE.Get()
    DO
      AESLOCKS.ObtainUI()
      pending=desktop.scene.visibleDamage<>0 OR desktop.scene.busy<>0
          OR CONSOLEBITMAP.Pending()<>0 OR AESCORE.Runnable(service)<>0
      AESLOCKS.ReleaseUI()
      IF pending=0 THEN
        EXIT
      FI
      EXEC.Yield()
    OD
  END

RETURN
ENDMODULE
''')
    probe='''MODULE ADMISSIONPROBE
USE EXEC
USE AESLOCKS
USE DESKINPUT
USE INPUT
USE A816MEMORY
USE CONSOLETILING
USE CONSOLECONTROL
USE CONSOLEWINDOWS
USE CONSOLETYPES
USE HEAPCORE
PUBLIC BYTE controlChecks
PUBLIC PROC Controls(BYTE unused)

  LET entered=CARD POINTER($AdmissionEntered)
  LET resumed=CARD POINTER($AdmissionResumed)
  IF entered^<>0 AND resumed^=0 AND controlChecks=0 THEN
    BEGIN
      LET windows=CONSOLEWINDOWS.Registry()
      LET view=CONSOLETYPES.Presentation POINTER(windows.items(0).view)
      IF CONSOLETILING.Lock()=0 THEN
        HEAPCORE.Abort($fc71)
      FI
      IF CONSOLECONTROL.Submit(CONSOLETYPES.CTL_CURSOR,view)=0
          OR CONSOLECONTROL.Submit(CONSOLETYPES.CTL_ERASE,view)=0
          OR windows.control.state<>CONSOLETYPES.CTL_IDLE THEN
        HEAPCORE.Abort($fc72)
      FI
      controlChecks=2
      CONSOLETILING.Unlock()
    END
  FI

RETURN

PUBLIC PROC Pending(BYTE unused)
  INPUT.Event key

  LET request=CARD POINTER($AdmissionRequest)
  IF request^<>0 THEN
    BEGIN
      LET entered=CARD POINTER($AdmissionEntered)
      request^=0
      entered^=1
      A816MEMORY.Clear(BYTE POINTER(@key),INPUT.EVENT_BYTES)
      key.kind=INPUT.EVENT_KEY
      key.code=44
      key.qualifiers=INPUT.CONTROL
      ; Feed the production copied-key route. The real interaction entry,
      ; rather than this fixture hook, must block on native UPDATE.
      BEGIN
        LET handled=DESKINPUT.CaptureKey(@key)
      END
    END
  FI

RETURN

PUBLIC PROC Completed(BYTE unused)

  LET entered=CARD POINTER($AdmissionEntered)
  IF entered^<>0 THEN
    BEGIN
      LET resumed=CARD POINTER($AdmissionResumed)
      resumed^=1
    END
  FI

RETURN

ENDMODULE
'''
    worker=read_source(ROOT/'lib/aes/screnmgr.act').replace(
        'USE AESLOCKS\n','USE AESLOCKS\nUSE ADMISSIONPROBE\n',1)
    point='    AESHOST.Service()'
    require(worker.count(point)==1,'Manager event boundary changed')
    worker=worker.replace(point,'    ADMISSIONPROBE.Pending(0)\n'+point,1)
    point='        AESLOCKS.SystemEnd()'
    require(worker.count(point)==1,'Manager interaction completion changed')
    (out/'screnmgr.act').write_text(worker.replace(point,
        point+'\n        ADMISSIONPROBE.Completed(0)',1))
    caller=read_source(ROOT/'lib/aes/aeslocal.act').replace(
        'USE EXEC\n','USE EXEC\nUSE ADMISSIONPROBE\n',1)
    point='CARD FUNC Exposure(AESTYPES.Request POINTER request)\n  CONSOLEBITMAP.Packet packet\n'
    require(caller.count(point)==1,'Caller exposure boundary changed')
    (out/'aeslocal.act').write_text(caller.replace(point,
        point+'\n  ADMISSIONPROBE.Controls(0)\n',1))
    original=builder.prepare

    def prepare(path,directory,foreign,*args):
        sy=foreign['symbols']
        text=path.read_text()
        for name in ('AESService','AESRun'):
            text=text.replace('$'+name,f'${sy[name]:x}')
        path.write_text(text)
        text=probe
        for name in ('AdmissionRequest','AdmissionEntered','AdmissionResumed'):
            text=text.replace('$'+name,f'${sy[name]:x}')
        (out/'admissionprobe.act').write_text(text)
        launcher=original(path,directory,foreign,*args)
        text=launcher.read_text()
        point='  IF CONSOLEDRIVER.Stop()=0 THEN\n    HEAPCORE.Abort($f732)\n  FI'
        require(text.count(point)==1,'Console stop boundary changed')
        text=text.replace(point,'''  BEGIN
    CARD attempts

    attempts=0
    WHILE CONSOLEDRIVER.Stop()=0 DO
      attempts==+1
      IF attempts=64 THEN
        HEAPCORE.Abort($f732)
      FI
      EXEC.Yield()
    OD
  END''',1)
        launcher.write_text(text)
        return launcher

    builder.prepare=prepare
    original_drawing=builder.drawing
    if reuse_c:
        cached=json.loads((out/'c-image.json').read_text())
        require(cached['provenance']['header_inputs'],'Missing cached C headers')
        for name,digest in {**cached['provenance']['source_inputs'],
                            **cached['provenance']['header_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Changed C input: '+name)
        require(cached['provenance']['compiler_flags'][-1]=='-O2','Wrong cached C mode')
        builder.drawing=lambda *args,**kwargs:cached
    try:
        return builder.build_bitmap(source,out,desktop=True,aes=True,
            release_compiler=True,client_sources=[ROOT/'c/calypsi/aes.c',
                ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
                ROOT/'tests/programs/display_admission.c'],
            client_entries=['AdmissionPeer','AdmissionApp'],
            client_roots=['AESRun','AESService','AESChecks','AESFailures','AESFirstFailure'])
    finally:
        builder.prepare=original
        builder.drawing=original_drawing


def run(out,reuse=False,reuse_c=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if reuse else build(out,reuse_c)
    sy=json.loads((out/'c-image.json').read_text())['symbols']
    report=dict(status='running',tier='development',qualification=False,build=p['build'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def before(_):
                condition=f'dw(${sy["AdmissionPainted"]:x})=1'
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
                # Let the completed VRAM writes pass through a full scanout.
                # The caller stays paused with UPDATE and the manager blocked.
                condition=f'@frame>={b.eval_expr("@frame")+2}'
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                run_to(b,p['labels']['native_irq'],condition=condition,timeout=30,frame_limit=60)
                require(b.peek16(sy['AESFailures'])==0,'Admission checks failed before paint')
                require(b.peek16(sy['AdmissionEntered'])==1 and b.peek16(sy['AdmissionResumed'])==0,
                        'Manager did not remain blocked on caller UPDATE')
                controls=next(d['address'] for d in p['image']['data']
                    if d['name'].startswith('M_ADMISSIONPROBE_CONTROLCHECKS_'))
                report['caller_console_control_checks']=b.memdump(controls,1)[0]
                require(report['caller_console_control_checks']==2,
                        'Caller text controls did not complete while manager blocked')
                x,y=b.peek16(sy['AdmissionX']),b.peek16(sy['AdmissionY'])
                path=out/'admission.bgra';frame=b.rawscreen(str(path));pixels=path.read_bytes()
                get=lambda at,n=4:int.from_bytes(b.memdump(at,n),'little')
                context=next(get(sy['contexts']+4*i) for i in range(8) if get(sy['contexts']+4*i))
                records=aes_layout();rf=records['Request']['fields'];vf=records['WindowView']['fields']
                view=get(context+rf['view'])
                report['view']=dict(address=view,updates=get(view+vf['updates'],2),visible_count=get(view+vf['visibleCount'],2),
                    visible=b.memdump(view+vf['visible'],32).hex(),work=b.memdump(view+vf['work'],8).hex())
                report['raster']=dict(stride=frame.stride,description=str(frame))
                report['sample_pixels']=[list(pixels[y*frame.stride+(xx+16)*4:y*frame.stride+(xx+16)*4+4]) for xx in range(x,x+8)]
                color=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[12:15])[::-1]
                for yy in range(y,y+8):
                    for xx in [*range(x,x+8),*range(x+24,x+32)]:
                        at=yy*frame.stride+(xx+16)*4
                        require(pixels[at:at+3]==color,f'Caller pixels at {xx},{yy}')
                report['caller_pixels']='exact 8x8 fill and offscreen round-trip while manager blocked'
                from generate_tasks import constants as task_constants
                tc=task_constants()
                directory=get(context+rf['directory'])
                manager=get(directory+records['Directory']['fields']['owner'],3)
                control=get(manager+tc['TASK_TC_EXECPRIVATE'],3)
                reason=get(control+tc['TCB_WAITREASON'],1)
                require(reason==tc['WAIT_SEMAPHORE'],
                        'SCRENMGR is not waiting in native UPDATE Obtain')
                report['manager_wait']='native semaphore for copied Ctrl-Tab interaction'
                endpoints=directory+records['Directory']['fields']['endpoints']
                endpoint=next(endpoints+i*records['Endpoint']['size'] for i in range(
                    (records['Directory']['fields']['mouse']-records['Directory']['fields']['endpoints'])//records['Endpoint']['size'])
                    if get(endpoints+i*records['Endpoint']['size'])==get(context+rf['client']))
                inbox=get(endpoint+records['Endpoint']['fields']['input'])
                keytail=inbox+records['InputInbox']['fields']['keyTail']
                previous=get(keytail,1)
                def frames(n):
                    condition=f'@frame>={b.eval_expr("@frame")+n}'
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    run_to(b,p['labels']['native_irq'],condition=condition,timeout=30,frame_limit=60)
                b._cmd_ok('KEY A down');frames(4)
                b._cmd_ok('KEY A up');frames(2)
                require(get(keytail,1)!=previous,'Input delivery waited for SCRENMGR UPDATE')
                require(get(control+tc['TCB_WAITREASON'],1)==tc['WAIT_SEMAPHORE'],
                        'SCRENMGR resumed before caller released UPDATE')
                report['independent_input']='physical A key published to caller inbox while SCRENMGR waits'
                b.poke16(sy['AdmissionGo'],1)
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            ownership(b,p,p['output'])
            report.update(checks=b.peek16(sy['AESChecks']),failures=b.peek16(sy['AESFailures']),
                first_failure=b.peek16(sy['AESFirstFailure']),stack_usage=stack_usage(b,p['build']['memory']))
            require(report['checks']==32 and report['failures']==0,'Incomplete direct admission checks')
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Direct display admission passed:',report['checks'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--reuse-c',action='store_true')
    args=parser.parse_args()
    run(args.output,args.reuse,args.reuse_c)
