"""Desktop file operations through physical input on disposable writable media."""
from browser_model import FIELDS as F, listing, select, wait_listing
from native_program import require


def exercise(s, desk, base, click, key, fill, path, desk_menu, shot):
    from colour_desktop_model import FIELDS as D
    confirmation_checked=False
    def n(name, size=2):return s.number(base+F[name],size)
    def text(name):return s.b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def menu(row):click(24,8);click(40,24+row*16)
    def dialog(kind):s.rendezvous('dw($%x)=%d'%(base+F['dialog'],kind))
    def closed():dialog(0);s.frames(90)
    def copy_to(target):
        print('Desktop copy to',target,flush=True)
        menu(7);dialog(4);fill(base,target);key('RETURN')
        print('Copy submitted',n('dialog'),text('editText'),text('status'),flush=True)
    def alert(confirm=False):
        nonlocal confirmation_checked
        for _ in range(30):
            if n('dialog') in (6,7):break
            s.frames(10)
        require(n('dialog') in (6,7),'Confirmation did not remain open')
        if n('dialog')==6 and not confirmation_checked:
            shot('desktop-delete-confirm')
            desk_menu(0);s.frames(200)
            peer=s.number(desk+D['folders']+4,4)
            require(peer and peer!=base,'Cannot open a sibling beside confirmation')
            x,y=[s.number(peer+F['work']+i*2,2) for i in range(2)]
            click(x,y-20);s.frames(100)
            require(n('dialog')==6,'Sibling closure dismissed confirmation')
            confirmation_checked=True
        if not confirm:key('RETURN');return
        x,y=[s.number(base+F['work']+i*2,2) for i in range(2)]
        click(x+32,y+52)
    def complete():
        for _ in range(300):
            if not n('dialog') and text('status')=='Copy complete':break
            s.frames(40)
        require(not n('dialog'),'Copy did not finish: '+repr((n('dialog'),text('status'),text('editText'),s.number(desk+D['copy'],4),s.number(desk+D['error'],4))))
        require(not s.number(desk+D['error'],4),'Copy reported an error')
        s.frames(90)
    path(base,'WORK:');print('Desktop writable folder',flush=True)
    key('N');dialog(2);fill(base,'AAA');key('RETURN');closed()
    select(s,base,'AAA',click)
    key('R');dialog(3);fill(base,'BBB');key('RETURN');closed()
    require('BBB' in listing(s,base) and 'AAA' not in listing(s,base),'Folder rename')
    select(s,base,'BBB',click);menu(8);alert();s.frames(100)
    require('BBB' in listing(s,base),'Default Delete must cancel: '+repr((text('path'),text('status'),listing(s,base))))
    menu(8);alert(True);wait_listing(s,base)
    require('BBB' not in listing(s,base),'Confirmed empty-folder delete');print('Desktop New/Rename/Delete',flush=True)
    select(s,base,'SOURCE.TXT',click);copy_to('WORK:COPY.TXT');complete()
    require('COPY.TXT' in listing(s,base),'Completed copy missing')
    select(s,base,'SOURCE.TXT',click);copy_to('WORK:COPY.TXT')
    alert();closed()
    require(not s.number(desk+D['copy'],4),'Default overwrite must cancel')
    copy_to('WORK:COPY.TXT');alert(True);complete()
    # An unfinished copy is cancelled after data has reached its temporary file.
    print('Desktop Copy/Replace',flush=True)
    select(s,base,'BIG.BIN',click);copy_to('WORK:CANCEL.BIN');dialog(5)
    require(s.number(desk+D['copy'],4),'No incremental copy job')
    key('ESC');closed()
    require(text('status')=='Copy cancelled' and not s.number(desk+D['error'],4),
        'Cancel was replaced by a copy failure: '+text('status'))
    require('CANCEL.BIN' not in listing(s,base),'Cancelled copy published destination')
    require('EXECCOPY.TMP' not in listing(s,base),'Cancelled copy retained temporary')
    # Operational failure keeps the typed path and directory state available.
    select(s,base,'SOURCE.TXT',click);copy_to('SYS:COPY.TXT');s.frames(100)
    require(n('dialog')==4 and s.number(desk+D['error'],4),'Read-only copy did not fail')
    require(text('editText')=='SYS:COPY.TXT','Failed copy lost destination text')
    key('ESC');closed()
    select(s,base,'BIG.BIN',click);copy_to('WORK:SOURCE.TXT');alert(True)
    for _ in range(300):
        if not n('dialog') and text('status').startswith('Copy failed'):break
        s.frames(40)
    require(not n('dialog') and s.number(desk+D['error'],4)==221,
        'Partial copy did not report disk full: '+repr((n('dialog'),
        s.number(desk+D['error'],4),text('status'),s.number(desk+D['copy'],4))))
    require(text('status').startswith('Copy failed'),'Missing partial-copy error status')
    print('Desktop copy cancellation and failures',flush=True)
    select(s,base,'DELETE.TXT',click);menu(8);alert(True);wait_listing(s,base)
    require('DELETE.TXT' not in listing(s,base),'Confirmed file delete')
    from gem_applications import instances
    from text_model import FIELDS as T
    select(s,base,'SOURCE.TXT',click);key('RETURN')
    for _ in range(60):
        viewers=[a for a in instances(s.b,s.p,s.p['output']/'bitmap-console') if a['name']=='text']
        if viewers:break
        s.frames(20)
    require(viewers,'TXT association did not launch the viewer')
    viewer=viewers[0]['symbols']['GEMText']
    s.rendezvous('dw($%x)=1'%(viewer+T['loads']))
    require(s.b.memdump(viewer+T['document']+14,128).split(b'\0')[0]==b'WORK:SOURCE.TXT','Association lost copied path arguments')
    x,y=[s.number(viewer+T['work']+i*2,2) for i in range(2)]
    click(x,y-8);s.frames(200)
    require(not any(a['name']=='text' for a in instances(s.b,s.p,s.p['output']/'bitmap-console')),'Viewer completion was not collected')
    # Save an independently identifiable folder state, then inspect it after EXIT.
    click(88,8);click(96,40);s.frames(80)  # View > List
    require(n('iconView')==0,'List mode was not selected')
    desk_menu(5);s.frames(120)
    require(not s.number(desk+D['error'],4),'Save Settings failed')
    shot('desktop-file-operations')
    s.saved['colour_files']=dict(new_folder=True,rename=True,delete_cancel=True,
        delete_file=True,delete_empty_folder=True,copy=True,overwrite_cancel=True,
        overwrite=True,copy_cancel=True,read_only_error=True,partial_write_error=True,
        failed_overwrite_preserved=True,association=True,collected_child=True,
        confirmation_sibling=confirmation_checked,save_settings=True)
