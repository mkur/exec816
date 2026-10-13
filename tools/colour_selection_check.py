"""Physical folder selection checks using the existing packaged desktop session."""
from browser_model import FIELDS as F, ROW_FIRST, listing, select, wait_listing
from colour_desktop_model import FIELDS as D
from native_program import require


def exercise(s, desk, base, click, key, path, desk_menu, shot, move, boundary=False):
    def n(name):return s.number(base+F[name],2)
    def work():return [s.number(base+F['work']+i*2,2) for i in range(4)]
    large_names=None
    def members():
        nonlocal large_names
        if n('count')==256:
            if large_names is None:large_names=listing(s,base)
            names=large_names
        else:names=listing(s,base)
        bits=s.b.memdump(base+F['selection'],32)
        result={name for i,name in enumerate(names) if bits[i//8] & (1<<(i%8))}
        require(len(result)==n('selectionCount'),'Selection count differs from membership: '+repr((len(result),n('selectionCount'),len(names),len(set(names)),bits.hex(),names[:4],names[-4:])))
        first=n('first');tree=s.number(base+F['tree'],4);parent=n('parent')
        for i in range(min(n('visible'),len(names)+parent-first)):
            entry=first+i-parent
            expected=(n('selected')==65534) if entry<0 else names[entry] in result
            require(bool(s.number(tree+(ROW_FIRST+i)*24+10,2)&1)==expected,
                    'Visible OBJECT selection disagrees with membership')
        return result
    def pick(name,shift=False):
        if shift:s.b._cmd_ok('KEY SHIFT down')
        select(s,base,name,click,stable_snapshot=name.startswith('E') and name.endswith('.TXT'))
        if shift:s.b._cmd_ok('KEY SHIFT up')
    def view(row):click(216,8);click(224,24+row*16)
    def all_key():
        s.b._cmd_ok('KEY CTRL down');key('A');s.b._cmd_ok('KEY CTRL up');s.frames(30)
    # A small writable directory also contains folders: Copy must not accept
    # a mixed selection, and sibling windows must own independent bitmaps.
    if not boundary:
        print('Selection: toggles, commands and refresh',flush=True)
        path(base,'WORK:');names=listing(s,base)
        pick('ALPHA.TXT');pick('BETA.TXT',True)
        require(members()=={'ALPHA.TXT','BETA.TXT'},'Shift-click did not add')
        key('RETURN');key('R');require(n('dialog')==0,'Multi-selection opened/renamed an arbitrary item')
        pick('ALPHA.TXT',True);require(members()=={'BETA.TXT'},'Shift-click did not remove lead')
        key('R');require(n('dialog')==3,'Single remaining member cannot be renamed')
        require(s.b.memdump(base+F['editText'],128).split(b'\0')[0]==b'BETA.TXT','Rename used deselected lead')
        key('ESC');pick('ALPHA.TXT',True)
        view(1);require(n('iconView')==0 and members()=={'ALPHA.TXT','BETA.TXT'},'List lost selection')
        view(2);wait_listing(s,base);require(members()=={'ALPHA.TXT','BETA.TXT'},'Disk order lost selected names')
        view(2);wait_listing(s,base);require(members()=={'ALPHA.TXT','BETA.TXT'},'Name sort lost selected names')
        s.b._cmd_ok('KEY CTRL down');key('L');s.b._cmd_ok('KEY CTRL up');wait_listing(s,base)
        require(members()=={'ALPHA.TXT','BETA.TXT'},'Refresh lost selection')
        view(3);require(members()==set(names),'Select All menu')
        require(n('selectionDirectories')>0,'Directory selection count')
        view(4);require(not members(),'Select None menu')
        all_key();require(members()==set(names),'Ctrl+A did not select cached entries')
        view(4);require(not members(),'Select None did not clear')
        pick('ALPHA.TXT');desk_menu(0);s.frames(150)
        peer=s.number(desk+D['folders']+4,4);require(peer and not s.number(peer+F['selectionCount'],2),'New folder inherited selection')
        require(members()=={'ALPHA.TXT'},'Sibling changed original selection')
        px,py=[s.number(peer+F['work']+i*2,2) for i in range(2)]
        click(px,py-8);s.frames(100)
        view(0);pick('BETA.TXT',True);shot('desktop-multiple-selection')
    # The scan cap and byte 31 of the bitmap are exercised with actual files.
    print('Selection: full directory and offscreen bitmap',flush=True)
    path(base,'WORK:SELECT');require(n('count')==256 and n('parent')==1 and n('truncated')==1,'256 real entries plus parent')
    require(not members(),'Navigation retained selection from another directory')
    all_key();require(len(members())==256,'Select All omitted offscreen entries')
    require(b'first 256' in s.b.memdump(base+F['status'],128),'Truncation warning hidden')
    x,y,w,h=work();height=h-32;thumb=max(8,height*(n('visible')*1000//(n('count')+n('parent')))//1000)
    move(x+w+8,y+16+thumb//2);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(x+w+8,y+h-16);s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(120)
    require(n('first')<=255+n('parent')<n('first')+n('visible'),'Thumb did not expose final entry')
    pick('E255.TXT',True);require(len(members())==255 and 'E255.TXT' not in members(),'Index 255 toggle')
    view(1);require(len(members())==255,'Offscreen selections lost switching view')
    view(4);pick('E000.TXT');require(members()=={'E000.TXT'},'Plain click did not replace set')
    shot('desktop-selection-boundary')
    path(base,'WORK:');require(not members(),'Directory navigation did not reset selection')
    s.saved['selection']=dict(boundary_only=boundary,all_clear=True,icon_list=True,boundary_255=True,truncated=True)
    if not boundary:s.saved['selection'].update(toggle=True,keyboard=True,single_command_gates=True,
        refresh_sort=True,independent_windows=True)
