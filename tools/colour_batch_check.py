"""Batch file operations through actual input and independent disk readback."""
from browser_model import FIELDS as F,listing,select,wait_listing
from colour_desktop_model import FIELDS as D,JOB_FIELDS as J
from native_program import require

PAYLOADS={'AEMPTY.BIN':b'', 'BSHORT.BIN':bytes(range(37)),
          'CEXACT.BIN':bytes(range(256))*64,
          'DTAIL.BIN':bytes(range(256))*128+bytes(range(37)),
          'ELARGE.BIN':bytes(range(256))*512}


def fixture(root):
    for name in ('SRC','DST','COLLIDE','CANCEL','CONFLICT'):(root/name).mkdir()
    for name,value in PAYLOADS.items():(root/'SRC'/name).write_bytes(value)
    for name in ('AEMPTY.BIN','BSHORT.BIN','CEXACT.BIN'):
        (root/'COLLIDE'/name).write_bytes(b'original '+name.encode())
    (root/'CONFLICT'/'EXECCOPY.TMP').write_bytes(b'preexisting temporary')


def exercise(s,desk,base,click,key,fill,path,desk_menu,shot):
    def n(name):return s.number(base+F[name],2)
    def text(name):return s.b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def job():return s.number(desk+D['job'],4)
    def menu(row):click(24,8);click(40,24+row*16)
    def chosen(names):
        key('ESC')
        for i,name in enumerate(names):
            if i:s.b._cmd_ok('KEY SHIFT down')
            select(s,base,name,click)
            if i:s.b._cmd_ok('KEY SHIFT up')
        require(n('selectionCount')==len(names),'Wrong batch selection')
    def start(names,target):
        chosen(names);menu(7);s.rendezvous('dw($%x)=4'%(base+F['dialog']))
        fill(base,target);key('RETURN')
    def wait_result(prefix):
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2))
        s.rendezvous('dw($%x)=0'%(base+F['dialog']));s.frames(300)
        require(text('status').startswith(prefix),'Wrong batch outcome: '+text('status'))
        return text('status')
    def choose(action):
        s.rendezvous('dw($%x)=7'%(base+F['dialog']));s.frames(30)
        require(job() and s.number(job()+J['state'],2)==3,'Overwrite did not wait')
        address=job();previous=s.number(address+J['index'],2)
        if action=='cancel':key('RETURN')
        else:
            x,y=[s.number(base+F['work']+i*2,2) for i in range(2)]
            click(x+(32 if action=='replace' else 100),y+52)
            s.rendezvous('((dw($%x)|dw($%x))=0)|(dw($%x)>%d)'%
                         (desk+D['job'],desk+D['job']+2,address+J['index'],previous))
    path(base,'WORK:SRC')
    print('Batch Copy: exact bytes and tail',flush=True)
    start(list(PAYLOADS)[:4],'WORK:DST')
    result=wait_result('Copy complete');require('4 done' in result and '0 left' in result,'Incomplete batch: '+result)
    shot('desktop-batch-copy')
    print('Batch Copy: Replace, Skip and default Cancel',flush=True)
    start(list(PAYLOADS)[:4],'WORK:COLLIDE');choose('replace');choose('skip');choose('cancel')
    result=wait_result('Copy cancelled');require('1 done, 1 skipped, 2 left' in result,'Wrong partial batch summary: '+result)
    start(list(PAYLOADS)[:2],'WORK:COLLIDE');choose('skip');choose('skip')
    result=wait_result('Copy complete');require('0 done, 2 skipped, 0 left' in result,'All-skipped batch')
    print('Batch Copy: cancellation after one file',flush=True)
    start(['AEMPTY.BIN','ELARGE.BIN'],'WORK:CANCEL')
    s.rendezvous('((dw($%x)|dw($%x))!=0)|(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2,base+F['dialog']))
    address=job();require(address,'Copy did not start: '+repr((n('dialog'),text('status'),text('editText'),n('selectionCount'),s.number(desk+D['error'],4))))
    s.rendezvous('(dw($%x)=1)&(dw($%x)=2)'%(address+J['completed'],address+J['state']))
    key('ESC');result=wait_result('Copy cancelled')
    require('1 done, 0 skipped, 1 left' in result,'Cancel affected wrong file: '+result)
    start(['AEMPTY.BIN','BSHORT.BIN'],'WORK:CONFLICT');result=wait_result('Copy failed')
    require('0 done' in result and s.number(desk+D['error'],4),'Existing temp was accepted')
    start(['AEMPTY.BIN','BSHORT.BIN'],'SYS:');wait_result('Copy failed')
    require(s.number(desk+D['error'],4),'Read-only batch did not fail')
    print('Batch Copy: close owner at overwrite prompt',flush=True)
    start(['AEMPTY.BIN','BSHORT.BIN'],'WORK:COLLIDE')
    s.rendezvous('dw($%x)=7'%(base+F['dialog']))
    x,y=[s.number(base+F['work']+i*2,2) for i in range(2)]
    click(x,y-20);s.frames(100)
    require(not job() and not s.number(desk+D['folders'],4),'Owner close retained batch')
    click(600,236);desk_menu(0)
    s.rendezvous('(dw($%x)|dw($%x))!=0'%(desk+D['folders'],desk+D['folders']+2))
    base=s.number(desk+D['folders'],4)
    require(base,'Cannot reopen folder after batch cleanup');wait_listing(s,base)
    path(base,'WORK:SRC')
    start(['AEMPTY.BIN','BSHORT.BIN'],'WORK:COLLIDE')
    s.rendezvous('dw($%x)=7'%(base+F['dialog']))
    desk_menu(6);s.frames(200)
    require(not any(a['name']=='desktop' for a in __import__('gem_applications').instances(s.b,s.p,s.p['output']/'bitmap-console')),
            'Quit Desktop retained owner or job')
    s.saved['batch_copy']=dict(binary_bytes=True,empty=True,tail=True,replace_skip_cancel=True,
        all_skipped=True,cancel_after_completed=True,temp_conflict=True,read_only=True,
        owner_close_prompt=True,desktop_quit_prompt=True)


def readback(root):
    for name,value in PAYLOADS.items():require((root/'SRC'/name).read_bytes()==value,'Source changed: '+name)
    for name in list(PAYLOADS)[:4]:require((root/'DST'/name).read_bytes()==PAYLOADS[name],'Copy bytes: '+name)
    require((root/'COLLIDE/AEMPTY.BIN').read_bytes()==PAYLOADS['AEMPTY.BIN'],'Replace did not publish')
    for name in ('BSHORT.BIN','CEXACT.BIN'):
        require((root/'COLLIDE'/name).read_bytes()==b'original '+name.encode(),'Skip/cancel replaced '+name)
    require(not (root/'COLLIDE/DTAIL.BIN').exists(),'Copy continued after cancel')
    require((root/'CANCEL/AEMPTY.BIN').read_bytes()==b'' and not (root/'CANCEL/ELARGE.BIN').exists(),'Partial batch cancellation')
    require((root/'CONFLICT/EXECCOPY.TMP').read_bytes()==b'preexisting temporary','Destroyed preexisting temp')
    for folder in ('SRC','DST','COLLIDE','CANCEL'):require(not (root/folder/'EXECCOPY.TMP').exists(),'Temporary left in '+folder)
