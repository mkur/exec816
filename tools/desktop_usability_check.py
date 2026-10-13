"""Physical desktop refinements on the packaged image; no guest-state edits."""
import struct
from browser_model import FIELDS as F,listing,select,wait_listing
from colour_desktop_model import FIELDS as D
from gem_applications import instances
from native_program import require


def exercise(s,desk,base,click,key,fill,path,desk_menu,shot,move,menus):
    b=s.b
    def n(name):return s.number(base+F[name],2)
    def text(name):return b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def work():return [s.number(base+F['work']+i*2,2) for i in range(4)]
    def objects():
        raw=b.memdump(base+F['dialogTree'],7*24)
        return [struct.unpack_from('<hhhHHHIhhhh',raw,i*24) for i in range(7)]
    def words(obj):return b.memdump(obj[6],128).split(b'\0')[0].decode('ascii')
    def button(index):
        tree=objects();o=tree[index]
        return tree[0][7]+o[7]+o[9]//2,tree[0][8]+o[8]+o[10]//2
    def menu(row):click(152,8);click(168,24+row*16)
    def begin_delete():
        menu(9);s.rendezvous('dw($%x)=6'%(base+F['dialog']))
        tree=objects();x,y,w,h=work();dx,dy,dw,dh=tree[0][7:]
        require(x<dx and y<dy and dx+dw<x+w and dy+dh<y+h,'Delete is not a compact overlay')
        require(tree[4][4]&2 and not tree[4][5]&1,'Cancel is not an unpressed default')
        return tree
    def finish_delete(prefix):
        s.rendezvous('dw($%x)=0'%(base+F['dialog']));s.frames(200)
        require(text('status').startswith(prefix),'Delete result: '+text('status'))

    require(work()[2:]==[432,164] and n('columns')==4 and n('visible')==16,'Default 4x4 layout')
    require(any(w['title']=='Shell' for w in menus.windows()),'Shell title not shortened')
    path(base,'SYS:C');shot('usability-grid')
    # Every label and selection extent remains on screen after shifting left.
    raw=b.memdump(desk+D['tree'],10*24)
    tree=[struct.unpack_from('<hhhHHHIhhhh',raw,i*24) for i in range(10)]
    labels=[]
    for o in tree[1:9]:
        ib=struct.unpack('<IIIH10hI',b.memdump(o[6],38))
        labels.append(b.memdump(ib[2],20).split(b'\0')[0].decode('ascii'))
        left=o[7]+ib[10];top=16+o[8]+ib[11]
        require(left>=0 and left+ib[12]<=96 and top+ib[13]<=240,'Desktop label clipped')
    require(labels==['SYS:','WORK:','RAM:','C:','Panel','Calculator','Text','Counter'],'Desktop icons')
    require(tree[1][7]==0,'Left margin not reduced')
    click(600,236)  # Activate the desktop before the double-click sequence.
    move(48,80)
    for _ in range(2):
        b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(2)
        b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(2)
    s.frames(160)
    ram=s.number(desk+D['folders']+4,4)
    require(ram,'RAM icon did not open a folder');wait_listing(s,ram)
    require(b.memdump(ram+F['path'],128).split(b'\0')[0]==b'RAM:','RAM icon opened wrong volume')
    shot('usability-ram')
    menus.select('SYS:C');path(base,'SYS:');select(s,base,'README.TXT',click)
    menu(8);fill(base,'RAM:README.TXT');key('RETURN')
    s.rendezvous('dw($%x)=0'%(base+F['dialog']));s.frames(200);wait_listing(s,ram)
    require('README.TXT' in listing(s,ram),'Copy to RAM missing')
    menus.select('Shell');s.command('CMP SYS:README.TXT RAM:README.TXT')
    menus.select('RAM:');rx,ry=[s.number(ram+F['work']+i*2,2) for i in range(2)]
    click(rx,ry-8);s.frames(100)
    require(not s.number(desk+D['folders']+4,4),'RAM folder did not close')

    menus.select('SYS:');path(base,'WORK:');select(s,base,'DELETE.TXT',click)
    tree=begin_delete()
    require(words(tree[1])=='Delete file?' and words(tree[2])=='DELETE.TXT','Single file wording')
    require(tree[5][4]&128,'Empty folder warning on a file')
    shot('usability-delete-file')
    key('RETURN');require(not n('dialog') and 'DELETE.TXT' in listing(s,base),'Default Cancel deleted file')
    begin_delete();move(*button(3));b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(30)
    require(objects()[3][5]&1,'Delete press not highlighted')
    # Release outside: clear the pressed state without performing the action.
    x,y,_,_=work();move(x+2,y+2);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(80)
    require(n('dialog')==6 and not objects()[3][5]&1,'Outside release activated/stuck Delete')
    shot('usability-delete-cancelled-press')
    key('ESC');require(not n('dialog') and text('path')=='WORK:','Escape navigated after dismissal')

    # A pending confirmation neither occupies another window slot nor stops
    # background work or another application's input and focus changes.
    desk_menu(4)
    for _ in range(60):
        found=[a for a in instances(b,s.p,s.p['output']/'bitmap-console') if a['name']=='counter']
        if found:break
        s.frames(20)
    require(found,'Desk > Counter did not launch')
    counter=found[0]['symbols']['GEMCounter']
    s.rendezvous('dw($%x)=1'%(counter+12));s.frames(100)
    menus.select('WORK:');before_windows=len(menus.windows());begin_delete()
    ticks=s.number(counter+14,4);s.frames(120)
    require(s.number(counter+14,4)>ticks,'Delete confirmation stopped Counter')
    require(len(menus.windows())==before_windows,'Delete consumed another window slot')
    menus.select('Shell');s.command('TASKS');menus.select('WORK:')
    require(n('dialog')==6,'Switching applications dismissed confirmation')
    shot('usability-delete-restored')
    key('TAB');require(n('focus')==3 and not objects()[3][5]&1,'Keyboard focus appears pressed')
    key('SPACE');finish_delete('Delete complete')
    require('DELETE.TXT' not in listing(s,base),'Keyboard Delete failed')
    menus.select('Counter');cx,cy=[s.number(counter+38+i*2,2) for i in range(2)]
    click(cx,cy-8);s.frames(150);menus.select('WORK:')

    path(base,'WORK:MIX')
    b._cmd_ok('KEY CTRL down');key('A');b._cmd_ok('KEY CTRL up')
    tree=begin_delete()
    require(words(tree[1])=='Delete selected items?' and words(tree[2])=='1 file, 1 folder','Mixed selection counts')
    require(not tree[5][4]&128 and words(tree[5])=='Empty folders only','Folder limit missing')
    shot('usability-delete-mixed');click(*button(3));finish_delete('Delete complete')
    require(not n('count'),'Mixed file/empty folder deletion failed')
    path(base,'WORK:FAIL');select(s,base,'BFULL',click)
    tree=begin_delete();require(words(tree[1])=='Delete folder?','Folder wording')
    click(*button(3));finish_delete('Delete failed')
    require('Folder is not empty' in text('status') and 'BFULL' in listing(s,base),'Nonempty-folder failure')
    shot('usability-delete-nonempty')
    # Frame and object clipping after a resize and list-view switch.
    select(s,base,'LATER.TXT',click);begin_delete()
    x,y,w,h=work();move(x+w+8,y+h+8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(x+w-88,y+h-32);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(120)
    shot('usability-delete-resized');key('ESC')
    click(216,8);click(224,40);begin_delete();shot('usability-delete-list')
    tree=objects()
    click(tree[0][7]+tree[6][7]+5,tree[0][8]+tree[6][8])
    require(not n('dialog') and 'LATER.TXT' in listing(s,base),'Mouse Cancel failed')
    shot('usability-delete-finished')
    return dict(grid_4x4=True,ram_icon=True,ram_copy_equal=True,desktop_margin=True,
                shell_name=True,compact_delete=True,default_cancel=True,mouse_press_cancel=True,
                keyboard_delete=True,mixed_delete=True,nonempty_error=True,other_apps=True,
                exposure=True,resize=True,list=True,bank_zero_reserved_delta=0)
