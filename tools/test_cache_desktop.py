#!/usr/bin/env python3
"""Exact ZIP walkthrough for cached AES clients, menus and shared dialogs."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_aes_server import expected_layout,ABI
from native_program import require,sha256
from text_model import FIELDS as T,LOAD_PHASE
from file_selector_model import FIELDS as F,FORM_SELECTOR
from test_demo import run


class Desktop:
    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        def at(name):return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,old,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),pos[0],at('cursorY'),pos[1]));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(65)
        def drag_client(work):
            x,y=[s.number(work+i*2,2) for i in range(2)]
            move(x+40,y-8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(12)
            move(x+24,y-8);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
            actual=[s.number(work+i*2,2) for i in range(2)]
            require(actual==[x-16,y],
                    'Copied move work geometry: '+str(actual)+' != '+str([x-16,y]))
        def key(name):
            b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up');s.frames(80)
        def app(name):
            for _ in range(80):
                found=[a for a in instances(b,s.p,directory) if a['name']==name]
                if found:return found[0]
                s.frames(20)
            raise RuntimeError('Missing loaded '+name)
        def shot(name):
            move(632,232);s.frames(100);s.cells(name);s.save_screen(s.p['output']/(name+'.png'))
        s.saved['desktop_menu']={}
        menus=Menus(s,click,move)
        menus.select('SYS:');shot('cache-files')
        click(296,8);click(304,61);counter=app('counter')['symbols']['GEMCounter']
        s.rendezvous('dw($%x)=1'%(counter+12));ticks=s.number(counter+14,4)
        menus.select('SYS:');click(296,8);click(304,28);panel=app('panel')['symbols']['GEMPanel']
        s.rendezvous('dw($%x)=1'%(panel+8));s.frames(100)
        require([s.number(panel+38+i*2,2) for i in range(2)]==[192,136],
                'Panel frame no longer fits its fixed object tree')
        drag_client(panel+34)
        x,y=[s.number(panel+34+i*2,2) for i in range(2)]
        before=s.number(panel+10,4);click(x+32,y+40)
        require(s.number(panel+10,4)==before+1,'Panel activation lost')
        key('TAB');key('SPACE')
        require(s.number(panel+10,4)==before+2,'Panel keyboard activation lost')
        shot('cache-panel')
        menus.close();s.frames(100)
        menus.select('SYS:');click(296,8);click(304,39)
        calculator=app('calc')['symbols'];model=calculator['Calculator']
        s.rendezvous('dw($%x)=1'%(model+4));s.frames(100)
        drag_client(model+22)
        tree=s.number(calculator['tree'],4)
        for index in (3,10,9,19):
            x,y=[s.number(tree+16+i*2,2) for i in range(2)]
            ox,oy,w,h=[s.number(tree+index*24+16+i*2,2) for i in range(4)]
            click(x+ox+w//2,y+oy+h//2)
        require(s.number(calculator['shown'],4)==42,'Calculator input after move')
        shot('cache-calculator');menus.close();s.frames(100)
        menus.select('Shell');old=s.begin('RUN C:TEXT.APP SYS:STORY.TXT');s.ready(old);s.result()
        text=app('text');model=text['symbols']['GEMText']
        s.rendezvous('dw($%x)=1'%(model+T['ready']))
        def settled():
            s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(model+T['load']+LOAD_PHASE,model+T['dirty']));s.frames(100)
        settled();doc=model+T['document'];data=s.number(doc,4);size=s.number(doc+8,4)
        digest=hashlib.sha256(b.memdump(data,size)).hexdigest()
        require(digest==s.manifest['files']['STORY.TXT']['sha256'],'Text differs from packaged document')
        shot('cache-text');drag_client(model+T['work']);shot('cache-text-moved');first=s.number(model+T['first'],2)
        key('SPACE');settled()
        require(s.number(model+T['first'],2)>first,'Text did not scroll')
        shot('cache-text-scrolled')
        form_offset=dict(expected_layout())['C context form']
        context=next(c for i in range(ABI['constants']['CONTEXTS'])
            if (c:=s.number(shared['contexts']+i*4,4)) and s.number(c+32,3)==text['task'])
        key('O');session=s.number(context+form_offset,4);require(session,'Text Open did not start a dialog')
        selector=s.number(session+FORM_SELECTOR,4);require(selector,'Missing file selector')
        s.rendezvous('dw($%x)=0'%(selector+F['loading']));shot('cache-open-dialog')
        key('ESC');require(not s.number(context+form_offset,4),'Cancel retained file selector')
        settled();require(s.number(doc,4)==data and s.number(doc+8,4)==size,'Cancel changed document')
        shot('cache-dialog-restored');menus.close();s.frames(150)
        require(not any(a['name']=='text' for a in instances(b,s.p,directory)),'Text did not retire')
        menus.select('Counter');require(s.number(counter+14,4)>ticks,'Counter stopped during walkthrough')
        menus.close();s.frames(100);menus.select('SYS:');shot('cache-clients-closed')
        self.results=dict(files=True,panel_pointer=True,panel_keyboard=True,panel_moved_hit_test=True,calculator_moved_input=42,text_moved=True,text_sha256=digest,
            text_scroll=True,selector_cancel=True,counter_progress=True,close_restore=True)
        menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    a=p.parse_args();out=a.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    probe=Desktop();result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),cache_desktop=probe.results)
    (out/'cache-desktop-results.json').write_text(json.dumps(result,indent=2)+'\n')
