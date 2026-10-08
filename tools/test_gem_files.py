"""Physical browser/RSC/popup/launcher cases for the exact OF816 desktop."""
from native_program import require
from stack_budget import stack_usage


def exercise(s,sy,click,move):
    b=s.b;base=sy['GEMBrowser']
    def num(off,n=2):return s.number(base+off,n)
    def string(off):return b.memdump(base+off,128).split(b'\0')[0].decode('ascii')
    def key(name):
        b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up');s.frames(70)
    def bar(item,keyboard=False):
        if keyboard:
            s.menus.key('ESC',ctrl=True,shift=True)
            enabled=[i for i in range(6,10) if not num(2028+i*24+10)&8]
            for _ in range(enabled.index(item)+1):s.menus.key('TAB')
            s.menus.key('RETURN')
        else:
            click(24,8);click(32,24+(item-6)*16)
        s.frames(100)
    def names():
        raw=b.memdump(base+306,8*108)
        return [raw[i*108:(i+1)*108].split(b'\0')[0].decode('ascii') for i in range(num(1962))]
    def row(name):
        observed=[]
        for page in range(12):
            listing=names()
            observed.append(dict(page=num(1964),names=listing,count=num(1962),
                path=string(178),status=string(1386),selected=num(1966),down=num(1968),armed=num(1970)))
            if string(1386)=='Directory unavailable':
                observed[-1]['dos_storage']=s.b.memdump(s.p['build']['memory']['dos_storage']['BASE'],128).hex()
                observed[-1]['sio']=s.b.memdump(s.p['labels']['SIO_STATE'],128).hex()
                observed[-1]['timer']=s.b.memdump(s.p['build']['task_storage']['BASE']+0xf30,20).hex()
                break
            if name in listing:
                click(80,108+listing.index(name)*12);return
            click(204,88);s.frames(100)
        import json
        (s.p['output']/'browser-navigation-failure.json').write_text(json.dumps(observed,indent=2)+'\n')
        raise RuntimeError('Missing browser row '+name)
    s.rendezvous('dw($%x)=1'%(base+8));s.frames(180)
    require(string(178)=='SYS:','Browser initial directory')
    click(24,64);s.frames(80)
    s.cells('browser-front');s.save_screen(s.p['output']/'browser.png')
    initial=names();require('C' in initial,'Directory entries did not come from SYS')
    require(num(2028+6*24+10)==8 and num(2028+8*24+10)==8,'Initial menu availability')
    click(24,8);move(632,232);s.cells('files-menu-disabled');s.menus.key('ESC')
    row('C');bar(6,True);require(string(178)=='SYS:C','Menu Open directory')
    row('HELLO')
    old=num(1972,4);bar(6)
    s.rendezvous('dw($%x)=0'%(base+1980));s.frames(100)
    require(num(1972,4)==old+1 and num(1984,4)==0,'HELLO launch/collection')
    print('Browser native HELLO launch pass',flush=True)
    # A resource-loaded popup handles keyboard cancel and selection.
    key('F');key('ESC');require(num(8)==1,'Popup Escape closed browser')
    key('F');key('TAB');key('RETURN');s.frames(100)
    require(num(1966)==65535,'Popup Refresh did not reset selection')
    # Browser stays responsive while a command runs; close requests a break
    # and collects it before the browser Task can retire.
    row('TICK');old=num(1972,4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(base+1972,old+1));s.frames(50)
    require(num(1972,4)==old+1 and num(1980,4)!=0,'TICK did not start')
    s.saved['desktop_peak_tasks']=s.ledger()['live']
    require(s.saved['desktop_peak_tasks']==8,'Launch did not use all eight Tasks')
    require(num(2028+6*24+10)==8 and num(2028+8*24+10)==0,'Live-child menu availability')
    bar(8,True)
    s.rendezvous('dw($%x)=0'%(base+1980));s.frames(100)
    require(num(1984,4)!=0 or num(1988,4)==304,'Stopped command result')
    print('Browser menu Stop/collection pass',flush=True)
    click(120,88);require(string(178)=='SYS:','Parent directory')
    row('STORY.TXT');old=num(1972,4);key('RETURN')
    require(num(1972,4)==old and not num(1980,4),'Text file accepted as executable')
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
    click(24,64);row('C');key('RETURN');row('PANEL.APP');key('RETURN')
    s.rendezvous('(dw($%x)!=0)|(dw($%x)=$6143)'%(base+1980,base+1386))
    child=num(1980,4);require(child!=0,'Files did not launch a GEM app')
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
    click(24,64);bar(8)
    s.rendezvous('dw($%x)=0'%(base+1980));s.frames(100)
    require(num(1984,4)==0,'GUI Stop did not return cleanly')
    print('Browser GEM launch/input/Stop pass',flush=True)
    # Close during a popup with a live child: defer WM_CLOSED, then BREAK/wait
    # before releasing the owning application. One launch slot remains.
    click(24,64);row('TICK')
    old=num(1972,4);key('RETURN')
    s.rendezvous('dw($%x)=%d'%(base+1972,old+1));key('F')
    menu=num(174,4)
    require(s.number(menu+18,2)!=0,'Popup did not enter its wait')
    s.saved['browser_stacks']=stack_usage(b,s.p['build']['memory'])
    click(250,64)
    s.rendezvous('dw($%x)=2'%sy['GEMDesktopDone']);s.frames(100)
    require(s.number(sy['GEMDesktopChildren']+8,4)==0,'Idle owner retained Files image')
    require(s.number(sy['GEMDesktopFailure'],2)==0,'Browser teardown failed')
    s.saved['browser']=dict(application_menu=True,menu_keyboard=True,menu_open=True,menu_stop=True,menu_disabled=True,resource=True,navigation=True,popup_keyboard=True,popup_mouse=True,
        launch='HELLO',cancel='TICK',gem_launch='PANEL.APP',gem_stop=True,
        idle_collection=True,invalid_executable=True,close_during_popup_with_child=True,
        popup_stacks=popup_stacks)
