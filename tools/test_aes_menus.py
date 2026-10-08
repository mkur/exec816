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
    report['menu_pixels']=[]
    for phase in range(1,8):
        print('Menu pixels phase',phase,flush=True)
        reach('dw($%x)=%d'%(sy['AESMenuPhase'],phase))
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
                    at=y*frame.stride+(x+16)*4
                    require(raw[at:at+3]==hardware[model.pixels[y*640+x]],
                            'Menu pixels phase %d at %d,%d: %s != %s'%(phase,x,y,
                                raw[at:at+3].hex(),hardware[model.pixels[y*640+x]].hex()))
        report['menu_pixels'].append(dict(phase=phase,pixels=sum((r-l)*(bt-t) for l,t,r,bt in areas)))
        b.poke16(sy['AESMenuGo'],phase)
    b.bp_clear_all()
