#!/usr/bin/env python3
"""Exercise console binding with an independent complete desktop raster."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_desktop_presentation import desktop, frame, menu_bar, shell_tabs
from bitmap_console_oracle import Terminal
from gem_render_oracle import Raster, font_bytes, DESKTOP_PALETTE
from test_gem_cursor import overlay
from test_gem_interactive import pixels


def scenes(font):
    first, second = Terminal(64, 20), Terminal(64, 20)
    first.feed(b'\x0cAlpha'); second.feed(b'Beta')
    for stage in range(1, 10):
        if stage == 3:
            for row in range(25):
                first.feed(bytes(33+(row*7+col) % 90 for col in range(64)))
        if stage == 5: second.feed(b' hidden')
        raster=Raster(font); desktop(raster)
        selected=second if stage in (2,3,5,8) else first
        focused=stage not in (4,5,6)
        left,top=(80,45) if stage>=8 else (32,29)
        if stage!=6:
            frame(raster,(left,top,left+528,top+189),b'Shell',focused)
            shell_tabs(raster,(left,top,left+528,top+189))
            selected.paint(raster,(left+8)//8,(top+27)//8,focused)
        if stage in (4,5,6):
            frame(raster,(113,93,273,173),b'Clip',True,3,close=True)
        # Stage 7 raises Shell over the entire panel, retaining its pixels below.
        menu_bar(raster,b'Clip' if stage in (4,5,6) else b'Shell')
        yield overlay(raster,(320,120))


def run(out,reuse=False,iconified=False,stale=False):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if reuse else build_bitmap(
        ROOT/'tests/programs/desktop_console_bind.act',out,
        desktop=True,release_compiler=True)
    record=dict(status='running',tier='development',qualification=False,iconified=iconified,stale_completion=stale,build=p['build'],observations=[])
    address=lambda name: next(d['address'] for d in p['image']['data'] if '_DESKBINDTEST_'+name+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            record['machine']=verify_machine(b,ROM,PIN)
            def before(b):
                from desktop_mouse import schedule
                from generate_desktop import layout
                from desktop_oracle import compose
                symbol=lambda module,name:next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name+'_' in d['name'])
                def frames(count):
                    condition=f'@frame>={b.eval_expr("@frame")+count}'
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    run_to(b,p['labels']['native_irq'],12000,120,condition)
                def point():
                    return [b.peek16(symbol('DESKINPUT',axis)) for axis in ('CURSORX','CURSORY')]
                def move(x,y):
                    target=schedule(b,p,point(),(x,y))
                    condition='&'.join(f'dw(${symbol("DESKINPUT",axis):x})={value}' for axis,value in zip(('CURSORX','CURSORY'),target))
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    run_to(b,p['labels']['native_irq'],12000,120,condition);frames(3)
                def click(x,y):
                    move(x,y)
                    b._cmd_ok('MOUSE AT 2000 0 0 1');frames(5)
                    b._cmd_ok('MOUSE AT 2000 0 0 0');frames(10)
                def cycle():
                    for key in ('CTRL','TAB'):b._cmd_ok(f'KEY {key} down')
                    frames(3)
                    for key in ('TAB','CTRL'):b._cmd_ok(f'KEY {key} up')
                    frames(10)
                b._cmd_ok('MOUSE ST')
                for stage,expected in enumerate(scenes(font_bytes(out/'selected/src/vdi/font8x8.c')),1):
                    condition=f'dw(${address("CHECKPOINT"):x})={stage}'
                    b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    try:
                        run_to(b,p['labels']['native_nmi'],12000,120,condition)
                    except Exception:
                        print('Bind stage/status/checks',stage,b.peek16(adapter.STATE),data(b,p['image'],'checks',True),flush=True)
                        raise
                    require(b.peek16(adapter.STATE)==65535,'Desktop bind stopped early')
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    if stale and stage==2:
                        from generate_console import constants
                        c=constants();registry=p['build']['memory']['console_storage']['WINDOWS']
                        first=registry+c['WINDOWS_ITEMS'];other=first+c['WINDOW_SIZE']
                        pointer=lambda at:int.from_bytes(b.memdump(at,3),'little')
                        first_view=pointer(first+c['WINDOW_VIEW']);other_view=pointer(other+c['WINDOW_VIEW'])
                        first_model=pointer(first+c['WINDOW_INSTANCE']);other_model=pointer(other+c['WINDOW_INSTANCE'])
                        generation=int.from_bytes(b.memdump(first_view+c['PRESENTATION_GENERATION'],4),'little')
                        unchanged=b.memdump(other_view,c['PRESENTATION_SIZE'])
                        # Replay a retired owner's completion identity at the
                        # worker boundary. No destination storage is altered.
                        b.memload(symbol('CONSOLEDISPLAY','BITMAPUNIT'),bytes(4))
                        b.memload(symbol('CONSOLEDISPLAY','BITMAPGENERATION'),(generation-1).to_bytes(4,'little'))
                        b.memload(symbol('CONSOLEDISPLAY','BITMAPMODEL'),b.memdump(first_model+c['INSTANCE_GENERATION'],4))
                        b.poke(first_view+c['PRESENTATION_SCROLLSTATE'],3)
                        b.poke(symbol('CONSOLEDISPLAY','BITMAPREADY'),1)
                        b._cmd_ok('MOUSE AT 2000 0 16 -1');frames(12)
                        require(b.peek(symbol('CONSOLEDISPLAY','BITMAPREADY'))==b'\0','Late completion did not retire')
                        require(b.peek(first_model+c['INSTANCE_DIRTYROWS'])!=b'\0','Old completion was adopted')
                        require(b.peek(other_model+c['INSTANCE_DIRTYROWS'])==b'\0','Old completion dirtied the new owner')
                        require(b.memdump(other_view,c['PRESENTATION_SIZE'])==unchanged,'Old completion altered the new view')
                        move(320,120);frames(3)
                    if iconified and stage==4:
                        service=int.from_bytes(b.memdump(symbol('DESKSTATE','SERVICE'),3),'little')
                        fields=layout()['Service']['fields'];wf=layout()['Window']['fields']
                        window=service+fields['windows']
                        require(b.peek(window+wf['iconified'])==b'\x01','Bind restored an iconified Shell')
                        require(int.from_bytes(b.memdump(service+fields['consoleUnit'],4),'little')==0,'Iconified bind did not commit')
                        icon_folder=out/'iconified-bind';icon_folder.mkdir(exist_ok=True)
                        packed=compose(b,p,font_bytes(out/'selected/src/vdi/font8x8.c'),Terminal(64,20),tuple(point()))
                        record['iconified_pixels']=pixels(b,icon_folder,packed,palette=DESKTOP_PALETTE)
                        click(144,232);cycle();move(320,120);frames(100)
                    record['observations'].append(dict(stage=stage,pixels=pixels(b,folder,expected,palette=DESKTOP_PALETTE)))
                    if iconified and stage==3:
                        click(552,34)
                        service=int.from_bytes(b.memdump(symbol('DESKSTATE','SERVICE'),3),'little')
                        window=service+layout()['Service']['fields']['windows']
                        require(b.peek(window+layout()['Window']['fields']['iconified'])==b'\x01','Physical iconify failed')
                    b.memload(address('GATE'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            record['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output'])
            record['checks']=data(b,p['image'],'checks',True)[0]
            record['status']='pass'
    except Exception as error:
        record.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Desktop console bind passed',record['checks'],'checks',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--iconified',action='store_true')
    parser.add_argument('--stale-completion',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.reuse,args.iconified,args.stale_completion)
