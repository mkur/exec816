"""Physical Files-to-viewer launch, ownership and Stop checks."""
import json
from native_program import require
from gem_applications import symbols
from browser_model import FIELDS as B,select,wait_listing
from text_model import FIELDS as T,LOAD_PHASE

def exercise(s,shared,menus,move,click,key,collected,memory):
    if 'text_viewer' in s.saved:
        (s.p['output']/'text-viewer-stage.json').write_text(json.dumps(s.saved['text_viewer'],indent=2)+'\n')
    directory=s.p['output']/'bitmap-console';job=s.at('job')
    panel=symbols(s.b,s.p,directory,'panel',s.number(shared['GEMDesktopChildren'],4))['GEMPanel']
    menus.select('Control Panel');actions=s.number(panel+10,4)
    key('SPACE');key('RETURN')
    require(s.number(panel+10,4)==actions+2,'Rebuilt panel keyboard activation')
    move(630,230);s.cells('rebuilt-panel');menus.close()
    s.rendezvous('dw($%x)=0'%shared['GEMDesktopChildren'])
    menus.select('Shell');baseline=memory();owners=s.ledger()
    old=s.begin('RUN C:FILES.APP');s.ready(old);s.result();identity=s.number(job,4)
    browser=symbols(s.b,s.p,directory,'files',identity)['GEMBrowser']
    s.rendezvous('dw($%x)=1'%(browser+B['ready']));wait_listing(s,browser)
    def num(name,size=2):return s.number(browser+B[name],size)
    # Files allocates its child-poll timer lazily. Warm a native child first;
    # parent close below must still restore the original pre-Files baseline.
    def free_ranges():
        heap=s.p['build']['memory']['heap_storage'];ranges=[]
        for i in range(s.number(heap['BASE']+12,2)):
            at=s.number(heap['HEADERS']+32*i+14,3)
            while at:
                record=s.b.memdump(at,8);size=int.from_bytes(record[4:8],'little')
                ranges.append((at,at+size));at=int.from_bytes(record[:3],'little')
        return ranges
    def retained(before,after):
        result=[]
        for lo,hi in before:
            pieces=[(lo,hi)]
            for x,y in after:
                pieces=[r for a,b in pieces for r in ((a,min(b,x)),(max(a,y),b)) if r[0]<r[1]]
            result.extend(dict(address=a,bytes=b-a,head=s.b.memdump(a,min(b-a,64)).hex()) for a,b in pieces)
        return result
    menus.select('Shell');cold=memory();cold_free=free_ranges()
    menus.select('Files');select(s,browser,'C',click);key('RETURN');wait_listing(s,browser)
    select(s,browser,'HELLO',click);key('RETURN')
    s.rendezvous('dw($%x)=1'%(browser+B['launches']))
    s.rendezvous('dw($%x)=0'%(browser+B['child']));s.frames(80)
    require(num('result',4)==0,'Files warm-up native child failed')
    key('BACKSPACE');wait_listing(s,browser)
    menus.select('Shell');file_baseline=memory();file_owners=s.ledger()
    warm_free=free_ranges();warm_allocations=retained(cold_free,warm_free)
    (s.p['output']/'files-warmup-memory.json').write_text(json.dumps(dict(delta=cold[0]-file_baseline[0],allocations=warm_allocations),indent=2)+'\n')
    require(cold[0]-file_baseline[0]==112,'Unexpected first-child timer allocation')
    print('Files first-child warm-up bytes',cold[0]-file_baseline[0],flush=True)
    menus.select('Files')
    def content(a):
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(a+T['load']+LOAD_PHASE,a+T['dirty']))
        s.frames(70)
    def launch(name):
        menus.select('Files');select(s,browser,name,click);previous=num('launches',4)
        key('RETURN')
        s.rendezvous('dw($%x)=%d'%(browser+B['launches'],previous+1))
        child=num('child',4);require(child,'Files did not retain viewer')
        a=symbols(s.b,s.p,directory,'text',child)['GEMText']
        s.rendezvous('dw($%x)=1'%(a+T['ready']))
        return child,a
    child,a=launch('STORY.TXT');content(a)
    require(s.b.memdump(a+T['document']+14,128).split(b'\0')[0]==b'SYS:STORY.TXT','Files argument/path copy')
    menus.select('STORY.TXT');move(630,230);s.cells('files-text-open')
    menus.select('Files');previous=num('launches',4);key('RETURN')
    require(num('child',4)==child and num('launches',4)==previous,'Files started a second child')
    # Reusing Files scratch for navigation cannot change the child's argument copy.
    select(s,browser,'C',click);key('RETURN');wait_listing(s,browser)
    require(s.b.memdump(a+T['document']+14,128).split(b'\0')[0]==b'SYS:STORY.TXT','Files lent path storage')
    menus.select('STORY.TXT');key('O');s.frames(100)
    menus.select('Files');click(24,8);click(32,56)
    s.rendezvous('dw($%x)=0'%(browser+B['child']));s.frames(80)
    require(num('result',4)==0,'Selector Stop did not close viewer cleanly')
    menus.select('Shell');after=memory()
    audit=dict(before=file_baseline,after=after,allocations=retained(warm_free,free_ranges()))
    (s.p['output']/'files-after-stop-memory.json').write_text(json.dumps(audit,indent=2)+'\n')
    # The association is this parent's first C: assign use. DOS retains one
    # 256-byte expansion buffer until ReleaseContext; verify that exact range.
    require(after==[file_baseline[0]-256,file_baseline[1],file_baseline[2]-256,file_baseline[3]],
        'Unexpected Files assign-buffer allocation: '+repr((file_baseline,after)))
    require(len(audit['allocations'])==1 and audit['allocations'][0]['bytes']==256 and
        bytes.fromhex(audit['allocations'][0]['head']).startswith(b'D1:C/TEXT.APP\0'),
        'First association retained something other than its DOS assign buffer')
    require(s.ledger()==file_owners,'Stopped viewer retained ownership')
    file_baseline=after
    menus.select('Files')
    # An ordinary native program still launches with an empty argument tail.
    select(s,browser,'HELLO',click);previous=num('launches',4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(browser+B['launches'],previous+1))
    s.rendezvous('dw($%x)=0'%(browser+B['child']));s.frames(80)
    require(num('launches',4)==previous+1 and num('result',4)==0,'Native Files launch changed')
    # Non-text GEM applications keep the ordinary empty-tail launcher too.
    select(s,browser,'CALC.APP',click);previous=num('launches',4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(browser+B['launches'],previous+1))
    calc=symbols(s.b,s.p,directory,'calc',num('child',4))['Calculator']
    s.rendezvous('dw($%x)=1'%(calc+4));menus.select('Calculator');key('1');key('2')
    menus.select('Files');click(24,8);click(32,56)
    s.rendezvous('dw($%x)=0'%(browser+B['child']));s.frames(80)
    require(num('result',4)==0,'Ordinary GEM Files launch/Stop changed')
    menus.select('Shell');require(s.ledger()==file_owners and memory()==file_baseline,'Calculator Files launch leaked')
    menus.select('Files');key('BACKSPACE');wait_listing(s,browser)
    child,a=launch('LONG.TXT')
    s.rendezvous('dw($%x)=3'%(a+T['load']+LOAD_PHASE))
    def fast_click(x,y):
        move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(3)
        s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(3)
    # Reach the covered Files title through the real Windows menu, without
    # the ordinary helper's long observation waits consuming the whole load.
    windows=menus.windows();row=next(i for i,w in enumerate(windows) if w['title']=='Files')
    files_id=windows[row]['id']
    fast_click(472,8);s.rendezvous('db($%x)=2'%menus.at('DESKMENU','menu'))
    fast_click(472,24+row*16);s.rendezvous('dw($%x)=%d'%(menus.focus_address,files_id))
    fast_click(24,8);s.rendezvous('db($%x)=3'%menus.at('DESKMENU','menu'))
    require(s.number(a+T['load']+LOAD_PHASE,2)==3 and not s.number(a+T['loads'],4),
        'Read completed before physical Stop submission')
    fast_click(32,56);s.rendezvous('dw($%x)=0'%(browser+B['child']));s.frames(80)
    require(num('result',4)==0,'Read-time Stop did not close viewer cleanly')
    menus.select('Shell');require(s.ledger()==file_owners and memory()==file_baseline,'Read-time Stop leaked')
    child,a=launch('LONG.TXT');content(a);menus.select('LONG.TXT')
    move(630,230);s.cells('files-text-relaunch')
    # Parent close must stop and collect its child before its own retirement.
    key('O');s.frames(100);menus.select('Files')
    windows=menus.windows();retiring={w['id'] for w in windows if w['title'] in ('Files','LONG.TXT')}
    expected=min((w for w in windows if w['id'] not in retiring),key=lambda w:w['rank'])['id']
    # The ordinary close helper expects one retiring window; this action closes
    # both the Files parent and its child before focus settles on a survivor.
    click(472,8);click(472,24+(len(windows)+1)*16);collected()
    require(not any(w['id'] in retiring for w in menus.windows()),'Parent close left a window behind')
    require(menus.focus()==expected,'Parent close did not restore surviving focus')
    menus.select('Shell')
    require(s.ledger()==owners and memory()==baseline,'Files/viewer parent-close ownership leak')
    s.saved['text_files']=dict(open=True,quoted_path=True,caller_scratch_reuse=True,
        one_child=True,selector_stop=True,read_stop=True,native_launch=True,ordinary_gem_launch=True,panel_keyboard=True,relaunch=True,parent_close=True,heap_return=True,first_child_timer_bytes=112,first_association_assign_bytes=256)
