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

def development_media(out):
    """Rebuild loadable apps against the unchanged resident image, explicitly.

    The experimental disk is separate from the original packaged ZIP. Final
    package checks omit this option and execute the exact distribution.
    """
    import shutil,tempfile
    from build_c_program import build
    from browser_model import LAYOUT as browser_layout
    from colour_desktop_model import LAYOUT as desktop_layout
    from native_program import ROOT
    from sdfs_reference import extract,make
    for name in ('desktop','files'):
        build(out/'bitmap-console/apps'/name,
            [ROOT/'examples/gem-browser'/('desktop-main.c' if name=='desktop' else 'main.c'),
             ROOT/'examples/gem-browser/browser.c',ROOT/'c/calypsi/file-list.c'],
            probes=[(ROOT/'tests/programs/gem_browser_layout.c',browser_layout),
                    (ROOT/'tests/programs/gem_colour_desktop_layout.c',desktop_layout)])
    media=out/'development-system.atr'
    manifest=json.loads((out/'demo-manifest.json').read_text());geometry=manifest['mounts'][0]
    with tempfile.TemporaryDirectory(prefix='exec816-selection-apps-') as tmp:
        root=Path(tmp);extract(out/manifest['media'],root)
        for name in ('desktop','files'):
            shutil.copyfile(out/'bitmap-console/apps'/name/'program.app',root/'C'/(name.upper()+'.APP'))
        make(media,root,geometry['sectors'],geometry['sector_bytes'])
    return media


class ColourDesktop:
    def __init__(self,files=False,restore=None,only=False,selection=False,batch=False,drag=False,compact=False,icons=False):
        self.files,self.restore,self.only,self.selection,self.batch=files,restore,only,selection,batch
        self.drag=drag;self.compact=compact;self.icons=icons

    def prepare_work(self,target,item):
        if not self.files and not self.selection and not self.batch and not self.compact and self.restore is None:return
        import tempfile
        from sdfs_reference import extract,make
        with tempfile.TemporaryDirectory(prefix='exec816-colour-') as tmp:
            root=Path(tmp);extract(target,root)
            if self.batch:
                if self.batch=='delete':from colour_delete_check import fixture
                else:from colour_batch_check import fixture
                fixture(root)
            if self.compact:
                for name in [*(f'A{i:02d}' for i in range(12)),'ZLAST']:(root/'NAV'/name).mkdir(parents=True)
            if self.selection=='standalone':(root/'EMPTY').mkdir()
            if self.selection:
                (root/'ALPHA.TXT').write_bytes(b'alpha')
                (root/'BETA.TXT').write_bytes(b'beta')
                if self.selection not in ('feedback','standalone'):
                    (root/'SELECT').mkdir()
                    for i in range(257):(root/'SELECT'/f'E{i:03d}.TXT').write_bytes(b'')
            (root/'SOURCE.TXT').write_bytes(b'Copied by the GEM desktop.\n'*37)
            (root/'DELETE.TXT').write_bytes(b'Delete fixture\n')
            (root/'BIG.BIN').write_bytes(bytes(range(256))*512)
            # Leave space for one 16 KiB chunk before the disk-full case.
            # Cancel is handled between chunks: a smaller reserve can report
            # disk full before processing Escape and falsely "pass" cleanup.
            if self.files:(root/'FILL.BIN').write_bytes(bytes([0x5a])*(590000-16384))
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
            s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(s,base,limit=200 if self.selection else 50)
            require(text(base,'path')==value,'Folder path did not change')
        def desk_menu(row):click(296,8);click(304,24+row*16)
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
        if self.icons:
            from compact_files_check import colour_icons
            self.report=colour_icons(s,desk,first,click,key,path,shot,move,menus)
            self.report['stacks']=stack_usage(b,s.p['build']['memory'])
            menus.select('Shell');s.command('HELLO',b'Hello from disk!');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        if self.compact:
            from compact_files_check import exercise
            self.report=exercise(s,desk,first,click,key,path,shot,move)
            self.report['stacks']=stack_usage(b,s.p['build']['memory'])
            menus.select('Shell');s.command('HELLO',b'Hello from disk!');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        if self.drag:
            from colour_drag_check import exercise
            self.report=exercise(s,desk,first,click,key,fill,path,desk_menu,shot,move,menus)
            self.report['stacks']=stack_usage(b,s.p['build']['memory'])
            menus.select('Shell');s.command('HELLO',b'Hello from disk!');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        if self.batch:
            if self.batch=='delete':
                from colour_delete_check import exercise
                exercise(s,desk,first,click,key,fill,path,desk_menu,shot,menus)
                self.report=dict(batch_delete=s.saved['batch_delete'],remaining=s.saved['delete_remaining'])
            else:
                from colour_batch_check import exercise
                exercise(s,desk,first,click,key,fill,path,desk_menu,shot)
                self.report=dict(batch_copy=s.saved['batch_copy'])
            self.report['stacks']=stack_usage(b,s.p['build']['memory'])
            menus.select('Shell');s.command('HELLO',b'Hello from disk!');s.save_screen(s.p['output']/'boot-smoke.png')
            for c in 'EXIT':s.press(c)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        if self.selection:
            if self.selection=='standalone':
                from colour_selection_feedback import standalone
                standalone(s,desk,click,key,path,move,menus,shot)
                self.report=dict(standalone_selection=s.saved['standalone_selection'])
            elif self.selection=='feedback':
                from colour_selection_feedback import exercise
                exercise(s,first,click,key,path,move)
                self.report=dict(selection_feedback=s.saved['selection_feedback'])
            else:
                from colour_selection_check import exercise
                exercise(s,desk,first,click,key,path,desk_menu,shot,move,boundary=self.selection=='boundary')
                self.report=dict(selection=s.saved['selection'])
            self.report['stacks']=stack_usage(b,s.p['build']['memory'])
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
        click(x+w+8,y-8);s.frames(120)
        require(s.number(second+F['full'],2)==1,'Full gadget')
        x,y,w,h=work(second);click(x+w+8,y-8);s.frames(120)
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
        menus.select('SYS:C');x,y,w,h=work(second);click(x,y-8)
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['folders']+4,desk+D['folders']+6))
        require(s.number(desk+D['children'],4)==child,'Closing folder retired its child')
        menus.select('SYS:');x,y,w,h=work(first);click(x,y-8)
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
        shot('desktop-shell')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for c in 'EXIT':s.press(c)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()

if __name__=='__main__':
    from test_demo import run
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--development-media',type=Path,help='Reuse an explicitly identified development disk')
    p.add_argument('--rebuild-apps',action='store_true',help='Use an explicit development disk; leave the ZIP unchanged')
    p.add_argument('--drag-drop',action='store_true');p.add_argument('--compact-files',action='store_true');p.add_argument('--file-icons',action='store_true')
    p.add_argument('--batch-copy',action='store_true');p.add_argument('--batch-delete',action='store_true')
    p.add_argument('--standalone-selection',action='store_true');p.add_argument('--selection-boundary',action='store_true');p.add_argument('--selection-feedback',action='store_true')
    p.add_argument('--selection-only',action='store_true');p.add_argument('--files',action='store_true');p.add_argument('--files-only',action='store_true');args=p.parse_args()
    args.files=args.files or args.files_only
    out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    media=development_media(out) if args.rebuild_apps else args.development_media.resolve() if args.development_media else None
    from native_program import sha256
    overrides=dict(media_path=media,measurement_media_sha256=sha256(media),measurement_commands=[]) if media else {}
    probe=ColourDesktop(files=args.files,only=args.files_only,selection='standalone' if args.standalone_selection else 'feedback' if args.selection_feedback else 'boundary' if args.selection_boundary else args.selection_only,batch='delete' if args.batch_delete else args.batch_copy,drag=args.drag_drop,compact=args.compact_files,icons=args.file_icons)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False,**overrides)
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
        restored=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=restart,profile_commands=False,**overrides)
        result['settings_restart']=dict(status='pass',checks=restart.report,exit=restored.get('status'))
    if args.batch_copy:
        from colour_batch_check import readback
        from sdfs_reference import extract
        import tempfile
        with tempfile.TemporaryDirectory(prefix='exec816-batch-readback-') as tmp:
            root=Path(tmp);extract(out/'work-walkthrough.atr',root);readback(root)
        result['independent_batch_readback']=True
    if args.batch_delete:
        from colour_delete_check import readback
        from sdfs_reference import extract
        import tempfile
        with tempfile.TemporaryDirectory(prefix='exec816-delete-readback-') as tmp:
            root=Path(tmp);extract(out/'work-walkthrough.atr',root);readback(root,probe.report['remaining'])
        result['independent_batch_readback']=True
    if args.drag_drop:
        from colour_drag_check import readback
        readback(out)
        result['independent_drag_readback']=True
    result['development_media_sha256']=sha256(media) if media else None
    result['application_sha256']={name:sha256(out/'bitmap-console/apps'/name/'program.app') for name in ('desktop','files')}
    (out/('file-icons-results.json' if args.file_icons else 'compact-files-results.json' if args.compact_files else 'drag-session-results.json' if args.drag_drop else 'colour-session-results.json')).write_text(json.dumps(result,indent=2)+'\n')
