"""Fixture-only menu selection entry, absent from production link roots."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    source = '''MODULE AESMENUPROBE
USE EXEC
USE AESSTATE
USE AESTYPES
USE AESGUI
USE AESLOCKS
USE AESMENU
USE DESKMENU
USE DESKAPPMENU

PUBLIC PROC Pump()
  BYTE accepted

  LET command=CARD POINTER($COMMAND)
  IF command^=0 OR AESLOCKS.NativeReady()=0 THEN
    RETURN
  FI
  LET identity=LONGCARD POINTER($CLIENT)
  LET service=AESSTATE.Get()
  LET client=AESSTATE.Find(service,identity^)
  accepted=0
  IF command^=1 THEN
    accepted=AESGUI.Select(service,client,3,6,5)
  ELSEIF command^=3 THEN
    IF DESKAPPMENU.Current()=0 THEN RETURN FI
    DESKMENU.Application(0)
  ELSEIF command^=2 THEN
    AESGUI.Post(service,client,AESTYPES.GUI_CLOSED,0,0,0,0)
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
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Menu producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESMENUPROBE.Pump()\n'+needle))


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
    from test_desktop_presentation import rectangle,text
    from application_menu_oracle import draw
    import adapter_state as adapter
    sy=foreign['symbols'];out=p['output'].parent
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
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
        model=Raster(font);rectangle(model,(0,0,640,16),0)
        tree=int.from_bytes(b.memdump(sy['AESMenuPeerTree' if phase in (5,6) else 'AESMenuTree'],4),'little')
        if phase not in (4,7):draw(b,model,tree,opened=phase in (2,3,6))
        text(model,440,4,b'Windows');rectangle(model,(0,15,640,16),1)
        areas=[(0,0,640,16)]
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
            print('Public menu pointer/keyboard checks',flush=True)
            click(24,8);click(32,24);actions(0,1,6)
            key('ESC',ctrl=True,shift=True);key('ASTERISK',ctrl=True)
            require(get(at('DESKAPPMENU','heading'))==1,'Right did not switch application title')
            key('ASTERISK',ctrl=True);require(get(at('DESKAPPMENU','heading'))==0,'Title navigation did not wrap')
            key('TAB');key('TAB');key('RETURN');actions(0,2,7)
            click(24,8);click(600,220);actions(0,2)
            click(24,8);move(32,24);edge(1);key('ESC');edge(0);actions(0,2)
            move(24,8);edge(1);move(32,24);edge(0);actions(0,3,6)
            click(24,8);move(472,8);frames()
            require(get(at('DESKMENU','menu'),1)==2,'Heading switch to Windows failed')
            # The native popup uses the same monochrome conventions. Rebuild
            # it from retained windows, then compare only its opaque bounds.
            from desktop_oracle import compose
            from bitmap_console_oracle import Terminal
            packed=compose(b,p,font,Terminal(64,20),pointer=position,
                           external=lambda raster,title,bounds:None,
                           menu_contexts=sy['contexts'])
            bottom=16+max(4,get(at('DESKMENU','count'),1))*16
            path=out/'native-menu.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
            for yy in range(16,bottom):
                for xx in range(432,640):
                    byte=packed[yy*320+xx//2];pen=byte&15 if xx&1 else byte>>4
                    pixel=yy*capture.stride+64+xx*4
                    require(pixels[pixel:pixel+3]==hardware[pen],f'Native menu pixel {xx},{yy}')
            for xx,yy in [(432,24),(639,24),(472,16),(472,bottom-1)]:
                move(xx,yy);frames()
                require(get(at('DESKMENU','selected'))==65535,'Popup border selected an item')
            report['native_popup']=dict(pixels='exact',border_hits='excluded')
            move(24,8);frames();click(32,40);actions(0,4,7)
            click(24,8);move(32,24);edge(1);mutation(1);edge(0);actions(0,4)
            key('ESC');mutation(2)
            click(24,8);move(32,24);edge(1);mutation(3);edge(0);actions(0,4)
            mutation(4);key('ESC',ctrl=True,shift=True);key('TAB');key('RETURN');actions(0,4)
            key('ESC');mutation(5)
            actions(1,0)
        elif phase==3:
            click(32,24);actions(0,4)
            key('ESC',ctrl=True,shift=True);key('TAB');key('RETURN');actions(0,5,7)
        elif phase==5:
            click(168,8);click(176,24);actions(1,1,6);actions(0,5)
            key('ESC',ctrl=True,shift=True);key('TAB');key('TAB');key('TAB');key('RETURN');actions(1,2,6)
        b.poke16(sy['AESMenuGo'],phase)
    report['physical_menus']=dict(pointer=True,keyboard=True,commands=[5,2],identical_titles=True,disabled=True,held_replacement=True,held_disable=True,cancel=True,heading_switch=True,hidden=True,multiple_titles=True)
    b.bp_clear_all()
