#!/usr/bin/env python3
"""Exact OF816 ZIP: viewer pixels, file selection, scrolling and lifetime."""
import argparse,json,zipfile
from pathlib import Path
from native_program import require,sha256
from test_demo import run
from test_file_selector_demo import FileSelectorDemo
from gem_applications import symbols
from text_model import FIELDS as F,LOAD_PHASE
from generate_aes_server import expected_layout
from file_selector_model import FIELDS as S,FORM_SELECTOR
from test_shell_core import KEYS
from sio_transaction_trace import BASE_HZ

class TextViewerDemo(FileSelectorDemo):
    capacity_app='TEXT'
    def __init__(self,focused=False):self.extensions_only=focused
    def selectors(self,s,shared,menus,counter,launch,accept,phase,move,edge,click,key,collected,owners,memory,baseline):
        if not self.extensions_only:
            super().selectors(s,shared,menus,counter,launch,accept,phase,move,edge,click,key,collected,owners,memory,baseline)
        directory=s.p['output']/'bitmap-console';job=s.at('job');scenes=[];timing=[]
        def num(a,name,size=2):return s.number(a+F[name],size)
        def value(at,limit=128):return s.b.memdump(at,limit).split(b'\0')[0].decode('ascii')
        def settled(a):
            s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(a+F['load']+LOAD_PHASE,a+F['dirty']));s.frames(50)
        def begin(args='',wait=True):
            menus.select('Shell');old=s.begin('RUN C:TEXT.APP'+(' '+args if args else ''));s.ready(old);s.result()
            identity=s.number(job,4);sy=symbols(s.b,s.p,directory,'text',identity);a=sy['GEMText']
            s.rendezvous('dw($%x)=1'%(a+F['ready']))
            if wait:settled(a)
            return identity,a
        def pixels(a,label):
            settled(a);move(630,230);s.cells('text-'+label);scenes.append(label)
        def context(a):
            for i in range(4):
                c=s.number(shared['contexts']+4*i,4)
                if c:
                    # GEM id is the third global word in the request.
                    from generate_aes_server import layout
                    if s.number(c+layout()['Request']['fields']['global']+4,2)==s.number(a,2):return c
            raise RuntimeError('No viewer context')
        def selector(a):
            session=s.number(context(a)+dict(expected_layout())['C context form'],4)
            return s.number(session+FORM_SELECTOR,4) if session else 0
        def select_file(a,filename,accept_selection=True):
            key('O');v=selector(a);require(v!=0,'Viewer selector absent')
            s.rendezvous('dw($%x)=1'%(v+S['valid']));s.frames(60)
            obj=v+5*24
            click(s.number(v+16,2)+s.number(obj+16,2)+12,s.number(v+18,2)+s.number(obj+18,2)+8)
            for _ in value(v+S['file'],13):key('BACKSPACE')
            for ch in filename:
                name,shift=KEYS[ch]
                if shift:s.b._cmd_ok('KEY SHIFT down')
                key(name)
                if shift:s.b._cmd_ok('KEY SHIFT up')
            require(value(v+S['file'],13)==filename,'Viewer selection filename')
            if accept_selection:key('RETURN')
        def close(a,title):
            menus.select(title);menus.close();collected();menus.select('Shell')
            require(s.ledger()==owners and memory()==baseline,'Viewer retained heap or Process ownership')
        identity,a=begin();menus.select('Text viewer');pixels(a,'empty')
        require(num(a,'loads',4)==0,'Empty viewer loaded a file')
        select_file(a,'STORY.TXT');settled(a);require(num(a,'loads',4)==1,'Open did not commit document')
        pixels(a,'open');paint_count=num(a,'paints',4);s.frames(100)
        require(num(a,'paints',4)==paint_count,'Idle viewer keeps repainting')
        require(s.number(a+F['document']+12,2)>num(a,'rows'),'Fixture needs scrolling')
        for title in ('STORY.TXT','STORY.TXT'):
            menus.select(title);old=num(a,'first');paint_count=num(a,'paints',4)
            start=s.b.eval_expr('@clk');s.b._cmd_ok('KEY SPACE down')
            s.rendezvous('dw($%x)!=%d'%(a+F['first'],old));accepted=s.b.eval_expr('@clk')
            s.b._cmd_ok('KEY SPACE up')
            s.rendezvous('(dw($%x)!=%d)&(dw($%x)=0)'%(a+F['paints'],paint_count&65535,a+F['dirty']))
            complete=s.b.eval_expr('@clk');s.frames(50)
            require(num(a,'first')==old+num(a,'rows'),'Page key did not move one viewport')
            timing.append(dict(operation='page',input_to_model_ms=((accepted-start)&0xffffffff)*1000/BASE_HZ,
                model_to_paint_ms=((complete-accepted)&0xffffffff)*1000/BASE_HZ,
                scope='Physical key submission through completed paint bands; scanout excluded'))
        pixels(a,'page')
        x,y,w,h=[s.number(a+F['work']+i*2,2) for i in range(4)]
        old=num(a,'first');click(x+w+8,y+8);settled(a)
        require(num(a,'first')==old-1,'Viewer arrow');pixels(a,'arrow')
        # Minimum work area must continue to host the file selector.
        move(x+w+8,y+h+8);edge(1);move(x+208+8,y+128+8);edge(0);settled(a)
        require(num(a,'rows')==13 and s.number(a+F['work']+4,2)==208,'Viewer minimum resize')
        pixels(a,'minimum')
        # Drag the current thumb to the bottom, then test a no-op down arrow.
        x,y,w,h=[s.number(a+F['work']+i*2,2) for i in range(4)]
        count=s.number(a+F['document']+12,2);extent=count-num(a,'rows')
        height=h-32;thumb=max(8,height*(num(a,'rows')*1000//count)//1000)
        top=y+16+(height-thumb)*(num(a,'first')*1000//extent)//1000
        move(x+w+8,top+thumb//2);edge(1);move(x+w+8,y+h-16);edge(0);settled(a)
        require(num(a,'first')==extent,'Viewer thumb did not reach final page')
        pixels(a,'thumb-bottom');old=num(a,'paints',4)
        click(x+w+8,y+h-8);settled(a)
        require(num(a,'first')==extent and num(a,'paints',4)==old,'No-op scroll repainted')
        menus.key('SPACE',shift=True);settled(a)
        require(num(a,'first')==extent-num(a,'rows'),'Shift-Space did not page up')
        pixels(a,'page-up')
        before=num(a,'loads',4);first=num(a,'first');select_file(a,'MISSING.TXT',False);key('ESC');settled(a)
        require(num(a,'loads',4)==before and num(a,'first')==first,'Cancel replaced document')
        select_file(a,'MISSING.TXT');settled(a)
        require(num(a,'loads',4)==before and num(a,'first')==first,'Failed Open replaced document')
        require(value(a+F['status'],81).startswith('Cannot load:'),'No Open error')
        pixels(a,'failed-open')
        key('O');require(selector(a)!=0,'Selector missing before interruption')
        interrupted=num(a,'interruptions',4)
        x,y=[s.number(a+F['work']+i*2,2) for i in range(2)]
        move(x+48,y-8);edge(1);move(x+64,y);edge(0);settled(a)
        require(num(a,'interruptions',4)==interrupted+1,'Selector swallowed window move')
        pixels(a,'selector-interrupted');close(a,'STORY.TXT')
        identity,a=begin('"SYS:LONG.TXT"');menus.select('LONG.TXT');pixels(a,'argument')
        require(num(a,'loads',4)==1 and s.number(a+F['document']+12,2)==768,'Quoted startup path')
        count=s.number(counter+14,4);menus.select('Shell');s.command('CAT STORY.TXT');s.command('HELLO',b'Hello from disk!')
        require(s.number(counter+14,4)>count,'Viewer blocked counter')
        menus.select('LONG.TXT');pixels(a,'exposure')
        first=num(a,'first');select_file(a,'LONG.TXT',False)
        # Trigger acceptance without the helper's long post-key wait, then meet a read boundary.
        s.b._cmd_ok('KEY RETURN down');s.frames(3);s.b._cmd_ok('KEY RETURN up')
        s.rendezvous('dw($%x)=3'%(a+F['load']+LOAD_PHASE));key('ESC');settled(a)
        require(num(a,'loads',4)==1 and num(a,'first')==first,'Escape committed a candidate')
        require(value(a+F['status'],81)=='Load cancelled','Read-time Escape was lost')
        pixels(a,'cancel-load');close(a,'LONG.TXT')
        identity,a=begin('SYS:LONG.TXT',False)
        menus.select('Shell');old=s.begin('BREAK '+str(identity));s.ready(old);s.result();collected()
        s.cells('collected-stop')
        require(s.ledger()==owners and memory()==baseline,'Stopped loading viewer leaked')
        identity,a=begin('one two');menus.select('Text viewer');pixels(a,'bad-arguments')
        require(num(a,'loads',4)==0 and value(a+F['status'],81).startswith('Expected one path'),'Bad argument admission')
        close(a,'Text viewer')
        s.saved['text_viewer']=dict(scenes=scenes,page_observations=timing,selector=True,
            cancel_preserves_document=True,error_preserves_document=True,quoted_path=True,
            cancel_loading=True,stop=True,heap_return=True,counter_progress=True,qualification=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--viewer-only',action='store_true');args=p.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=TextViewerDemo(args.viewer_only),profile_commands=False)
    result.update(qualification=False,scope='Exact ZIP viewer'+(' (focused)' if args.viewer_only else ', standard dialogs/selectors and existing desktop smoke'),zip_sha256=sha256(out/'exec816-demo.zip'))
    result['ordinary_stack_headroom_pass']=all(result['gem_stacks'][str(slot)]['remaining_above_floor']>=128 for slot in range(1,6))
    if not result['ordinary_stack_headroom_pass']:result['status']='fail'
    (out/'text-viewer-results.json').write_text(json.dumps(result,indent=2)+'\n')
    require(result['ordinary_stack_headroom_pass'],'Viewer ordinary-stack margin below 128 bytes: '+str(result['gem_stacks']))
