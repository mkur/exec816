#!/usr/bin/env python3
"""Compact geometry and cache checks through physical input in the demo ZIP."""
import argparse,json,struct,zipfile
from pathlib import Path
from browser_model import FIELDS as F,select,listing,wait_listing
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_desktop import layout
from generate_layers import layout as layer_layout
from native_program import require,sha256
from test_demo import run
from test_shell_core import KEYS
from test_window_iconification import Iconification


class Compact(Iconification):
    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console';s.saved['desktop_menu']={}
        def at(mod,name):return next(d['address'] for d in s.p['image']['data'] if '_'+mod+'_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(at('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,old,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]));s.frames(3)
        def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(int(down)));s.frames(20 if down else 100)
        def click(x,y):move(x,y);edge(1);edge(0)
        def drag(start,end):move(*start);edge(1);move(*end);edge(0);s.frames(80)
        menus=Menus(s,click,move)
        def key(name):menus.key(name)
        def text(base,name):return b.memdump(base+F[name],128).split(b'\0')[0].decode()
        def work(base):return struct.unpack('<4h',b.memdump(base+F['work'],8))
        def shot(name):
            move(632,212);s.frames(100);s.cells(name);s.save_screen(s.p['output']/(name+'.png'))
        desk=next(a for a in instances(b,s.p,directory) if a['name']=='desktop')['symbols']['GEMDesk']
        base=s.number(desk+D['folders'],4);wait_listing(s,base)
        menus.select('SYS:');initial=work(base)
        require(initial[2:]==(438,174),'Default Files work size: '+str(initial))
        require(s.number(base+F['columns'],2)==4 and s.number(base+F['visible'],2)==16,'Lost 4 by 4 grid')
        select(s,base,'C',click);key('RETURN');wait_listing(s,base)
        require(text(base,'path')=='SYS:C','Directory navigation failed')
        shot('compact-files-4x4')
        tree=s.number(base+F['tree'],4)
        for index in range(16):
            obj=struct.unpack('<hhhHHHIhhhh',b.memdump(tree+(2+index)*24,24))
            require(not obj[4]&128 and obj[9:11]==(104,32),'Missing complete icon cell')
            icon=struct.unpack('<IIIH10h',b.memdump(obj[6],34))
            require(icon[8:10]==(32,16),'Application icon artwork was resized')
        # Full/restore and resize use actual title/size gadgets.
        x,y,w,h=work(base);click(x+w+8,y-6);s.frames(150)
        require(work(base)==(8,22,616,207),'Maximized Files work size: '+str(work(base)))
        shot('compact-files-full')
        click(632,16);s.frames(150);require(work(base)==initial,'Full restore lost default bounds')
        x,y,w,h=work(base)
        drag((x+w+8,y+h+5),(x+270+8,y+122+5))
        require(work(base)[2:]==(270,122),'Smaller resize work size: '+str(work(base)))
        require(s.number(base+F['columns'],2)==2 and s.number(base+F['visible'],2)==4,'Smaller layout did not reflow')
        x,y,w,h=work(base);drag((x+w+8,y+h+5),(x+438+8,y+174+5))
        require(work(base)==initial,'Resize restore lost default bounds')
        key('ESC');wait_listing(s,base);require(text(base,'path')=='SYS:','Parent shortcut failed')
        # A topmost clean move must not repaint the application.
        s.frames(120);before=s.number(base+F['paints'],4);x,y,w,h=work(base)
        drag((x+120,y-6),(x+112,y-6))
        require(work(base)==(x-8,y,w,h),'Even-X move rejected')
        require(s.number(base+F['paints'],4)==before,'Clean move repainted Files')
        shot('compact-files-copied')
        # Switching unequal popup footprints retains the saved background.
        click(160,5);s.frames(100)
        before=s.number(base+F['paints'],4);captures=s.number(at('DESKMENUCACHE','captures'),4)
        restores=s.number(at('DESKMENUCACHE','restores'),4)
        for x in (224,160,224,160):move(x,5);s.frames(100)
        require(s.number(base+F['paints'],4)==before,'Heading switch repainted Files')
        require(s.number(at('DESKMENUCACHE','captures'),4)==captures,'Heading switch recaptured background')
        require(s.number(at('DESKMENUCACHE','restores'),4)>=restores+4,'Heading switch lost background restores')
        key('ESC');s.frames(120);shot('compact-menus-dismissed')
        # Real folder-to-folder drop into RAM:, without altering the SYS image.
        def path(target,value):
            key('P');s.rendezvous('dw($%x)=1'%(target+F['dialog']))
            for _ in text(target,'editText'):key('BACKSPACE')
            for ch in value:
                name,shift=KEYS[ch];menus.key(name,shift=shift)
            key('RETURN');wait_listing(s,target)
            require(text(target,'path')==value,'Path dialog failed')
        click(296,5);click(304,28);s.frames(150)
        target=s.number(desk+D['folders']+4,4);require(target,'Second folder did not open')
        wait_listing(s,target);path(target,'RAM:')
        def place(model,left):
            x,y,w,h=work(model);drag((x+w+8,y+h+5),(x+274+8,y+154+5))
            x,y,w,h=work(model);drag((x+100,y-6),(left+108,25))
            require(work(model)==(left+8,31,274,154),'Folder placement: '+str(work(model)))
        place(target,328);menus.select('SYS:');place(base,8)
        point=[]
        def pick(x,y):point[:]=[x,y];click(x,y)
        select(s,base,'README.TXT',pick)
        move(*point);edge(1);move(point[0]+8,point[1]);s.frames(10)
        tx,ty,tw,th=work(target);move(tx+180,ty+100);s.frames(20);edge(0)
        for _ in range(300):
            if not s.number(desk+D['job'],4) and text(base,'status').startswith('Copy complete'):break
            s.frames(20)
        else:raise RuntimeError('File drop did not finish: '+text(base,'status'))
        wait_listing(s,target);require('README.TXT' in listing(s,target),'Drop destination was not refreshed')
        shot('compact-folder-drop')
        menus.select('RAM:');menus.close();s.frames(120);menus.select('SYS:')
        # Restore the default size, then test Shell alignment at both clamps.
        x,y,w,h=work(base);drag((x+w+8,y+h+5),(x+438+8,y+174+5))
        menus.select('Shell')
        s.command('CMP SYS:README.TXT RAM:README.TXT')
        types=layout();wf=types['Window']['fields'];sf=types['Service']['fields'];layers=layer_layout()
        def shell_bounds():
            scene=menus.service+sf['scene'];ident=next(w['id'] for w in menus.windows() if w['title']=='Shell')
            for i in range(6):
                win=menus.service+sf['windows']+i*types['Window']['size']
                if s.number(win+wf['id'],4)==ident:layer=s.number(win+wf['layer'],4);break
            for i in range(9):
                item=scene+layers['Scene']['fields']['items']+i*layers['Layer']['size']
                if s.number(item,4)==layer:return struct.unpack('<4h',b.memdump(item+4,8))
            raise AssertionError('Missing Shell layer')
        original=shell_bounds();l,t,r,bot=original
        drag((l+80,t+5),(0,0));require(shell_bounds()==(0,13,528,186),'Shell top clamp: '+str(shell_bounds()))
        shot('compact-shell-top')
        drag((80,18),(639,239));require(shell_bounds()==(112,61,640,234),'Shell bottom clamp: '+str(shell_bounds()))
        shot('compact-shell-bottom')
        drag((192,66),(original[0]+80,original[1]+5));require(shell_bounds()==original,'Shell restore coordinates')
        self.geometry=dict(default_work=[438,174],maximized_work=[616,207],grid=[4,4],icon_pixels=[32,16],
            small_work=[270,122],clean_move_repaints=0,warm_heading_recaptures=0,folder_drop=True,
            shell_top=[0,13,528,186],shell_bottom=[112,61,640,234])
        super().exercise(s)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    out=parser.parse_args().bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    probe=Compact();result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(tier='development',qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),geometry=probe.geometry,iconification=probe.results)
    (out/'compact-geometry-results.json').write_text(json.dumps(result,indent=2)+'\n')
