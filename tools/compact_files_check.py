"""Physical compact-folder controls and selection on the distributed demo."""
from browser_model import FIELDS as F,ROW_FIRST,listing,select,wait_listing
from native_program import require


def exercise(s,desk,base,click,key,path,shot,move):
    b=s.b
    n=lambda name:s.number(base+F[name],2)
    def work():return [s.number(base+F['work']+2*i,2) for i in range(4)]
    def text(name):return b.memdump(base+F[name],128).split(b'\0')[0].decode('ascii')
    def view(row):click(216,8);click(224,24+row*16)
    def file(row):click(152,8);click(168,24+row*16)
    def arrow(name,shift=False):
        b._cmd_ok('KEY CTRL down')
        if shift:b._cmd_ok('KEY SHIFT down')
        key(name)
        b._cmd_ok('KEY ALL up');s.frames(35)
    def icon_pixels(index=None):
        # Compare just the bitmap, excluding its independently selected label.
        at=s.number(base+F['tree'],4)+(ROW_FIRST+(n('selected') if index is None else index)+n('parent')-n('first'))*24
        x,y,w,h=work();x+=s.number(at+16,2)+32;y+=s.number(at+18,2)+2
        frame=b.rawscreen(str(s.p['output']/'compact-icon.bgra'))
        raw=(s.p['output']/'compact-icon.bgra').read_bytes()
        return b''.join(raw[yy*frame.stride+(x+16)*4:yy*frame.stride+(x+48)*4] for yy in range(y,y+20))
    require(work()[2:]==[336,152],'Compact default window size')
    require(n('visible')==9,'Compact default icon rows')
    require(' bytes in ' in text('status') and text('status')!=text('path'),'Top totals')
    shot('compact-files-initial')
    bounds=work()
    select(s,base,'C',click);key('RETURN');wait_listing(s,base)
    require(text('path')=='SYS:C' and work()==bounds,'Navigation resized folder')
    # Backspace is reserved for editing; Esc and the File menu go up.
    key('BACKSPACE');require(text('path')=='SYS:C','Backspace still navigates')
    key('P');require(n('dialog')==1,'Path dialog');key('ESC')
    require(n('dialog')==0 and text('path')=='SYS:C','Dialog Escape also navigated')
    file(7);wait_listing(s,base);require(text('path')=='SYS:','Parent menu')
    select(s,base,'C',click);key('RETURN');wait_listing(s,base);key('ESC');wait_listing(s,base)
    require(text('path')=='SYS:','Parent keyboard')
    before=s.number(base+F['paints'],4);key('ESC')
    require(s.number(base+F['paints'],4)==before,'Root Escape reread/repainted')
    require(not n('menuEnabled')&64,'Root Parent enabled')
    select(s,base,'README.TXT',click)
    move(632,232);s.frames(60);selected=icon_pixels()
    lead=n('selected');view(4);s.frames(60)
    # Select None clears membership and the lead; compare the same retained object.
    require(n('selectionCount')==0,'Select None did not clear selection')
    require(icon_pixels(lead)==selected,'Selection changed file artwork')
    select(s,base,'README.TXT',click)
    b._cmd_ok('KEY CTRL down');key('L');b._cmd_ok('KEY CTRL up');wait_listing(s,base)
    require(n('selectionCount')==1,'Refresh shortcut lost selection')
    file(1);wait_listing(s,base);require(n('selectionCount')==1,'Refresh menu lost selection')
    view(2);wait_listing(s,base);require(n('sortNames')==0,'Disk order toggle')
    view(2);wait_listing(s,base);require(n('sortNames')==1,'Name sort toggle')
    # Keyboard focus is distinct from selection, and a mouse click through its
    # decorative outline remains a normal selection rather than a control hit.
    view(4);arrow('ASTERISK');require(n('keyboardFocus')==1,'Keyboard focus missing')
    shot('compact-files-keyboard-icons')
    name=listing(s,base)[n('selected')];select(s,base,name,click)
    require(n('keyboardFocus')==0 and n('selectionCount')==1,'Focus decoration intercepted click')
    shot('compact-files-mouse-icons')
    view(1);arrow('EQUALS',True)
    require(n('keyboardFocus')==1 and n('selectionCount')==2,'List keyboard selection')
    shot('compact-files-keyboard-list')
    view(0);view(4)
    # Saved/restored size stays independent of the current directory contents.
    x,y,w,h=work();move(x+w+8,y+h+8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(x+w-24,y+h-16);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(150)
    resized=work();require(resized[2:]==[w-32,h-24],'Compact resize')
    path(base,'WORK:');require(work()==resized,'Sparse directory changed chosen size')
    path(base,'SYS:');x,y,w,h=work();click(x+w+8,y-8);s.frames(120)
    require(n('full')==1 and work()==[8,32,616,192],'Full geometry without INFO')
    shot('compact-files-full')
    x,y,w,h=work();click(x+w+8,y-8);s.frames(120)
    require(n('full')==0 and work()==resized,'Fuller did not restore user size')
    shot('compact-files-restored')
    path(base,'SYS:C');x,y,w,h=work();before=n('first');click(x+w+8,y+h-8)
    require(n('first')>before,'Compact scrolling')
    shot('compact-files-scrolled')
    # Parent is a navigation item, never part of file membership. Up reveals
    # the directory just left even when it lies beyond the first page.
    path(base,'WORK:NAV/ZLAST')
    require(n('count')==0 and n('parent')==1,'Empty directory omitted parent')
    select(s,base,'..',click)
    require(n('selected')==65534 and not n('selectionCount'),'Parent joined selection bitmap')
    require(n('menuEnabled')&1 and not n('menuEnabled')&52,'Parent mutation commands enabled')
    key('R');require(n('dialog')==0,'Parent Rename opened a dialog')
    b._cmd_ok('KEY CTRL down');key('L');b._cmd_ok('KEY CTRL up');wait_listing(s,base)
    require(n('selected')==65534,'Refresh lost parent focus')
    shot('compact-files-parent')
    key('RETURN');wait_listing(s,base)
    require(text('path')=='WORK:NAV' and n('first')>0 and listing(s,base)[n('selected')]=='ZLAST','Up did not reveal child')
    shot('compact-files-parent-return')
    view(2);wait_listing(s,base)
    select(s,base,'ZLAST',click);key('RETURN');wait_listing(s,base);key('ESC');wait_listing(s,base)
    require(text('path')=='WORK:NAV' and listing(s,base)[n('selected')]=='ZLAST','Disk-order upward selection')
    select(s,base,'..',click);b._cmd_ok('KEY SHIFT down');select(s,base,'..',click);b._cmd_ok('KEY SHIFT up')
    require(not n('selectionCount') and n('selected')==65534,'Modified parent joined file selection')
    view(3);require(n('selectionCount')==n('count'),'Select All included parent')
    require(n('selected')!=65534,'Select All retained parent action')
    path(base,'SYS:');require(n('parent')==0,'Volume root includes parent')
    click(120,100);shot('compact-files-inactive')
    x,y,w,h=work();click(x+120,y-8);s.frames(60)
    click(x,y-8);s.frames(160);shot('compact-files-closed')
    return dict(no_toolbar=True,parent_menu=True,parent_key=True,root_noop=True,dialog_escape=True,
        refresh_menu=True,refresh_key=True,status_totals=True,selection_artwork_unchanged=True,
        keyboard_focus=True,focus_click_through=True,icon_list=True,sort_toggle=True,
        resize=True,navigation_keeps_bounds=True,full_restore=True,scroll=True,
        distinct_gadgets=True,inactive_exposure=True,close=True,virtual_parent=True,empty_parent=True,upward_reveal=True,parent_mutation_exclusion=True,parent_refresh=True)


def colour_icons(s,desk,base,click,key,path,shot,move,menus):
    """Shared artwork pointers, real painting and ordinary app launching."""
    from gem_applications import instances,MODELS
    b=s.b;n=lambda name:s.number(base+F[name],2)
    def stock(name,index):
        select(s,base,name,click)
        cell=n('selected')+n('parent')-n('first')
        actual=b.memdump(base+F['icons']+cell*38,38)
        source=s.number(s.number(base+F['stock'],4)+index*24+12,4)
        expected=b.memdump(source,38)
        require(actual[:8]==expected[:8] and actual[34:]==expected[34:],'Wrong icon for '+name)
        require(int.from_bytes(actual[12:14],'little')&0xf00==0,'Desktop grey leaked into file label')
        require(int.from_bytes(actual[30:32],'little')==96,'File label width')
    stock('C',5);shot('files-colour-folders')
    stock('CALC.RSC',3);shot('files-colour-document')
    select(s,base,'C',click);key('RETURN');wait_listing(s,base)
    point=[]
    def parent_click(x,y):point[:]=[x,y];click(x,y)
    select(s,base,'..',parent_click)
    b._cmd_ok('KEY CTRL down');key('ASTERISK');b._cmd_ok('KEY CTRL up')
    require(n('selected')==0 and n('selectionCount')==1,'Arrow from parent skipped first file')
    b._cmd_ok('KEY CTRL down');key('MINUS');b._cmd_ok('KEY CTRL up')
    require(n('selected')==65534 and not n('selectionCount') and n('keyboardFocus'),'Arrow to parent joined membership')
    shot('files-parent-keyboard')
    move(*point)
    for _ in range(2):
        b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(2)
        b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(2)
    s.frames(100);wait_listing(s,base)
    require(b.memdump(base+F['path'],128).split(b'\0')[0]==b'SYS:','Parent double-click')
    require(listing(s,base)[n('selected')]=='C','Parent double-click did not reveal C')
    key('RETURN');wait_listing(s,base)
    stock('HELLO',11);shot('files-colour-console')
    stock('DESKTOP.APP',2);shot('files-colour-generic')
    for file,name,index in [('PANEL.APP','panel',6),('CALC.APP','calc',7),('TEXT.APP','text',8),('COUNTER.APP','counter',9)]:
        stock(file,index)
        # Selection must preserve artwork; the pixel oracle checks clipped
        # rows while select() also scrolls these entries into view.
        shot('files-colour-'+name)
        key('RETURN')
        for _ in range(60):
            found=[a for a in instances(b,s.p,s.p['output']/'bitmap-console') if a['name']==name]
            if found:break
            s.frames(20)
        require(found,'GUI icon launch failed: '+file)
        model,ready,work=MODELS[name];app=found[0]['symbols'][model]
        s.rendezvous('dw($%x)=1'%(app+ready));s.frames(100)
        x,y=[s.number(app+work+i*2,2) for i in range(2)]
        click(x,y-8);s.frames(120)
        require(not [a for a in instances(b,s.p,s.p['output']/'bitmap-console') if a['name']==name],'GUI app did not close: '+name)
        menus.select('SYS:C')
    path(base,'SYS:')
    shot('files-refinement-desktop')
    return dict(folder=True,document=True,console=True,generic_gui=True,shared_app_artwork=True,
        paper_labels=True,selected_pixels=True,scroll_and_clip=True,gui_launch_close=True,parent_arrows=True,parent_double_click=True)
