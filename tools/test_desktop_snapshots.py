#!/usr/bin/env python3
"""Exercise the private snapshot facility through a fixture-only owner hook."""
import argparse,json
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from library_paths import read_source
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_desktop_presentation import desktop, frame,rectangle,text
from test_gem_cursor import overlay
from test_gem_interactive import pixels
from gem_render_oracle import Raster,font_bytes
from bitmap_console_oracle import Terminal
from stack_budget import stack_usage
from desktop_budget import delta


def run(out,replay=False):
    out.mkdir(parents=True,exist_ok=True)
    host=read_source(ROOT/'lib/desktop/deskhost.act').replace('USE DESKMOVE','USE SNAPSHOTPROBE\nUSE DESKMOVE',1)
    host=host.replace('    DESKPAINT.Sync()','    DESKPAINT.Sync()\n    SNAPSHOTPROBE.Pump(service)',1)
    # This facility test drives retirement explicitly, including fault injection.
    # Keep automatic policy out of this fixture, not out of production.
    host=host.replace('    DESKCACHE.Pump(service)\n','')
    if 'PUBLIC PROC Cache()' in host:
        start=host.index('PUBLIC PROC Cache()');end=host.index('PUBLIC PROC Stop()',start)
        host=host[:start]+'PUBLIC PROC Cache()\n\nRETURN\n\n'+host[end:]
    (out/'deskhost.act').write_text(host)
    (out/'snapshotprobe.act').write_text(read_source(ROOT/'tests/programs/snapshotprobe.act'))
    source=read_source(ROOT/'tests/programs/desktop_presentation.act').split('PROC Main()')[0]
    source=source.replace('USE DESKPAINT','USE DESKPAINT\nUSE SNAPSHOTPROBE',1)
    source+='''PROC Main()
  BYTE operation

  DESKTOP.Prepare(@request,DESKTYPES.OPEN)
  request.value=DESKTYPES.CONTENT_COMMANDS
  request.payload=BYTE POINTER(c"Snapshot")
  request.bytes=8
  REGIONS.Assign(@request.bounds,0,0,544,208)
  Send(DESKTYPES.OPEN,0)
  panel=request.window
  content.background=3
  content.count=1
  content.textBytes=3
  content.text(0)='X
  content.text(1)='Y
  content.text(2)='Z
  content.commands(0).kind=DESKTYPES.DRAW_TEXT
  content.commands(0).pen=1
  content.commands(0).count=3
  REGIONS.Assign(@content.commands(0).bounds,3,3,27,11)
  DESKTOP.Prepare(@request,DESKTYPES.REPLACE)
  request.payload=BYTE POINTER(@content)
  request.bytes=DESKTYPES.CONTENT_SIZE
  Send(DESKTYPES.REPLACE,panel)
  Send(DESKTYPES.SHOW,panel)
  Pause(1)
  FOR operation=1 TO 4 DO
    SNAPSHOTPROBE.Request(operation,panel)
    WHILE SNAPSHOTPROBE.Done()=0 DO
      EXEC.Yield()
    OD
    Pause(CARD(operation)+1)
  OD
  SNAPSHOTPROBE.Request(5,panel)
  WHILE SNAPSHOTPROBE.Held()=0 DO
    EXEC.Yield()
  OD
  Send(DESKTYPES.CLOSE,panel)
  Require(SNAPSHOTPROBE.Done()<>0)

RETURN

ENDMODULE
'''
    # Poll the test hook while idle; the production worker sleeps instead.
    host=(out/'deskhost.act').read_text().replace('RETURN(DESKPAINT.Runnable() OR DESKINPUT.Runnable())',
        'RETURN(DESKPAINT.Runnable() OR DESKINPUT.Runnable() OR SNAPSHOTPROBE.Done()=0)')
    (out/'deskhost.act').write_text(host)
    (out/'fixture.act').write_text(source)
    p=read_build(out/'program') if replay else build_bitmap(out/'fixture.act',out,True,desktop=True)
    report=dict(status='running',tier='development',qualification=False,scope='Private owner-hook capture, full restore, revision mismatch and quiescent capture failure; production driver and bitmap bridge',scenes=[])
    at=lambda module,n:next(d['address'] for d in p['image']['data'] if '_'+module+'_'+n+'_' in d['name'])
    r=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'));desktop(r)
    frame(r,(32,24,560,208),b'Exec816 Shell',True)
    Terminal(64,20).paint(r,5,5,True)
    frame(r,(0,0,544,208),b'Snapshot',False,3,close=True);text(r,11,19,b'XYZ',bg=3)
    expected=overlay(r,(320,120))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            report['machine']=verify_machine(b,ROM,PIN)
            def before(b):
                for stage in range(1,6):
                    condition=f'dw(${at("DESKTEST","CHECKPOINT"):x})={stage}'
                    marker=p['labels']['native_nmi'];b.bp_clear_all();b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    run_to(b,marker,condition=condition,frame_limit=12000,timeout=180)
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    report['scenes'].append(dict(stage=stage,pixels=pixels(b,folder,expected)))
                    b.memload(at('DESKTEST','GATE'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output'])
            report['checks']=b.peek16(at('SNAPSHOTPROBE','CHECKS'))
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            report['bank_zero_delta']=delta(p['build']['memory'])
        report['status']='pass'
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Snapshot facility passed',report['checks'],flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',required=True,type=Path);a.add_argument('--replay',action='store_true')
    args=a.parse_args();run(args.output.resolve(),args.replay)
