"""Sequential Delete and deferred refresh through the real desktop event loop."""
from browser_model import FIELDS as F,listing,select,wait_listing
from colour_desktop_model import FIELDS as D,JOB_FIELDS as J
from native_program import require


def fixture(root):
    for name in ('MIX','FAIL','STOP','SRC','DST'):(root/name).mkdir()
    (root/'MIX/AEMPTY').mkdir();(root/'MIX/FILE.TXT').write_bytes(b'delete me')
    (root/'FAIL/AEMPTY').mkdir();(root/'FAIL/BFULL').mkdir()
    (root/'FAIL/BFULL/KEEP.TXT').write_bytes(b'keep descendant')
    (root/'FAIL/LATER.TXT').write_bytes(b'keep later')
    for i in range(12):(root/'STOP'/f'F{i:02d}.TXT').write_bytes(b'cancel boundary')
    (root/'SRC/ONE.BIN').write_bytes(bytes(range(256))*128)
    (root/'SRC/TWO.BIN').write_bytes(b'tail')
    (root/'DST/OLD.TXT').write_bytes(b'existing destination')


def exercise(s,desk,base,click,key,fill,path,desk_menu,shot,menus):
    def n(name):return s.number(base+F[name],2)
    def text(name):return s.b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def job():return s.number(desk+D['job'],4)
    def all_entries():
        s.b._cmd_ok('KEY CTRL down');key('A');s.b._cmd_ok('KEY CTRL up')
    def menu(row):click(24,8);click(40,24+row*16)
    def delete(confirm=True):
        menu(8);s.rendezvous('dw($%x)=6'%(base+F['dialog']))
        if confirm:
            x,y=[s.number(base+F['work']+i*2,2) for i in range(2)];click(x+32,y+52)
        else:key('RETURN')
    def finished(prefix):
        s.rendezvous('(dw($%x)|dw($%x))=0'%(desk+D['job'],desk+D['job']+2))
        s.rendezvous('dw($%x)=0'%(base+F['dialog']));s.frames(300)
        require(text('status').startswith(prefix),'Unexpected delete status: '+text('status'))
        return text('status')
    print('Batch Delete: default Cancel and mixed entries',flush=True)
    path(base,'WORK:MIX');all_entries();delete(False)
    require(n('selectionCount')==2 and len(listing(s,base))==2 and not job(),'Default Cancel mutated selection')
    delete();result=finished('Delete complete')
    require('2 done, 0 skipped, 0 left' in result and not n('count') and not n('selectionCount'),'Mixed Delete incomplete: '+result)
    print('Batch Delete: stop at nonempty directory',flush=True)
    path(base,'WORK:FAIL');all_entries();delete();result=finished('Delete failed')
    require('1 done, 0 skipped, 2 left' in result and n('selectionCount')==2,'Failure did not preserve pending selection: '+result)
    require(listing(s,base)==['BFULL','LATER.TXT'],'Delete continued after failure')
    shot('desktop-batch-delete-error')
    print('Batch Delete: cancellation between entries',flush=True)
    path(base,'WORK:STOP');all_entries();delete()
    address=job();require(address,'Delete completed before cancellation sample')
    s.rendezvous('dw($%x)>=1'%(address+J['completed']))
    key('ESC');finished('Delete cancelled')
    remaining=listing(s,base)
    require(0<len(remaining)<12 and n('selectionCount')==len(remaining),'Cancellation lost pending entries')
    s.saved['delete_remaining']=remaining
    path(base,'SYS:');all_entries();delete();finished('Delete failed')
    require(n('selectionCount')==n('count') and s.number(desk+D['error'],4),'Read-only Delete changed selection')

    print('Batch refresh: destination dialog and second-job exclusion',flush=True)
    path(base,'WORK:SRC');all_entries();desk_menu(0)
    s.rendezvous('(dw($%x)|dw($%x))!=0'%(desk+D['folders']+4,desk+D['folders']+6))
    peer=s.number(desk+D['folders']+4,4);wait_listing(s,peer);path(peer,'WORK:DST')
    select(s,peer,'OLD.TXT',click);menus.select('WORK:SRC')
    menu(7);s.rendezvous('dw($%x)=4'%(base+F['dialog']));fill(base,'work:dst');key('RETURN')
    s.rendezvous('((dw($%x)|dw($%x))!=0)|((dw($%x)=4)&(dw($%x)!=0))'%(desk+D['job'],desk+D['job']+2,base+F['dialog'],desk+D['error']))
    require(job(),'Deferred copy failed admission: '+repr((n('dialog'),text('status'),text('editText'),n('selectionCount'),n('selectionDirectories'),s.number(desk+D['error'],4))))
    address=job();menus.select('WORK:DST');menu(7)
    require(not s.number(peer+F['dialog'],2) and job()==address,'Sibling started another batch')
    key('N');s.rendezvous('dw($%x)=2'%(peer+F['dialog']));fill(peer,'TYPED')
    s.rendezvous('(dw($%x)|dw($%x))=0'%(desk+D['job'],desk+D['job']+2));s.frames(100)
    require(s.number(peer+F['refreshPending'],2)==1 and s.number(peer+F['count'],2)==1,'Sibling refreshed inside its dialog')
    require(s.b.memdump(peer+F['editText'],128).split(b'\0')[0]==b'TYPED','Refresh lost typed input')
    key('ESC');wait_listing(s,peer)
    require(not s.number(peer+F['refreshPending'],2) and set(listing(s,peer))=={'OLD.TXT','ONE.BIN','TWO.BIN'},'Deferred refresh did not run')
    require(n('selectionCount')==2,'Copy lost source selection')
    shot('desktop-deferred-refresh')
    s.saved['batch_delete']=dict(mixed=True,default_cancel=True,nonempty_stops=True,
        read_only=True,cancel_between_entries=True,pending_selection=True,
        deferred_refresh=True,typed_input=True,second_batch_excluded=True)


def readback(root,remaining):
    require(not list((root/'MIX').iterdir()),'Mixed Delete not persisted')
    require(not (root/'FAIL/AEMPTY').exists(),'Earlier completed Delete was undone')
    require((root/'FAIL/BFULL/KEEP.TXT').read_bytes()==b'keep descendant','Descendant changed')
    require((root/'FAIL/LATER.TXT').read_bytes()==b'keep later','Delete passed first error')
    require(sorted(p.name for p in (root/'STOP').iterdir())==sorted(remaining),'Cancelled Delete readback differs')
    for name in ('ONE.BIN','TWO.BIN'):
        require((root/'DST'/name).read_bytes()==(root/'SRC'/name).read_bytes(),'Deferred refresh copy bytes')
    require(not (root/'DST/TYPED').exists() and not (root/'DST/EXECCOPY.TMP').exists(),'Dialog or job left files')
