"""Physical browser/RSC/popup/launcher cases for the exact OF816 desktop."""
from native_program import require
from stack_budget import stack_usage
from browser_model import FIELDS as F, listing, select


def exercise(s,sy,click,move):
    b=s.b;base=sy['GEMBrowser']
    def num(off,n=2):return s.number(base+off,n)
    def string(off):return b.memdump(base+off,128).split(b'\0')[0].decode('ascii')
    def key(name):
        b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up');s.frames(70)
    def bar(item,keyboard=False):
        if keyboard:
            s.menus.key('ESC',ctrl=True,shift=True)
            enabled=[i for i in range(6,10) if not num(F['bar']+i*24+10)&8]
            for _ in range(enabled.index(item)+1):s.menus.key('TAB')
            s.menus.key('RETURN')
        else:
            click(24,8);click(32,24+(item-6)*16)
        s.frames(100)
    def names():return listing(s,base)
    def row(name):select(s,base,name,click)
    s.rendezvous('dw($%x)=1'%(base+8));s.frames(180)
    require(string(178)=='SYS:','Browser initial directory')
    s.menus.select('Files');s.frames(80)
    s.cells('browser-front');s.save_screen(s.p['output']/'browser.png')
    initial=names();require('C' in initial,'Directory entries did not come from SYS')
    require(num(F['bar']+6*24+10)==8 and num(F['bar']+8*24+10)==8,'Initial menu availability')
    click(24,8);move(632,232);s.cells('files-menu-disabled');s.menus.key('ESC')
    row('C');bar(6,True);require(string(178)=='SYS:C','Menu Open directory')
    row('HELLO')
    old=num(F['launches'],4);bar(6)
    s.rendezvous('dw($%x)=0'%(base+F['child']));s.frames(100)
    require(num(F['launches'],4)==old+1 and num(F['result'],4)==0,'HELLO launch/collection')
    print('Browser native HELLO launch pass',flush=True)
    # A resource-loaded popup handles keyboard cancel and selection.
    key('F');key('ESC');require(num(8)==1,'Popup Escape closed browser')
    key('F');key('TAB');key('RETURN');s.frames(100)
    require(num(F['selected'])>=0 and names()[num(F['selected'])]=='HELLO','Popup Refresh lost selection')
    # Exercise actual scroll/resize gadgets with a selected filename retained.
    selected_name=names()[num(F['selected'])]
    old_visible=num(F['visible']);old_first=num(F['first'])
    click(248,208);s.frames(90)
    require(num(F['first'])==min(old_first+1,num(F['count'])-old_visible),'Files down arrow')
    move(248,224);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(248,176);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
    require(num(F['visible'])==4,'Files height did not set visible rows')
    require(names()[num(F['selected'])]==selected_name,'Shrink lost selected filename')
    s.cells('files-shrunk')
    move(248,176);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(312,224);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
    require(num(F['visible'])==8 and num(F['work']+4)==280,'Files grow layout')
    s.cells('files-grown')
    move(312,224);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(248,224);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
    require(num(F['work']+4)==216,'Files restore width')
    s.saved['files_scrolling']=dict(snapshot_entries=num(F['count']),rows=[old_visible,4,8],
        continuous_scroll=True,resize=True,preserved_selection=selected_name,pixel_repair=True)
    if 'objc_edit' in sy and 'files_dialogs' not in s.saved:
        from files_dialog_check import exercise as dialogs
        dialogs(s,sy,click,move)
    # Browser stays responsive while a command runs; close requests a break
    # and collects it before the browser Task can retire.
    row('TICK');old=num(F['launches'],4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(base+F['launches'],old+1));s.frames(50)
    require(num(F['launches'],4)==old+1 and num(F['child'],4)!=0,'TICK did not start')
    s.saved['desktop_peak_tasks']=s.ledger()['live']
    require(s.saved['desktop_peak_tasks']==8,'Launch did not use all eight Tasks')
    require(num(F['bar']+6*24+10)==8 and num(F['bar']+8*24+10)==0,'Live-child menu availability')
    if 'objc_edit' in sy:
        key('N');s.rendezvous('dw($%x)=2'%(base+F['dialog']))
    bar(8,True)
    s.rendezvous('dw($%x)=0'%(base+F['child']));s.frames(100)
    require(num(F['result'],4)!=0 or num(F['result']+4,4)==304,'Stopped command result')
    if 'objc_edit' in sy:
        require(num(F['dialog'])==2,'Child completion dismissed Files dialog')
        key('ESC');s.rendezvous('dw($%x)=0'%(base+F['dialog']))
        s.saved['files_dialogs']['child_collection_while_editing']=True
    print('Browser menu Stop/collection pass',flush=True)
    click(120,88);require(string(178)=='SYS:','Parent directory')
    row('STORY.TXT');old=num(F['launches'],4);key('RETURN')
    require(num(F['launches'],4)==old and not num(F['child'],4),'Text file accepted as executable')
    # Explicit popup mouse cancel; same loaded object tree and public API.
    click(48,88);s.frames(80);click(80,160);s.frames(100)
    require(num(8)==1,'Popup mouse cancel closed browser')
    popup_stacks=stack_usage(b,s.p['build']['memory'])
    click(96,32);s.command('TASKS')
    # Release an initial app while the shell waits, then let Files own a new
    # private panel. Stop is an AES close, with ordinary Process collection.
    click(592,56)
    if 'panel_settings' in s.saved:
        click(456,104)
        require(s.number(sy['GEMPanel']+400,2)==1 and s.number(sy['GEMPanel']+402,2)==0,
                'Close-with-pending-edit setup')
    if hasattr(s,'menus'):s.menus.close()
    else:click(424,56)
    s.rendezvous('dw($%x)=0'%sy['GEMDesktopChildren'])
    s.menus.select('Files');row('C');key('RETURN');row('PANEL.APP');key('RETURN')
    s.rendezvous('(dw($%x)!=0)|(dw($%x)=$6143)'%(base+F['child'],base+F['status']))
    child=num(F['child'],4);require(child!=0,'Files did not launch a GEM app')
    from gem_applications import symbols
    panel=symbols(b,s.p,s.p['output']/'bitmap-console','panel',child)['GEMPanel']
    s.rendezvous('dw($%x)=1'%(panel+8));s.frames(100)
    if hasattr(s,'menus'):
        current=s.menus.select('Control Panel')
        require(current not in s.menus.closed,'Window menu reused a retired identity')
        s.saved['desktop_menu']['window_reuse']=True
    if 'panel_settings' in s.saved:
        require(s.number(panel+402,2)==s.saved['panel_settings']['reopen_profile'],'Reopened panel lost session preference')
        s.saved['panel_settings']['reopen_verified']=True
    click(456,104)
    require(s.number(panel+400,2)==1 and s.number(panel+178+2*24+10,2)==0,'Loaded child panel Defaults')
    from loadable_gem_feedback import measure
    measure(s,panel,move,'reloaded')
    s.menus.select('Files');bar(8)
    s.rendezvous('dw($%x)=0'%(base+F['child']));s.frames(100)
    require(num(F['result'],4)==0,'GUI Stop did not return cleanly')
    print('Browser GEM launch/input/Stop pass',flush=True)
    # Close during a popup with a live child: defer WM_CLOSED, then BREAK/wait
    # before releasing the owning application. One launch slot remains.
    s.menus.select('Files');row('TICK')
    old=num(F['launches'],4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(base+F['launches'],old+1));key('F')
    menu=num(174,4)
    require(s.number(menu+18,2)!=0,'Popup did not enter its wait')
    s.saved['browser_stacks']=stack_usage(b,s.p['build']['memory'])
    click(24,64)
    s.rendezvous('dw($%x)=2'%sy['GEMDesktopDone']);s.frames(100)
    require(s.number(sy['GEMDesktopChildren']+8,4)==0,'Idle owner retained Files image')
    require(s.number(sy['GEMDesktopFailure'],2)==0,'Browser teardown failed')
    s.saved['browser']=dict(application_menu=True,menu_keyboard=True,menu_open=True,menu_stop=True,menu_disabled=True,resource=True,navigation=True,popup_keyboard=True,popup_mouse=True,
        launch='HELLO',cancel='TICK',gem_launch='PANEL.APP',gem_stop=True,
        idle_collection=True,invalid_executable=True,close_during_popup_with_child=True,
        popup_stacks=popup_stacks)
