#!/usr/bin/env python3
"""Retained widget damage, occlusion and exposure against complete scene pixels."""
import adapter_state as adapter
import argparse
import json
import sys
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_gem_interactive import pixels
from test_gem_cursor import overlay
from test_desktop_presentation import rectangle,frame
from gem_render_oracle import Raster,font_bytes
from bitmap_console_oracle import Terminal
from stack_budget import stack_usage
from desktop_budget import delta

def scene(stage,font):
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    terminal=Terminal(64,20);terminal.feed(b'ABC')
    r=Raster(font);rectangle(r,(0,0,640,240),8)
    frame(r,(32,24,560,208),b'Exec816 Shell',stage!=9)
    terminal.paint(r,5,5,stage!=9)
    if stage==10:return overlay(r,(320,120))
    x,y=(113,85) if stage<6 else (273,53)
    frame(r,(x,y,x+336,y+144),b'Cover' if stage==7 else b'Widgets',stage==9,
        15 if stage==7 else 8,close=True)
    if stage==7:return overlay(r,(320,120))
    tree=[
        a.Obj(-1,1,8,a.G_BOX,0,0,0x78,x+8,y+16,320,120),
        a.Obj(2,-1,-1,a.G_BUTTON,a.SELECTABLE,1 if 2<=stage<7 else 0,1,16,24,56,16),
        a.Obj(3,-1,-1,a.G_BUTTON,a.SELECTABLE|a.RBUTTON,8 if stage>=5 else 1,2,88,24,56,16),
        a.Obj(4,-1,-1,a.G_BUTTON,a.SELECTABLE|a.RBUTTON,1 if stage>=5 else 0,3,160,24,56,16),
        a.Obj(5,-1,-1,a.G_STRING,0,0,4,16,8,160,8),
        a.Obj(8,6,7,a.G_IBOX,a.HIDETREE if 4<=stage<9 else 0,0,0x11170,16,64,200,40),
        a.Obj(7,-1,-1,a.G_STRING,0,0,6,8,8,160,8),
        a.Obj(5,-1,-1,a.G_BUTTON,a.SELECTABLE|a.DEFAULT|a.EXIT,0,7,8,20,56,16),
        a.Obj(0,-1,-1,a.G_STRING,a.LASTOB,0,8,24,24,8,8)]
    mem={1:'Toggle',2:'Small',3:'Large',4:'OK' if stage>=3 else 'Ready for input',6:'Subtree',7:'Apply',8:'x'}
    d=v.VDI();d.call(v.V_OPNWK,(),v.WORK_IN);d.dev.s.mem[:76800]=r.packed()
    aes=a.AES(d,tree,{k:a.Text(s) for k,s in mem.items()});aes.gsx_start()
    aes.gsx_sclip(a.Rect(x+8,y+16,320,120));aes.ob_draw(0,7)
    if stage==9:
        for xx in range(x+27,x+77):d.dev.plot_xor(xx,y+53)
    packed=bytes(d.dev.s.mem[:76800])
    r.pixels[:]=bytes(n for byte in packed for n in (byte>>4,byte&15))
    return overlay(r,(320,120))

def run(out,mode,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/widgets_presentation.act',
        out,mode=='opt',desktop=True,memory_profile=memory)
    report=dict(slice='AW3',tier='development',qualification=False,status='running',mode=mode,scenes=[])
    at=lambda n:next(d['address'] for d in p['image']['data'] if '_WIDGETSCENE_'+n.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');report['machine']=verify_machine(b,ROM,PIN)
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            def before(b):
                for stage in range(1,11):
                    marker=p['labels']['native_nmi'];condition='dw($%x)=%d'%(at('checkpoint'),stage)
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    try:run_to(b,marker,condition=condition,frame_limit=12000,timeout=180)
                    except Exception:
                        print('Widget stage/checks/state',stage,b.peek16(at('checks')),b.peek16(adapter.STATE),b.regs(),flush=True)
                        raise
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    report['scenes'].append(dict(stage=stage,pixels=pixels(b,folder,scene(stage,font_bytes(out/'selected/src/vdi/font8x8.c')))))
                    b.memload(at('gate'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,frame_limit=20000,timeout=240)
            ownership(b,p,p['output']);report['checks']=data(b,p['image'],'checks',True)[0]
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(v['remaining_above_floor']>0 for v in report['stack_usage'].values()),'Widget presenter stack floor')
        report.update(status='pass',bank_zero_delta=delta(p['build']['memory']),
            build_sha256=sha256(out/'program/build.json'),xex_sha256=sha256(p['xex']))
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'presentation-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Widget presentation passed',mode,report['checks'],flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',required=True,type=Path)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');a.add_argument('--replay',action='store_true')
    args=a.parse_args();run(args.output,args.mode,args.replay)
