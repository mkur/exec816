#!/usr/bin/env python3
"""Exact OF816 ZIP: standard dialogs plus loadable file-selector consumers."""
import argparse,json,zipfile
from pathlib import Path
from native_program import require,sha256
from test_demo import run
from test_standard_dialog_demo import DialogDemo
from generate_aes_server import expected_layout,layout
from file_selector_model import FIELDS as F,FORM_SELECTOR
from dialog_model import FIELDS as D
from test_shell_core import KEYS

class FileSelectorDemo(DialogDemo):
    def selectors(self,s,shared,menus,counter,launch,accept,phase,move,edge,click,key,collected,owners,memory,baseline):
        def text(at,limit=128):return s.b.memdump(at,limit).split(b'\0')[0].decode('ascii')
        def context(app):
            for i in range(4):
                c=s.number(shared['contexts']+i*4,4)
                if c and s.number(c+layout()['Request']['fields']['global']+4,2)==s.number(app,2):return c
            raise RuntimeError('No selector context')
        def selector(app):
            session=s.number(context(app)+dict(expected_layout())['C context form'],4)
            require(session!=0,'Selector session absent')
            return s.number(session+FORM_SELECTOR,4)
        def ready(app):
            s.frames(100);a=selector(app)
            s.rendezvous('(dw($%x)=1)&(dw($%x)=0)'%(a+F['valid'],a+F['loading']));s.frames(40)
            return a
        def xy(app,i):
            a=selector(app);o=a+24*i
            return s.number(a+16,2)+s.number(o+16,2)+s.number(o+20,2)//2, s.number(a+18,2)+s.number(o+18,2)+s.number(o+22,2)//2
        def fill(app,field,value):
            click(*xy(app,3 if field=='path' else 5))
            for _ in text(selector(app)+F[field]):key('BACKSPACE')
            for ch in value:
                name,shift=KEYS[ch]
                if shift:s.b._cmd_ok('KEY SHIFT down')
                key(name)
                if shift:s.b._cmd_ok('KEY SHIFT up')
            require(text(selector(app)+F[field])==value,'Loaded selector editor '+field)
        identity,app=launch('SELECT')
        menus.select('Alert');key('RETURN');phase(app,4);ready(app)
        menus.select('File selector');move(630,230);s.cells('selector-before-window')
        a=selector(app);x,y=s.number(a+16,2),s.number(a+18,2)
        move(x+64,y-8);edge(1);move(x+80,y);edge(0);s.frames(60)
        move(630,230);s.cells('selector-temporary-moved')
        # The app immediately opens its real window, so do not wait for the
        # generic menu-close helper's transient focus-restoration checkpoint.
        a=selector(app);click(s.number(a+16,2),s.number(a+18,2)-8)
        s.rendezvous('dw($%x)=1'%(app+D['ready']));s.frames(80)
        require(s.number(app+D['fileResult'],2)==1 and s.number(app+D['fileButton'],2)==0,'Temporary closer result')
        key('O');phase(app,4);ready(app)
        fill(app,'path','SYS:SELECT/*.TXT');key('RETURN');a=ready(app)
        require(s.number(a+F['count'],2)==13,'Filtered demo directory')
        click(*xy(app,11));a=selector(app);first=s.number(a+F['first'],2)
        require(first>0,'Loaded selector did not page')
        click(*xy(app,15));candidate=text(selector(app)+F['file'],13)
        move(630,230);s.cells('selector-scrolled')
        click(*xy(app,13));phase(app,1)
        require(s.number(app+D['fileButton'],2)==1 and text(app+D['file'],13)==candidate,'Open selection output')
        move(630,230);s.cells('selector-open-repair')
        key('S');phase(app,5);ready(app);fill(app,'file','NEW.TXT');key('RETURN');phase(app,1)
        require(text(app+D['selection'],40)=='Save: NEW.TXT','Save selection output')
        key('O');phase(app,4);ready(app)
        fill(app,'path','SYS:MISSING/*.*');key('RETURN');s.frames(100)
        require(text(selector(app)+F['status'])=='Cannot open dir','Missing path error')
        fill(app,'path','SYS:SELECT/SUB/*.TXT');key('RETURN');ready(app)
        click(*xy(app,6));ready(app)
        require(text(selector(app)+F['path'])=='SYS:SELECT/*.TXT','Loaded parent navigation')
        fill(app,'file','CANCEL.TXT');key('ESC');phase(app,1)
        require(s.number(app+D['fileButton'],2)==0 and text(app+D['file'],13)=='CANCEL.TXT','Edited Cancel output')
        key('O');phase(app,4);ready(app);count=s.number(counter+14,4)
        menus.select('Shell');s.command('CAT STORY.TXT');s.command('HELLO',b'Hello from disk!')
        require(s.number(counter+14,4)>count,'Selector blocked counter progress')
        menus.select('Dialog example');move(630,230);s.cells('selector-exposed')
        interrupted=s.number(app+D['interruptions'],4)
        click(24,8);click(32,40);phase(app,3)
        require(s.number(app+D['interruptions'],4)==interrupted+1,'Selector swallowed menu policy')
        key('RETURN');phase(app,1);move(630,230);s.cells('selector-menu-repair')
        key('O');phase(app,4);ready(app)
        menus.select('Shell');old=s.begin('BREAK '+str(identity));s.ready(old);s.result();collected()
        s.cells('collected-stop')
        require(s.ledger()==owners and memory()==baseline,'Stopped selector retained process resources')
        identity,app=launch();accept(app);key('O');phase(app,4);ready(app)
        key('ESC');phase(app,1);menus.close();collected();menus.select('Shell')
        require(s.ledger()==owners and memory()==baseline,'Relaunched selector leaked ownership')
        s.saved['file_selector']=dict(pre_window=True,temporary_move_close=True,open=True,save_name=True,
            edited_cancel=True,filter=True,scroll=True,path_correction=True,parent=True,
            counter_progress=True,shell_disk=True,exposure_pixels=True,menu_policy=True,
            cooperative_stop=True,relaunch=True,heap_return=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    out=p.parse_args().bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=FileSelectorDemo(),profile_commands=False)
    result.update(qualification=False,scope='Exact ZIP: file selectors, existing dialogs, Files/calculator smoke, shell/counter/panel, physical input, pixels, resource return and EXIT',zip_sha256=sha256(out/'exec816-demo.zip'))
    result['ordinary_stack_headroom_pass']=all(result['gem_stacks'][str(slot)]['remaining_above_floor']>=128 for slot in range(1,6))
    if not result['ordinary_stack_headroom_pass']:result['status']='fail'
    (out/'file-selector-results.json').write_text(json.dumps(result,indent=2)+'\n')
    require(result['ordinary_stack_headroom_pass'],'Selector ordinary-stack margin below 128 bytes: '+str(result['gem_stacks']))
