"""Physical compact-folder controls and selection on the distributed demo."""
from browser_model import FIELDS as F,listing,select,wait_listing
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
        at=s.number(base+F['tree'],4)+(4+(n('selected') if index is None else index)-n('first'))*24
        x,y,w,h=work();x+=s.number(at+16,2)+32;y+=s.number(at+18,2)+2
        frame=b.rawscreen(str(s.p['output']/'compact-icon.bgra'))
        raw=(s.p['output']/'compact-icon.bgra').read_bytes()
        return b''.join(raw[yy*frame.stride+(x+16)*4:yy*frame.stride+(x+48)*4] for yy in range(y,y+20))
    require(work()[2:]==[336,152],'Compact default window size')
    require(n('visible')==6,'Compact default icon rows')
    require(' bytes in ' in text('status') and text('status')!=text('path'),'Bottom totals')
    shot('compact-files-initial')
    bounds=work()
    select(s,base,'C',click);key('RETURN');wait_listing(s,base)
    require(text('path')=='SYS:C' and work()==bounds,'Navigation resized folder')
    # Small glyph, global menu, and Backspace have the same parent operation.
    x,y,w,h=work();click(x+20,y+8);wait_listing(s,base)
    require(text('path')=='SYS:','Parent glyph: '+repr((text('path'),text('status'),n('armed'),n('down'))))
    select(s,base,'C',click);key('RETURN');wait_listing(s,base);file(7);wait_listing(s,base)
    require(text('path')=='SYS:','Parent menu')
    select(s,base,'C',click);key('RETURN');wait_listing(s,base);key('BACKSPACE');wait_listing(s,base)
    require(text('path')=='SYS:','Parent keyboard')
    select(s,base,'README.TXT',click)
    move(632,232);s.frames(60);selected=icon_pixels()
    lead=n('selected');key('ESC');s.frames(60)
    # Escape clears membership and the lead; compare the same retained object.
    require(n('selectionCount')==0,'Escape did not clear selection')
    require(icon_pixels(lead)==selected,'Selection changed file artwork')
    select(s,base,'README.TXT',click)
    x,y,w,h=work();click(x+48,y+8);wait_listing(s,base)
    require(n('selectionCount')==1 and listing(s,base)[n('selected')]=='README.TXT','Refresh glyph lost selection')
    b._cmd_ok('KEY CTRL down');key('L');b._cmd_ok('KEY CTRL up');wait_listing(s,base)
    require(n('selectionCount')==1,'Refresh shortcut lost selection')
    file(1);wait_listing(s,base);require(n('selectionCount')==1,'Refresh menu lost selection')
    view(2);wait_listing(s,base);require(n('sortNames')==0,'Disk order toggle')
    view(2);wait_listing(s,base);require(n('sortNames')==1,'Name sort toggle')
    # Keyboard focus is distinct from selection, and a mouse click through its
    # decorative outline remains a normal selection rather than a control hit.
    key('ESC');arrow('ASTERISK');require(n('keyboardFocus')==1,'Keyboard focus missing')
    shot('compact-files-keyboard-icons')
    name=listing(s,base)[n('selected')];select(s,base,name,click)
    require(n('keyboardFocus')==0 and n('selectionCount')==1,'Focus decoration intercepted click')
    shot('compact-files-mouse-icons')
    view(1);arrow('EQUALS',True)
    require(n('keyboardFocus')==1 and n('selectionCount')==2,'List keyboard selection')
    shot('compact-files-keyboard-list')
    view(0);key('ESC')
    # Saved/restored size stays independent of the current directory contents.
    x,y,w,h=work();move(x+w+8,y+h+8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(x+w-24,y+h-16);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(150)
    resized=work();require(resized[2:]==[w-32,h-24],'Compact resize')
    path(base,'WORK:');require(work()==resized,'Sparse directory changed chosen size')
    path(base,'SYS:');x,y,w,h=work();click(x+w+8,y-8);s.frames(120)
    require(n('full')==1 and work()==[8,32,616,192],'Full geometry without INFO')
    x,y,w,h=work();click(x+w+8,y-8);s.frames(120)
    require(n('full')==0 and work()==resized,'Fuller did not restore user size')
    path(base,'SYS:C');x,y,w,h=work();before=n('first');click(x+w+8,y+h-8)
    require(n('first')>before,'Compact scrolling')
    shot('compact-files-scrolled')
    return dict(navigation_glyph=True,parent_menu=True,parent_key=True,refresh_glyph=True,
        refresh_menu=True,refresh_key=True,status_totals=True,selection_artwork_unchanged=True,
        keyboard_focus=True,focus_click_through=True,icon_list=True,sort_toggle=True,
        resize=True,navigation_keeps_bounds=True,full_restore=True,scroll=True)
