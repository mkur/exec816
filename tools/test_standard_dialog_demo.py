#!/usr/bin/env python3
"""Cold boot the exact ZIP and exercise a loaded synchronous-form application."""
import argparse,json,re,zipfile
from pathlib import Path
from native_program import require,sha256
from test_demo import run
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols

class DialogDemo:
    def exercise(self,s):
        directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        counter=symbols(s.b,s.p,directory,'counter',s.number(shared['GEMDesktopChildren']+4,4))['GEMCounter']
        files=symbols(s.b,s.p,directory,'files',s.number(shared['GEMDesktopChildren']+8,4))['GEMBrowser']
        def move(x,y):
            at=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            current=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            target=schedule(s.b,s.p,current,(x,y));s.saved['pointer']=target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),target[0],at('cursorY'),target[1]))
        def edge(down):s.b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(25)
        def click(x,y):move(x,y);edge(1);edge(0);s.frames(60)
        def key(name):s.b._cmd_ok('KEY '+name+' down');s.frames(3);s.b._cmd_ok('KEY '+name+' up');s.frames(45)
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        job=s.at('job')
        def memory():
            screen=s.command('MEM').decode('ascii')
            return [int(v) for v in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',screen)][-4:]
        def begin(name,args=''):
            menus.select('Shell');old=s.begin('RUN C:'+name+'.APP'+(' '+args if args else ''));s.ready(old);s.result()
            return s.number(job,4)
        def collected():s.rendezvous('db($%x)=3'%(job+12));s.frames(80)
        # Existing resource-backed Files editing remains independent.
        menus.select('Files');key('P')
        from browser_model import FIELDS
        require(s.number(files+FIELDS['dialog'],2)!=0,'Files path editor did not open')
        key('ESC');require(s.number(files+FIELDS['dialog'],2)==0,'Files editor did not dismiss')
        menus.select('Shell');baseline=memory();owners=s.ledger()
        begin('DIALOG');collected()
        require(len(menus.windows())==4 and s.ledger()==owners,'Full desktop launch retained resources')
        require(memory()==baseline,'Full desktop launch leaked memory')
        menus.select('Files');menus.close();menus.select('Shell');baseline=memory();owners=s.ledger()
        def launch(args=''):
            identity=begin('DIALOG',args);sy=symbols(s.b,s.p,directory,'dialog',identity);app=sy['GEMDialog']
            s.rendezvous('dw($%x)=3'%(app+10));s.frames(100)
            return identity,app
        def accept(app):
            menus.select('Alert');key('RETURN');s.rendezvous('dw($%x)=1'%(app+8));s.frames(80)
        def phase(app,value):s.rendezvous('dw($%x)=%d'%(app+10,value));s.frames(50)
        identity,app=launch();move(630,230);s.cells('pre-window-alert');accept(app)
        s.cells('dialog-home');key('E');phase(app,2)
        for letter in 'ABC':key(letter)
        from dialog_model import FIELDS as D
        text=s.b.memdump(app+D['text'],32).split(b'\0')[0]
        require(text==b'Exec816abc','Loaded form insertion: '+repr(text))
        old=s.number(app+12,4);key('RETURN');phase(app,2)
        require(s.number(app+12,4)==old+1,'Apply did not repeat the explicit form')
        key('TAB');key('TAB');key('SPACE');phase(app,1)
        move(630,230);s.cells('borrowed-content-repair')
        key('E');phase(app,2);count=s.number(counter+14,4)
        menus.select('Shell');s.command('CAT STORY.TXT');s.command('HELLO',b'Hello from disk!')
        require(s.number(counter+14,4)>count,'Form blocked the peer counter')
        menus.select('Dialog example');move(630,230);s.cells('form-exposed')
        interrupted=s.number(app+20,4)
        click(24,8);click(32,40);phase(app,3)
        require(s.number(app+20,4)==interrupted+1,'Menu policy did not interrupt the form')
        key('RETURN');phase(app,1);s.cells('menu-alert-repair')
        key('E');phase(app,2)
        move(112,56);edge(1);move(124,64);edge(0);phase(app,1)
        require(s.number(app+20,4)==interrupted+2,'Move policy did not interrupt the form')
        move(630,230);s.cells('move-form-handoff')
        key('E');phase(app,2);menus.close();collected();menus.select('Shell')
        require(s.ledger()==owners and memory()==baseline,'Close during form leaked ownership')
        identity,app=launch();accept(app);key('E');phase(app,2)
        menus.select('Shell');s.command('BREAK '+str(identity));collected()
        require(s.ledger()==owners and memory()==baseline,'Stopped form leaked ownership')
        # Rebuilt resource-loaded calculator still uses its event-driven helpers.
        identity=begin('CALC');sy=symbols(s.b,s.p,directory,'calc',identity)
        s.rendezvous('dw($%x)=1'%(sy['Calculator']+4));s.frames(80);menus.select('Calculator')
        key('1');key('2')
        tree=s.number(sy['tree'],4);obj=tree+18*24
        click(s.number(tree+16,2)+s.number(obj+16,2)+s.number(obj+20,2)//2,
              s.number(tree+18,2)+s.number(obj+18,2)+s.number(obj+22,2)//2)
        key('7');key('RETURN');require(s.number(sy['shown'],4)==19,'Calculator shared-binding smoke')
        move(630,230);s.cells('calculator-smoke');menus.close();collected();menus.select('Shell')
        require(s.ledger()==owners and memory()==baseline,'Calculator teardown leaked ownership')
        if hasattr(self,'selectors'):
            self.selectors(s,shared,menus,counter,launch,accept,phase,move,edge,click,key,collected,owners,memory,baseline)
        identity,app=launch();accept(app);key('E');phase(app,2)
        menus.select('Shell');s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='standard-dialogs',full_capacity=True,pre_window_alert=True,
            repeat_apply=True,text=text.decode(),borrowed_repair=True,menu_handoff=True,move_handoff=True,
            covered_form=True,counter_progress=True,shell_disk=True,close_while_waiting=True,
            stop_while_waiting=True,relaunches=3,heap_return=True,files_smoke=True,calculator=19,
            exit_while_waiting=True,heap_baseline=baseline)
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
               integration=DialogDemo(),profile_commands=False)
    result['qualification']=False
    result['scope']='Exact ZIP: standard dialogs beside shell/counter/panel, Files editor and calculator smoke, physical input, pixels, resource return and EXIT'
    result['zip_sha256']=sha256(out/'exec816-demo.zip')
    # Keep failure measurements as well: the 128-byte plan gate is for ordinary
    # Tasks. Root, dedicated service pools and idle retain their guard checks.
    result['ordinary_stack_headroom_pass']=all(
        result['gem_stacks'][str(slot)]['remaining_above_floor']>=128 for slot in range(1,6))
    if not result['ordinary_stack_headroom_pass']:result['status']='fail'
    (out/'standard-dialog-results.json').write_text(json.dumps(result,indent=2)+'\n')
    require(result['ordinary_stack_headroom_pass'],'Packaged ordinary-Task margin below 128-byte target: '+str(result['gem_stacks']))
