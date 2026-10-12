#!/usr/bin/env python3
"""Physical CG3/CG4 desktop walkthrough on the extracted OF816 distribution."""
import argparse,json,zipfile
from pathlib import Path
from browser_model import FIELDS as F,listing,select,wait_listing
from colour_desktop_model import FIELDS as D
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols
from native_program import require
from stack_budget import stack_usage
from test_shell_core import KEYS

class ColourDesktop:
    def __init__(self,files=False,restore=None,only=False):
        self.files,self.restore,self.only=files,restore,only

    def prepare_work(self,target,item):
        if not self.files and self.restore is None:return
        import tempfile
        from sdfs_reference import extract,make
        with tempfile.TemporaryDirectory(prefix='exec816-colour-') as tmp:
            root=Path(tmp);extract(target,root)
            (root/'SOURCE.TXT').write_bytes(b'Copied by the GEM desktop.\n'*37)
            (root/'DELETE.TXT').write_bytes(b'Delete fixture\n')
            (root/'BIG.BIN').write_bytes(bytes(range(256))*512)
            # Leave 21 free sectors in this geometry. A small copy still fits;
            # BIG.BIN reaches a real partial-write failure after several chunks.
            (root/'FILL.BIN').write_bytes(bytes([0x5a])*590000)
            (root/'DESKTOP.CFG').write_bytes(self.restore or b'Invalid old preferences\n')
            make(target,root,item['sectors'],item['sector_bytes'])

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        owner=resident['GEMDesktopChildren']
        sy=symbols(b,s.p,directory,'desktop',s.number(owner,4));desk=sy['GEMDesk']
        def dn(name,size=2):return s.number(desk+D[name],size)
        def folders():return [s.number(desk+D['folders']+i*4,4) for i in range(3)]
        def text(base,name):return b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
        def work(base):return [s.number(base+F['work']+i*2,2) for i in range(4)]
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
        def fill(base,value):
            for _ in text(base,'editText'):key('BACKSPACE')
            for c in value:k,shift=KEYS[c];key(k,shift)
        def path(base,value):
            key('P');s.rendezvous('dw($%x)=1'%(base+F['dialog']));fill(base,value);key('RETURN')
            s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(s,base)
            require(text(base,'path')==value,'Folder path did not change')
        def desk_menu(row):click(168,8);click(176,24+row*16)
        def shot(name):
            move(632,232);s.frames(140);s.cells(name);s.save_screen(s.p['output']/(name+'.png'))
            print(name,flush=True)
        s.rendezvous('dw($%x)=1'%(desk+D['ready']))
        first=folders()[0];require(first and not folders()[1],'Default desktop folder')
        wait_listing(s,first)
        menus=Menus(s,click,move);s.saved['desktop_menu']={}
        if self.restore is not None:
            require(dn('settingsLoaded')==1 and text(first,'path')=='WORK:','Saved folder was not restored')
            require(s.number(first+F['iconView'],2)==0,'Saved List view was not restored')
            shot('desktop-settings-restored')
            self.report=dict(settings_restart=True)
            menus.select('Shell');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        if self.only:
            from colour_file_check import exercise
            exercise(s,desk,first,click,key,fill,path,desk_menu,shot)
            self.report=dict(files=s.saved['colour_files'],stacks=stack_usage(b,s.p['build']['memory']))
            menus.select('Shell');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        require(len(menus.windows())==2,'Background leaked into Windows menu')
        shot('desktop-initial')
        click(600,236)  # Like other windows, the background consumes its focus click.
        require(not dn('active',4),'Background focus before icon selection')
        click(56,26);require(dn('selected')==1,'Background volume selection')
        click(56,58);require(dn('selected')==2,'Background selection change')
        require(s.number(desk+D['tree']+24+10,2)==0 and
                s.number(desk+D['tree']+48+10,2)==1,'Background icon states')
        shot('desktop-selection')
        desk_menu(0);s.frames(200)
        second=folders()[1];require(second and second!=first,'Second independent folder not opened')
        wait_listing(s,second)
        require(s.number(first,2)==s.number(second,2),'Folders do not share an AES application')
        require(s.number(first+F['tree'],4)!=s.number(second+F['tree'],4),'Folders share mutable trees')
        original=work(second);peer=work(first)
        x,y,w,h=original
        move(x+w+8,y+h+8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(x+w-56,y+h-24);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
        require(work(second)[2:] == [w-64,h-32] and work(first)==peer,'Independent folder resize')
        x,y,w,h=work(second)
        click(x+w+8,y-20);s.frames(120)
        require(s.number(second+F['full'],2)==1,'Full gadget')
        x,y,w,h=work(second);click(x+w+8,y-20);s.frames(120)
        require(s.number(second+F['full'],2)==0,'Full restore')
        path(second,'SYS:C')
        require(text(first,'path')=='SYS:','Second folder changed first folder')
        x,y,w,h=work(second);click(x+w+8,y+h-8)
        require(s.number(second+F['first'],2)>0,'Second folder did not scroll')
        shot('desktop-two-folders')
        desk_menu(4);s.frames(200)
        child=s.number(desk+D['children'],4);require(child,'Counter launch failed')
        counter=symbols(b,s.p,directory,'counter',child)['GEMCounter']
        s.rendezvous('dw($%x)=1'%(counter+12));before=s.number(counter+14,4)
        menus.select('SYS:C');x,y,w,h=work(second);click(x,y-20)
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['folders']+4,desk+D['folders']+6))
        require(s.number(desk+D['children'],4)==child,'Closing folder retired its child')
        menus.select('SYS:');x,y,w,h=work(first);click(x,y-20)
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['folders'],desk+D['folders']+2))
        require(dn('ready')==1 and not any(folders()),'Last folder closed the desktop')
        require(s.number(counter+14,4)>before,'Counter stopped with folder closure')
        click(600,236);s.frames(100)
        require(not dn('active',4),'Background did not become active')
        shot('desktop-no-folders')
        desk_menu(0);s.frames(200)
        first=folders()[0];require(first,'New Window failed after last folder closed')
        wait_listing(s,first)
        shot('desktop-folder-reopened')
        if self.files:
            from colour_file_check import exercise
            exercise(s,desk,first,click,key,fill,path,desk_menu,shot)
        self.report=s.saved['colour_desktop']=dict(multiple_windows=True,shared_application=True,
            independent_trees=True,independent_paths=True,resize=True,full_restore=True,scroll=True,persistent_background=True,background_selection=True,
            independent_launch_lifetime=True,windows_menu=True,files=s.saved.get('colour_files'),
            stacks=stack_usage(b,s.p['build']['memory']))
        menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for c in 'EXIT':s.press(c)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()

if __name__=='__main__':
    from test_demo import run
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--files',action='store_true');p.add_argument('--files-only',action='store_true');args=p.parse_args()
    args.files=args.files or args.files_only
    out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    probe=ColourDesktop(files=args.files,only=args.files_only)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(tier='development',qualification=False,colour_desktop=probe.report)
    if args.files:
        from sdfs_reference import extract
        import tempfile
        with tempfile.TemporaryDirectory(prefix='exec816-readback-') as tmp:
            root=Path(tmp);extract(out/'work-walkthrough.atr',root)
            require((root/'COPY.TXT').read_bytes()==(root/'SOURCE.TXT').read_bytes(),'Independent copy byte comparison')
            require((root/'SOURCE.TXT').read_bytes()==b'Copied by the GEM desktop.\n'*37,'Failed overwrite changed its existing target')
            require(not (root/'EXECCOPY.TMP').exists() and not (root/'CANCEL.BIN').exists(),'Cancelled copy left files')
            require(not (root/'BBB').exists() and not (root/'DELETE.TXT').exists(),'Delete did not persist')
            preferences=(root/'DESKTOP.CFG').read_bytes()
            require(preferences.startswith(b'EXEC816_DESKTOP 1\n'),'Settings format')
            (out/'saved-desktop.cfg').write_bytes(preferences)
        restart=ColourDesktop(restore=preferences)
        restored=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=restart,profile_commands=False)
        result['settings_restart']=dict(status='pass',checks=restart.report,exit=restored.get('status'))
    (out/'colour-session-results.json').write_text(json.dumps(result,indent=2)+'\n')
