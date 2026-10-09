"""Physical Files dialogs on the demo runner's disposable writable WORK disk."""
from browser_model import FIELDS as F, listing, select
from native_program import require
from test_shell_core import KEYS


def exercise(s,sy,click,move):
    base=sy['GEMBrowser'];b=s.b
    def n(name):return s.number(base+F[name],2)
    def text(name):return b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def key(name,shift=False):
        if shift:b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up')
        if shift:b._cmd_ok('KEY SHIFT up')
        s.frames(24)
    def fill(value):
        for _ in range(len(text('editText'))):key('BACKSPACE')
        for char in value:
            name,shift=KEYS[char];key(name,shift)
        require(text('editText')==value,'Dialog text entry: '+repr((text('editText'),value)))
    def opened(kind):
        s.rendezvous('dw($%x)=%d'%(base+F['dialog'],kind));s.frames(60)
    def closed():
        s.rendezvous('dw($%x)=0'%(base+F['dialog']));s.frames(90)
    def menu(item):click(24,8);click(40,24+(item-6)*16)
    def path(value):
        key('P');opened(1);fill(value);key('RETURN');closed()
        require(text('path')==value,'Path dialog did not navigate')
    original=text('path')
    menu(10);opened(1)
    s.cells('files-path-dialog');move(632,232);s.save_screen(s.p['output']/'files-path-dialog.png')
    # Covered exposure repairs the same steady caret without another input.
    counter=s.number(sy['GEMCounter']+14,4)
    s.menus.select('Shell');s.frames(70);s.menus.select('Files')
    require(s.number(sy['GEMCounter']+14,4)>counter,'Files dialog stopped another app')
    s.cells('files-dialog-exposed')
    fill('WORK:')
    for start,end,height in [((248,224),(248,152),72),((248,152),(248,224),144)]:
        move(*start);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(*end);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(160)
        require(s.number(base+F['work']+6,2)==height and n('dialog')==1,'Dialog resize')
        require(text('editText')=='WORK:','Resize lost typed path')
        s.cells('files-dialog-resize-'+str(height))
    key('TAB');key('RETURN');closed()
    require(text('path')=='WORK:','Keyboard default Path')
    menu(11);opened(2);fill('AAA');key('RETURN');closed()
    select(s,base,'AAA',click)
    require(listing(s,base)[n('selected')]=='AAA','New folder selection')
    # Duplicate creation is an operational failure and retains the dialog/text.
    key('N');opened(2);fill('AAA');key('RETURN');s.frames(150)
    require(n('dialog')==2 and s.number(base+F['dialogError'],4)==203,'Duplicate folder was accepted')
    require(text('editText')=='AAA','Failed operation lost text');key('ESC');closed()
    # Rename through the application menu, commit through a physical button.
    menu(12);opened(3);fill('BBB')
    x,y=[s.number(base+F['work']+i*2,2) for i in range(2)]
    click(x+32,y+52);closed();select(s,base,'BBB',click)
    require('AAA' not in listing(s,base),'Rename retained old directory entry')
    # A path separator is not a single leaf; Cancel does not mutate the disk.
    key('R');opened(3);fill('X/Y');key('RETURN')
    require(n('dialog')==3 and text('status')=='Enter one leaf name','Leaf validation')
    click(x+132,y+52);closed();require('BBB' in listing(s,base),'Cancel renamed a directory')
    # Enter an empty directory, then a missing/file path that must preserve it.
    path('WORK:BBB');require(n('count')==0,'New folder is not empty')
    for invalid in ('WORK:BAD','SYS:STORY.TXT'):
        key('P');opened(1);fill(invalid);key('RETURN');s.frames(150)
        require(n('dialog')==1 and text('path')=='WORK:BBB','Failed path replaced current directory')
        key('ESC');closed()
    path(original)
    s.saved['files_dialogs']=dict(path=True,new_folder=True,rename=True,duplicate_preserved=True,
        invalid_leaf=True,missing_path=True,file_path=True,empty_directory=True,
        keyboard_default=True,mouse_ok_cancel=True,escape_cancel=True,exposure_caret=True,
        counter_continued=True,resize_while_editing=True,bank_zero_delta=0)
    print('Files Path/New Folder/Rename checks passed',flush=True)
