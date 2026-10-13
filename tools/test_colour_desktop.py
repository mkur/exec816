#!/usr/bin/env python3
"""Focused physical colour desktop cases on the packaged OF816 disk."""
import argparse,json,zipfile
from pathlib import Path
from browser_model import FIELDS as F,listing,select,wait_listing
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols
from native_program import require
from stack_budget import stack_usage
from test_demo import run
from test_shell_core import KEYS

class ColourFiles:
    def exercise(self,s):
        b=s.b
        sy=json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
        children=sy['GEMDesktopChildren']
        base=symbols(b,s.p,s.p['output']/'bitmap-console','files',s.number(children+8,4))['GEMBrowser']
        counter=symbols(b,s.p,s.p['output']/'bitmap-console','counter',s.number(children+4,4))['GEMCounter']
        def n(name):return s.number(base+F[name],2)
        def text(name):return b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
        def work():return [s.number(base+F['work']+i*2,2) for i in range(4)]
        def at(name):return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            position=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            position=schedule(b,s.p,position,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        def key(name,shift=False):
            if shift:b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up')
            if shift:b._cmd_ok('KEY SHIFT up')
            s.frames(35)
        def view(item):click(224,8);click(228,24+(item-15)*16)
        def fill(value):
            for _ in text('editText'):key('BACKSPACE')
            for c in value:
                k,shift=KEYS[c];key(k,shift)
        def path(value):
            key('P');s.rendezvous('dw($%x)=1'%(base+F['dialog']));fill(value);key('RETURN')
            s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(s,base)
            require(text('path')==value,'Path entry did not navigate')
        def shot(name):move(632,232);s.frames(100);s.cells(name);s.save_screen(s.p['output']/(name+'.png'))
        s.rendezvous('dw($%x)=1'%(base+F['ready']));wait_listing(s,base)
        s.menus=Menus(s,click,move);s.saved['desktop_menu']={}
        s.menus.select('SYS:')
        initial_counter=s.number(counter+14,4)
        require(n('iconView')==1 and n('columns')==3 and n('visible')==6,'Initial icon grid')
        require(s.number(base+F['bar']+15*24+10,2)&4,'Icons menu not checked')
        shot('colour-files-icons')
        # Ordinary clicks select immediately. Paired captured edges open a folder.
        names=listing(s,base);index=names.index('C');x,y,w,h=work()
        move(x+48+(index%3)*104,y+32+(index//3)*40)
        for button,frames in ((1,4),(0,4),(1,4),(0,160)):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(button));s.frames(frames)
        wait_listing(s,base);require(text('path')=='SYS:C','Physical double-click did not open folder')
        require(n('sortNames')==1 and listing(s,base)==sorted(listing(s,base)),'Name sort')
        before=n('first');x,y,w,h=work();click(x+w+8,y+h-8)
        require(n('first')==before+n('columns'),'Grid scroll is not row aligned')
        view(16);require(n('iconView')==0 and n('columns')==1,'List view')
        require(s.number(base+F['bar']+16*24+10,2)&4,'List menu not checked')
        shot('colour-files-list')
        select(s,base,'HELLO',click);key('RETURN')
        s.rendezvous('dw($%x)=0'%(base+F['child']));s.frames(80)
        require(s.number(base+F['launches'],4)==1,'Native launch from list')
        view(17);require(n('sortNames')==0,'Disk order menu')
        view(17);require(n('sortNames')==1,'Name order menu')
        view(15);require(n('iconView')==1,'Icon view restore')
        old=work();click(408,32);s.frames(120)
        require(n('full')==1 and work()==[8,44,616,180],'Full window geometry')
        require(n('columns')==5 and n('visible')==15,'Full icon reflow')
        shot('colour-files-full')
        click(632,24);s.frames(120);require(n('full')==0 and work()==old,'Restore window geometry')
        # Resize both dimensions, retain selection and reflow the same object pool.
        selected=listing(s,base)[n('selected')]
        move(408,224);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(304,184);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(160)
        require(n('columns')==2 and n('visible')==2,'Shrink icon reflow')
        require(listing(s,base)[n('selected')]==selected,'Resize lost selection')
        shot('colour-files-shrunk')
        # Existing editing and filesystem operations still work with compact insets.
        path('WORK:');key('N');s.rendezvous('dw($%x)=2'%(base+F['dialog']))
        fill('COLOUR');key('RETURN');s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(s,base)
        select(s,base,'COLOUR',click);key('R');fill('RENAMED');key('RETURN')
        s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(s,base)
        require('RENAMED' in listing(s,base) and 'COLOUR' not in listing(s,base),'Rename')
        key('P');fill('WORK:MISSING');key('RETURN');s.frames(140)
        require(n('dialog')==1 and text('path')=='WORK:','Bad path replaced live directory')
        key('ESC');s.rendezvous('dw($%x)=0'%(base+F['dialog']))
        require(s.number(counter+14,4)>initial_counter,'Files stopped the counter')
        shot('colour-files-dialog-retired')
        self.report=s.saved['colour_files']=dict(icons=True,list=True,sort=True,double_click=True,scroll=True,
            full_restore=True,resize=True,native_launch=True,dialogs=True,counter=True,
            bank_zero_reserved_delta=0,stacks=stack_usage(b,s.p['build']['memory']))
        click(24,32);s.rendezvous('dw($%x)=0'%(children+8));s.frames(100)
        s.menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.command('DELETE WORK:RENAMED')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for c in 'EXIT':s.press(c)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);args=p.parse_args()
    out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    probe=ColourFiles()
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(tier='development',qualification=False,colour_files=probe.report)
    (out/'colour-desktop-results.json').write_text(json.dumps(result,indent=2)+'\n')
