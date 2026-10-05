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

def scene(stage,font,aligned=False):
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    terminal=Terminal(64,20);terminal.feed(b'ABC')
    r=Raster(font);rectangle(r,(0,0,640,240),8)
    frame(r,(32,24,560,208),b'Exec816 Shell',stage!=9)
    terminal.paint(r,5,5,stage!=9)
    if stage==10:return overlay(r,(320,120))
    x,y=(113,85) if stage<6 else (273,53)
    if aligned:x-=1
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

def run(out,mode,replay=False,aligned=False,cache_miss=False,cache_observe=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    source=ROOT/'tests/programs/widgets_presentation.act'
    if aligned:
        from library_paths import read_source
        value=read_source(source).replace('113,85,449,229','112,85,448,229')
        value=value.replace('273,53,609,197','272,53,608,197').replace('request.bounds.left=273','request.bounds.left=272')
        # First warm exposure preserves the model; the existing second exposure
        # follows an occluded update and must reject the old snapshot.
        start=value.index('  DESKTOP.Prepare(@request,DESKTYPES.OPEN)',value.index('  Pause(6)'))
        end=value.index('  patch.count=1',start)
        cover=value[start:end]
        value=value[:start]+cover+'  Send(DESKTYPES.CLOSE,cover)\n  Settled()\n'+value[start:]
        source=out/'fixture.act';source.write_text(value)
    if cache_observe or cache_miss:
        from library_paths import read_source
        value=read_source(ROOT/'lib/desktop/deskcache.act')
        value=value.replace('BYTE active,activeSlot','BYTE active,activeSlot\nLONGCARD captures,restores')
        value=value.replace('  active=ACTIVE_CAPTURE','  captures==+1\n  active=ACTIVE_CAPTURE',1)
        value=value.replace('  active=ACTIVE_RESTORE','  restores==+1\n  active=ACTIVE_RESTORE',1)
        if cache_miss:
            start=value.index('  BYTE index',value.index('PUBLIC BYTE FUNC Lookup'))
            end=value.index('; With exactly two slots',start)
            value=value[:start]+'\nRETURN(NO_SLOT)\n\n'+value[end:]
        (out/'deskcache.act').write_text(value)
    p=read_build(out/'program') if replay else build_bitmap(source,
        out,mode=='opt',desktop=True,memory_profile=memory)
    report=dict(slice='AW3',tier='development',qualification=False,status='running',mode=mode,aligned=aligned,cache_miss=cache_miss,cache_observe=cache_observe,scenes=[])
    at=lambda n:next(d['address'] for d in p['image']['data'] if '_WIDGETSCENE_'+n.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');report['machine']=verify_machine(b,ROM,PIN)
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            def before(b):
                previous=b.eval_expr('@clk') & 0xffffffff
                for stage in range(1,11):
                    marker=p['labels']['native_nmi'];condition='dw($%x)=%d'%(at('checkpoint'),stage)
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    try:run_to(b,marker,condition=condition,frame_limit=12000,timeout=180)
                    except Exception:
                        print('Widget stage/checks/state',stage,b.peek16(at('checks')),b.peek16(adapter.STATE),b.regs(),flush=True)
                        raise
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    clock=b.eval_expr('@clk') & 0xffffffff
                    row=dict(stage=stage,stimulus_to_settled_cycles=(clock-previous)&0xffffffff,pixels=pixels(b,folder,scene(stage,font_bytes(out/'selected/src/vdi/font8x8.c'),aligned)))
                    if cache_observe or cache_miss:
                        for name in ('captures','restores'):
                            address=next(d['address'] for d in p['image']['data'] if '_DESKCACHE_'+name.upper()+'_' in d['name'])
                            row[name]=int.from_bytes(b.memdump(address,4),'little')
                    if cache_observe:
                        from generate_desktop import layout
                        layout=layout()
                        address=next(d['address'] for d in p['image']['data'] if '_DESKSTATE_SERVICE_' in d['name'])
                        service=int.from_bytes(b.memdump(address,3),'little')
                        raw=b.memdump(service,layout['Service']['size'])
                        row['slots']=[];row['windows']=[]
                        for kind,field,count in [('Snapshot','snapshots',2),('Window','windows',4)]:
                            for index in range(count):
                                base=layout['Service']['fields'][field]+index*layout[kind]['size']
                                fields=layout[kind]['fields']
                                names=['window','revision','width','height','valid','pinned'] if kind=='Snapshot' else ['id','layer','visualRevision','captureAttempt']
                                item={n:int.from_bytes(raw[base+fields[n]:base+fields[n]+(1 if n in ('valid','pinned') else 2 if n in ('width','height') else 4)],'little') for n in names}
                                row['slots' if kind=='Snapshot' else 'windows'].append(item)
                    previous=clock
                    report['scenes'].append(row)
                    b.memload(at('gate'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,frame_limit=20000,timeout=240)
            ownership(b,p,p['output']);report['checks']=data(b,p['image'],'checks',True)[0]
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(v['remaining_above_floor']>0 for v in report['stack_usage'].values()),'Widget presenter stack floor')
        if cache_observe or cache_miss:
            require(report['scenes'][-1]['captures']>0,'No automatic capture')
            if cache_miss:
                require(report['scenes'][-1]['restores']==0,'Forced miss restored pixels')
            elif aligned:
                rows=report['scenes']
                require(rows[6]['restores']>rows[5]['restores'],'Warm exposure replayed widgets')
                require(rows[7]['restores']==rows[6]['restores'],'Occluded update used stale pixels')
                require(rows[8]['restores']==rows[7]['restores'],'Widget focus reused stale pixels')
        report.update(status='pass',bank_zero_delta=delta(p['build']['memory']),
            build_sha256=sha256(out/'program/build.json'),xex_sha256=sha256(p['xex']))
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'presentation-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Widget presentation passed',mode,report['checks'],flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',required=True,type=Path)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');a.add_argument('--replay',action='store_true')
    a.add_argument('--aligned',action='store_true');a.add_argument('--cache-miss',action='store_true');a.add_argument('--cache-observe',action='store_true')
    args=a.parse_args();run(args.output,args.mode,args.replay,args.aligned,args.cache_miss,args.cache_observe)
