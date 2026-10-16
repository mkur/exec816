"""Fixture-only menu selection entry, absent from production link roots."""
from library_paths import read_source
from native_program import ROOT, require


def instrument(out):
    source=read_source(ROOT/'ports/gem4xe/adapter/gem-vbxe.c')
    source=source.replace('static UWORD draw_InvertRows(',
        'volatile ULONG MenuInvertCalls;\nstatic UWORD draw_InvertRows(')
    source=source.replace('    const WORD *r;\n',
        '    const WORD *r;\n    ++MenuInvertCalls;\n')
    path=out/'gem-vbxe.c';path.write_text(source)
    return path


def producer(out, symbols):
    # Fixed fixture hook; production has no injected input or pause state.
    probe=read_source(ROOT/'tests/programs/menutransitionprobe.act',
        {'input-storage.act.inc':out/'program/input-storage.act.inc'})
    (out/'menutransitionprobe.act').write_text(probe)
    (out/'menutitleprobe.act').write_text(read_source(ROOT/'tests/programs/menutitleprobe.act'))
    (out/'menutitlemarks.act').write_text('MODULE MENUTITLEMARKS\nPUBLIC BYTE fail\nENDMODULE\n')
    paint=read_source(ROOT/'lib/desktop/deskmenupaint.act').replace(
        'USE DESKMENU\n','USE DESKMENU\nUSE MENUTITLEMARKS\n',1)
    rule='    REGIONS.Assign(@bounds,0,DESKMENU.BAR_HEIGHT-1,640,DESKMENU.BAR_HEIGHT)'
    require(paint.count(rule)==1,'Title rule failure boundary changed')
    paint=paint.replace(rule,'    IF MENUTITLEMARKS.fail<>0 THEN\n'
        '      MENUTITLEMARKS.fail=0\n      RETURN(0)\n    FI\n'+rule)
    (out/'deskmenupaint.act').write_text(paint)
    (out/'menutransitionmarks.act').write_text('MODULE MENUTRANSITIONMARKS\nPUBLIC BYTE watch,ordinary,passed\nPUBLIC CARD waits\nENDMODULE\n')
    state=read_source(ROOT/'lib/desktop/deskstate.act').replace('USE EXEC',
        'USE EXEC\nUSE MENUTRANSITIONMARKS',1)
    state=state.replace('  IF ordinary<>0 THEN\n    menuTurns=0',
        '  IF ordinary<>0 THEN\n    IF MENUTRANSITIONMARKS.watch<>0 THEN\n      MENUTRANSITIONMARKS.ordinary==+1\n    FI\n    menuTurns=0')
    (out/'deskstate.act').write_text(state)
    cache=read_source(ROOT/'lib/desktop/deskmenucache.act').replace(
        'USE DESKSTATE', 'USE MENUTRANSITIONPROBE\nUSE DESKSTATE', 1)
    cache=cache.replace('  status=Transfer(1)\n',
        '  status=Transfer(1)\n  MENUTRANSITIONPROBE.Copy(1)\n')
    cache=cache.replace('  status=PopupTransfer(@service.scene.copyTarget,1)\n',
        '  status=PopupTransfer(@service.scene.copyTarget,1)\n  MENUTRANSITIONPROBE.Copy(2)\n')
    cache=cache.replace('  status=LAYERS.FinishSavedReplace',
        '  MENUTRANSITIONPROBE.BeforeFinish(0)\n  status=LAYERS.FinishSavedReplace')
    (out/'deskmenucache.act').write_text(cache)
    source = '''MODULE AESMENUPROBE
USE EXEC
USE AESSTATE
USE AESTYPES
USE AESGUI
USE AESLOCKS
USE AESMENU
USE DESKSTATE
USE LAYERS
USE LAYERTYPES
USE REGIONS
USE MENUTRANSITIONMARKS
USE DESKMENU
USE DESKAPPMENU
USE MENUTITLEPROBE

PUBLIC BYTE FUNC Pending()

  LET command=CARD POINTER($COMMAND)

RETURN(command^<>0)

PUBLIC PROC Pump()
  BYTE accepted,slot
  LAYERTYPES.Rect area

  LET command=CARD POINTER($COMMAND)
  IF command^=0 OR AESLOCKS.NativeReady()=0 THEN
    RETURN
  FI
  LET identity=LONGCARD POINTER($CLIENT)
  LET service=AESSTATE.Get()
  LET client=AESSTATE.Find(service,identity^)
  IF command^>=5 THEN
    BEGIN
      LET result=CARD POINTER($RESULT)
      result^=MENUTITLEPROBE.Run(command^)
      command^=0
      RETURN
    END
  FI
  accepted=0
  IF command^=1 THEN
    accepted=AESGUI.Select(service,client,3,6,5)
  ELSEIF command^=3 THEN
    IF DESKAPPMENU.Current()=0 THEN RETURN FI
    DESKMENU.Application(0)
  ELSEIF command^=4 THEN
    BEGIN
      LET desktop=DESKSTATE.Get()
      REGIONS.Assign(@area,620,200,624,204)
      accepted=LAYERS.Invalidate(@desktop.scene,0,@area)
      DESKSTATE.MenuTurn(0)
      DESKSTATE.MenuTurn(0)
      MENUTRANSITIONMARKS.watch=1
      MENUTRANSITIONMARKS.ordinary=0
      MENUTRANSITIONMARKS.passed=0
      DESKMENU.Application(1)
      command^=0
      RETURN
    END
  ELSEIF command^=2 THEN
    FOR slot=0 TO AESTYPES.WINDOWS-1 DO
      IF service.windows(slot).owner=client.id THEN
        AESGUI.Post(service,@service.windows(slot),AESTYPES.GUI_CLOSED,0,0,0,0)
        EXIT
      FI
    OD
  FI
  LET result=CARD POINTER($RESULT)
  result^=CARD(accepted)
  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,LONGCARD(1) LSH client.endpoint.port.mp_SigBit)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for key, symbol in (('COMMAND', 'AESMenuCommand'), ('CLIENT', 'AESMenuClient'),
                        ('RESULT', 'AESMenuResult')):
        source = source.replace('$'+key, f'${symbols[symbol]:x}')
    (out/'aesmenuprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE',
        'USE AESCORE\nUSE AESMENUPROBE')
    host=host.replace('PUBLIC BYTE FUNC Settled()\n',
        'PUBLIC BYTE FUNC Settled()\n\n  IF AESMENUPROBE.Pending()<>0 THEN RETURN(0) FI\n')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Menu producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESMENUPROBE.Pump()\n'+needle))


def worker_probe(original):
    def generate(*args, **kwargs):
        directory=original(*args, **kwargs)
        path=directory/'consoledriver.act'
        source=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE MENUTRANSITIONMARKS\n',1)
        old='      bits=EXEC.Wait($e0000000 OR displayMask OR desktopMask)'
        require(source.count(old)==1,'Presenter wait boundary changed')
        source=source.replace(old, '      IF inputPending<>0 AND DESKSTATE.menuReplacing<>0 THEN\n'
            '        MENUTRANSITIONMARKS.waits==+1\n      FI\n'+old)
        path.write_text(source)
        return directory
    return generate


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from gem_render_oracle import Raster,font_bytes,PENS,DESKTOP_PALETTE as PALETTE
    from test_desktop_presentation import rectangle,text
    from application_menu_oracle import draw
    import adapter_state as adapter
    sy=foreign['symbols'];out=p['output'].parent
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        try:
            run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        except Exception:
            report['stalled_condition']=condition
            report['menu_state']={module:{n:get(at(module,n),size) for n,size in names} for module,names in (
                ('DESKSTATE',[('menuReplacing',1),('menuActive',1),('menuTurns',1)]),
                ('DESKMENU',[('menu',1),('pendingMenu',1),('pendingHeading',2),('dirty',1)]),
                ('DESKMENUCACHE',[('token',4),('popupOperation',1)]))}
            from generate_desktop import layout as dl
            from generate_layers import layout as ll
            scene=get(at('DESKSTATE','service'),3)+dl()['Service']['fields']['scene']
            report['scene_state']={n:get(scene+ll()['Scene']['fields'][n],size) for n,size in
                [('busy',4),('activeKind',1),('visibleDamage',2)]}
            print(report['menu_state'],report['scene_state'],flush=True)
            raise
    font=font_bytes(out/'selected/src/vdi/font8x8.c')
    rgb=bytes((v&254)+(v>>7) for v in PALETTE);hardware=[None]*16
    for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
    from desktop_mouse import schedule
    at=lambda mod,n: next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
    def frames(n=75):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    position=[320,120]
    def move(x,y):
        nonlocal position
        position=schedule(b,p,position,(x,y))
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
    def edge(down):
        b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(25)
    def click(x,y):move(x,y);edge(1);edge(0);frames()
    def key(name,ctrl=False,shift=False):
        if ctrl:b._cmd_ok('KEY CTRL down')
        if shift:b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
        if shift:b._cmd_ok('KEY SHIFT up')
        if ctrl:b._cmd_ok('KEY CTRL up')
        frames()
    def mutation(value):
        b.poke16(sy['AESMenuMutation'],value)
        reach('dw($%x)=0'%sy['AESMenuMutation']);frames()
    def actions(who,count,item=None):
        frames()
        require(get(sy['AESMenuActions']+who*2)==count,'Physical command count/recipient mismatch: '+str((who,count,get(sy['AESMenuActions']+who*2))))
        if item is not None:require(get(sy['AESMenuItem']+who*2)==item,'Wrong menu item')
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    report['menu_pixels']=[]
    for phase in range(1,8):
        print('Menu pixels phase',phase,flush=True)
        reach('dw($%x)=%d'%(sy['AESMenuPhase'],phase))
        move(632,232)
        reach('@frame>=%d'%(b.eval_expr('@frame')+80))
        model=Raster(font);rectangle(model,(0,0,640,11),0)
        tree=int.from_bytes(b.memdump(sy['AESMenuPeerTree' if phase in (5,6) else 'AESMenuTree'],4),'little')
        if phase not in (4,7):draw(b,model,tree,opened=phase in (2,3,6))
        text(model,8,1,b'Exec816');text(model,568,1,b'Windows');rectangle(model,(0,10,640,11),1)
        areas=[(0,0,640,11)]
        if phase in (2,3,6):
            areas.append(draw(b,model,tree,True))
        path=out/('menu-%d.bgra'%phase);frame=b.rawscreen(str(path));raw=path.read_bytes()
        for left,top,right,bottom in areas:
            for y in range(top,bottom):
                for x in range(left,right):
                    pixel=y*frame.stride+(x+16)*4
                    require(raw[pixel:pixel+3]==hardware[model.pixels[y*640+x]],
                            'Menu pixels phase %d at %d,%d: %s != %s'%(phase,x,y,
                                raw[pixel:pixel+3].hex(),hardware[model.pixels[y*640+x]].hex()))
        report['menu_pixels'].append(dict(phase=phase,pixels=sum((r-l)*(bt-t) for l,t,r,bt in areas)))
        if phase==1:
            def title_pixels():
                expected=Raster(font);rectangle(expected,(0,0,640,11),0)
                draw(b,expected,tree)
                text(expected,8,1,b'Exec816');text(expected,568,1,b'Windows')
                rectangle(expected,(0,10,640,11),1)
                path=out/'title-paint.bgra';f=b.rawscreen(str(path));raw=path.read_bytes()
                for yy in range(11):
                    for xx in range(640):
                        pixel=yy*f.stride+(xx+16)*4
                        require(raw[pixel:pixel+3]==hardware[expected.pixels[yy*640+xx]],
                                f'Title damage pixel {xx},{yy}')
            def title_case(command,want):
                b.poke16(sy['AESMenuCommand'],command)
                move(630 if position[0]==632 else 632,232)
                reach('dw($%x)=0'%sy['AESMenuCommand']);frames()
                require(get(sy['AESMenuResult'])==want,'Title paint steps: '+str(command))
                title_pixels()
                return dict(command=command,paint_calls=want,pixels='exact')
            report['title_paint']=[title_case(c,n) for c,n in
                ((5,1),(6,1),(7,1),(8,3),(9,2),(10,1))]
            mutation(8)
            report['title_paint'].append(title_case(11,4))
            mutation(9);title_pixels()
            print('Public menu pointer/keyboard checks',flush=True)
            click(56,8)
            require(get(at('DESKMENU','menu'),1)==1,'Focused-window menu did not open')
            key('ESC');actions(0,0)
            # The normal File image survives a close/reopen. Exact owner,
            # lifetime, source revision and selection must all match.
            click(152,8);move(632,232);frames()
            key('ESC')
            restores=get(at('DESKMENUCACHE','popupRestores'),4)
            click(152,8);move(632,232);frames()
            require(get(at('DESKMENUCACHE','popupRestores'),4)==restores+1,
                    'Repeated File opening missed its rendered popup')
            cached=Raster(font);area=draw(b,cached,tree,True)
            path=out/'cached-menu.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
            for yy in range(area[1],area[3]):
                for xx in range(area[0],area[2]):
                    pixel=yy*capture.stride+(xx+16)*4
                    require(pixels[pixel:pixel+3]==hardware[cached.pixels[yy*640+xx]],
                            f'Cached File menu pixel {xx},{yy}')
            report['popup_cache']=dict(warm_file='exact',restore_delta=1)
            b.poke16(sy['AESMenuCommand'],4)
            move(630,232)  # A real capture wake admits the fixture command.
            reach('db($%x)=1'%at('MENUTRANSITIONMARKS','passed'));frames()
            require(get(at('MENUTRANSITIONMARKS','ordinary'),1)>0,
                    'Third preferred transaction bypassed ready ordinary paint')
            report['replacement_fairness']='ordinary paint before next combined replacement'
            key('ASTERISK',ctrl=True)
            # Both real copy submissions publish into the existing queues.
            # No new key/signal is sent after injection to rescue a lost hint.
            report['replacement_input']=[]
            for stage,kind in ((1,1),(2,1),(1,2),(2,2),(1,3),(2,3),(1,4),(2,4)):
                print('Replacement input',stage,kind,flush=True)
                # Warm both slots, leaving File open with no selected row.
                key('ASTERISK',ctrl=True);key('ASTERISK',ctrl=True)
                frames()
                base=get(at('MENUTRANSITIONPROBE','hits'),1)
                deferred=get(at('MENUTRANSITIONPROBE','deferred'),1)
                focus=get(at('DESKMENU','activeWindow'),4)
                b.poke(at('MENUTRANSITIONPROBE','kind'),kind)
                b.poke(at('MENUTRANSITIONPROBE','arm'),stage)
                key('ASTERISK',ctrl=True)
                reach('db($%x)=0'%at('DESKMENU','menu'));frames()
                require(get(at('MENUTRANSITIONPROBE','hits'),1)==base+1,
                        f'Replacement copy stage {stage} was not reached')
                require(get(at('MENUTRANSITIONPROBE','deferred'),1)>deferred,
                        'Queued replacement input was consumed before retirement')
                require(get(at('DESKMENU','activeWindow'),4)==focus,'Deferred click reached a window')
                actions(0,0)
                report['replacement_input'].append(dict(stage=stage,kind=kind,closed=True))
                click(152,8);move(632,232);frames()
            require(get(at('MENUTRANSITIONMARKS','waits'))>0,
                    'Deferred input kept the presenter runnable instead of waiting for completion')
            report['replacement_completion_waits']=get(at('MENUTRANSITIONMARKS','waits'))
            # Completed selection pixels, including both odd packed edges.
            inversions=get(sy['MenuInvertCalls'],4)
            for xx,yy,item,expected in [(160,16,6,1),(160,27,7,2),
                    (160,16,6,3),(160,16,6,3),(632,232,-1,4)]:
                move(xx,yy);frames()
                require(get(sy['MenuInvertCalls'],4)==inversions+expected,
                        'Selection did not use exactly one inversion per change')
                selected=Raster(font);area=draw(b,selected,tree,True,selected=item)
                path=out/'selection.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
                for yy2 in range(area[1],area[3]):
                    for xx2 in range(area[0],area[2]):
                        # Pointer is a separate overlay, covered by ordinary pointer tests.
                        if xx<=xx2<xx+20 and yy<=yy2<yy+20:continue
                        pixel=yy2*capture.stride+(xx2+16)*4
                        require(pixels[pixel:pixel+3]==hardware[selected.pixels[yy2*640+xx2]],
                                f'Selection pixel {item}: {xx2},{yy2}')
            report['selection_inversion']=dict(changes=4,repeated='no-op',pixels='exact',
                odd_edges=True,entry_exit=True)
            key('ESC')
            click(152,8);click(160,16);actions(0,1,6)
            key('ESC',ctrl=True,shift=True);key('ASTERISK',ctrl=True)
            require(get(at('DESKAPPMENU','heading'))==1,'Right did not switch application title')
            key('ASTERISK',ctrl=True);require(get(at('DESKAPPMENU','heading'))==0,'Title navigation did not wrap')
            key('TAB');key('TAB');key('RETURN');actions(0,2,7)
            click(152,8);click(600,220);actions(0,2)
            click(152,8);move(160,16);edge(1);key('ESC');edge(0);actions(0,2)
            move(152,8);edge(1);move(160,16);edge(0);actions(0,3,6)
            click(152,8);move(600,8);frames()
            require(get(at('DESKMENU','menu'),1)==2,'Heading switch to Windows failed')
            # The native popup uses the same monochrome conventions. Rebuild
            # it from retained windows, then compare only its opaque bounds.
            from desktop_oracle import compose
            from bitmap_console_oracle import Terminal
            bottom=11+max(4,get(at('DESKMENU','count'),1))*11
            def native_pixels():
                # A heading crossing may enqueue several paints. Observe the
                # settled chrome, rather than assuming a fixed frame delay.
                from generate_desktop import layout as desk_layout
                from generate_layers import layout as layer_layout
                service=get(at('DESKSTATE','service'),3)
                scene=service+desk_layout()['Service']['fields']['scene']
                layer=layer_layout()['Layer'];items=scene+layer_layout()['Scene']['fields']['items']
                chrome=[get(at('DESKSTATE',name),4) for name in ('barLayer','popupLayer')]
                for _ in range(300):
                    dirty=any(get(items+i*layer['size'],4) in chrome and
                        get(items+i*layer['size']+layer['fields']['dirty'],1) for i in range(9))
                    painting=get(at('DESKPAINT','paintToken'),4) and get(at('DESKPAINT','paintLayer'),4) in chrome
                    if not dirty and not painting:break
                    frames(2)
                else:raise RuntimeError('Menu chrome did not finish')
                packed=compose(b,p,font,Terminal(64,20),pointer=position,
                               external=lambda raster,title,bounds:None,
                               menu_contexts=sy['contexts'])
                path=out/'native-menu.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
                for yy in range(bottom):
                    for xx in range(432,640):
                        byte=packed[yy*320+xx//2];pen=byte&15 if xx&1 else byte>>4
                        pixel=yy*capture.stride+64+xx*4
                        if pixels[pixel:pixel+3]!=hardware[pen]:
                            b.screenshot(str(out/'native-menu-failure.png'))
                            report['native_menu_failure']={n:get(at('DESKMENU',n),1) for n in ('menu','paintMenu','dirty')}
                            report['native_menu_failure']['binding']=b.memdump(p['build']['memory']['console_storage']['BITMAP'],8).hex()
                            report['native_menu_failure']['paint']={n:get(at('DESKPAINT',n),z) for n,z in [('started',1),('paintToken',4),('paintLayer',4),('nextY',2)]}
                            require(False,f'Native menu pixel {xx},{yy}: {pixels[pixel:pixel+3].hex()} != {hardware[pen].hex()}')
            native_pixels()
            for xx,yy in [(472,16),(472,27),(432,16)]:
                move(xx,yy);frames();native_pixels()
            for xx,yy in [(432,16),(639,16),(472,11),(472,bottom-1)]:
                move(xx,yy);frames()
                require(get(at('DESKMENU','selected'))==65535,'Popup border selected an item')
            report['native_popup']=dict(pixels='exact',border_hits='excluded',highlight_transitions=3)
            move(152,8);frames();click(160,27);actions(0,4,7)
            click(152,8);move(160,16);edge(1);mutation(1);edge(0);actions(0,4)
            key('ESC');mutation(2)
            click(152,8);move(160,16);edge(1);mutation(3);edge(0);actions(0,4)
            mutation(4);key('ESC',ctrl=True,shift=True);key('TAB');key('RETURN');actions(0,4)
            key('ESC');mutation(5)
            mutation(6);click(152,8);move(632,232);frames()
            wide=Raster(font)
            area=draw(b,wide,tree,True)
            path=out/'wide-menu.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
            for yy in range(area[1],area[3]):
                for xx in range(area[0],area[2]):
                    pixel=yy*capture.stride+(xx+16)*4
                    require(pixels[pixel:pixel+3]==hardware[wide.pixels[yy*640+xx]],
                            f'Long checked/clipped menu pixel {xx},{yy}')
            report['long_menu']=dict(pixels='exact',odd_x=True,checked=True,disabled=True,
                                     partial_glyph=True,partial_row=True)
            key('ESC');mutation(7)
            actions(1,0)
        elif phase==3:
            click(160,16);actions(0,4)
            key('ESC',ctrl=True,shift=True);key('TAB');key('RETURN');actions(0,5,7)
        elif phase==5:
            click(296,8);click(304,16);actions(1,1,6);actions(0,5)
            key('ESC',ctrl=True,shift=True);key('TAB');key('TAB');key('TAB');key('RETURN');actions(1,2,6)
        b.poke16(sy['AESMenuGo'],phase)
    report['physical_menus']=dict(pointer=True,keyboard=True,commands=[5,2],identical_titles=True,disabled=True,held_replacement=True,held_disable=True,cancel=True,heading_switch=True,hidden=True,multiple_titles=True)
    b.bp_clear_all()
