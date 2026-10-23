"""Private application VDI, independent full-screen pixels and virtual-open preservation."""
from pathlib import Path
from native_program import require,sha256
from os_boundary import run_to
from desktop_mouse import schedule
from gem_render_oracle import Raster,font_bytes
from test_desktop_presentation import rectangle,frame,desktop,text,menu_bar,shell_tabs
from test_gem_cursor import overlay
from gem_render_oracle import DESKTOP_PALETTE
from test_gem_interactive import pixels
import adapter_state as adapter


def extract_with_preemption(folder):
    from extract_gem_vdi import extract
    record=extract(folder)
    path=folder/'src/hosted-dispatch.inc'; source=path.read_text()
    needle='    vwk.h_align=vwk.v_align=vwk.text_effects=0;'
    require(source.count(needle)==1,'Private workstation selection boundary changed')
    source='extern void VDIYield(void);\nextern void VDITextYield(void);\n'+source.replace(needle,needle+'\n    VDIYield();')
    fast='        vbxe_text_run(middle,u->top,text,count,u->textColor,0);'
    require(source.count(fast)==1,'VDI text upload boundary changed')
    source=source.replace(fast,'        VDITextYield();\n'+fast)
    path.write_text(source)
    device=folder/'src/vdi/dev_vbxe.c'; device_source=device.read_text()
    glyph='void dev_glyph(WORD ch, WORD cx, WORD cy, WORD overlay)\n{'
    require(device_source.count(glyph)==1,'Device glyph boundary changed')
    device.write_text('extern void VDIGlyphProbe(void);\n'+device_source.replace(glyph,glyph+'\n    VDIGlyphProbe();'))
    record['fixture_override']=dict(reason='Yield after private workstation selection and fast text scratch packing',vdi_sha256=sha256(path),device_sha256=sha256(device))
    return record


def expected(font, covered=False):
    r=Raster(font);desktop(r)
    frame(r,(32,29,560,218),b'Shell',False)
    shell_tabs(r,(32,29,560,218))
    long_text=bytes(65+i%26 for i in range(192))
    for who,(x,y) in enumerate(((32,17),(32,17) if covered else (200,65))):
        frame(r,(x,y,x+400,y+140),b'VDI B' if who else b'VDI A',bool(who),close=True)
        l,t,right,bottom=x+8,y+11,x+392,y+138
        r.clip=(l,t,right-1,bottom-1)
        r.fill=2 if who else 4;r.apply(11,(-300,-300,1000,1000))
        r.clip=(l+8,t+12,l+78,t+14);r.fill=3;r.apply(11,(-300,-300,1000,1000))
        r.text=6 if who else 1;r.apply(8,(l+4,t+15),b'ABCDEFGHIJKLMN')
        r.clip=(l,t,right-1,bottom-1)
        r.apply(8,(l-140*8,t+30),long_text)
        r.apply(8,(l,t+46),bytes(48+i%10 for i in range(80)))
        bank_text=bytes(65+i%26 if i%4<2 else 32 for i in range(80))
        r.apply(8,(l+1,t+62),bank_text)
        r.apply(8,(l+1,t+78),bank_text)
        r.text=0;r.apply(8,(l+(0 if who else 1),t+94),b'012345678901234567890123456789012345678' if who else b'Zero ink       ')
        r.apply(8,(l,t+110),bytes((255,32,65)))
        r.fill=5
        for i in range(4):
            left=l+120+i*16+(i==1);right=left+(0 if i<2 else 7)
            top=t+113;bottom=t+(113 if i<2 else 115)
            r.clip=(l,t,x+391,y+137)
            if i==3:r.clip=(left+1,t+114,right+8,t+115)
            r.apply(11,(left,top,right,bottom))
            r.apply(11,(left+8,top,right+8,bottom))
        r.clip=(0,0,639,239)
    menu_bar(r,b'VDI B')
    return r


def clipped_scene(font):
    r=expected(font);l,t=208,76
    r.clip=(l,t,l+383,t+126)
    for pen in range(16):
        r.fill=pen;r.apply(11,(l+pen*24,t,l+pen*24+23,t+126))
    cases=((10,13,106),(11,11,104),(10,13,103),(11,14,104),
           (10,26,82),(11,14,15),(10,16,20),(10,112,120),
           (11,14,104),(-5,13,103),(10,13,103),(11,14,104))
    bank_text=bytes(65+i%26 if i%4<2 else 32 for i in range(80))
    for i,(x,left,right) in enumerate(cases):
        r.clip=(l+left,t+i*9+(2 if i==8 else 0),l+right-1,t+i*9+(5 if i==8 else 7))
        r.text=0 if i>=10 else 6
        r.apply(8,(-5 if i==9 else l+x,t+i*9+6),bank_text if i==9 else b'A W09 BC DEF')
    r.clip=(0,0,639,239)
    return r


def mode_scene(font):
    r=clipped_scene(font)
    def ink(x,y,value):
        for i,ch in enumerate(value):
            for yy in range(8):
                for xx in range(8):
                    if font[yy*256+ch]&(128>>xx):r.pixel(x+i*8+xx,y-6+yy,r.text)
    original=r.pixel
    for who,(l,t) in enumerate(((40,28),(208,76))):
        r.pixel=lambda x,y,pen: original(x,y,pen) if who or not (200<=x<600 and 65<=y<205) else None
        r.clip=(l,t,l+383,t+126);r.fill=5;r.apply(11,(l,t,l+383,t+44))
        r.text=0;ink(l+1,t+6,b'A W09 BC')
        r.clip=(l+14,t+11,l+103,t+14);r.text=6;ink(l+11,t+15,b'A W09 BC DEF')
        r.clip=(l,t,l+383,t+126);ink(l+3,t+24,b'still transparent')
        r.apply(8,(l+1,t+33),b'replace paper')
        r.fill=4;r.apply(11,(l,t+36,l+31,t+39));r.apply(11,(l+32,t+36,l+63,t+39))
        r.fill=3;r.apply(11,(l,t+48,l+127,t+55));r.text=1
        if who:ink(l+1,t+54,b'Own mode')
        else:r.apply(8,(l+1,t+54),b'Own mode')
    r.pixel=original
    return r


def physical(b,p,foreign,report):
    sy=foreign['symbols'];out=p['output'].parent
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        original=b.regs
        def regs():
            value=original()
            if int(value['PC'].lstrip('$'),16)==p['labels']['done']:
                require(b.peek16(adapter.STATE)==65535,'VDI guest stopped: '+hex(b.peek16(adapter.STATE)))
            return value
        b.regs=regs
        try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        finally:b.regs=original
    def phase(n):reach('dw($%x)=%d'%(sy['VDIPhase'],n))
    def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    def scan(name):
        path=out/(name+'.bgra');screen=b.rawscreen(str(path));raw=path.read_bytes()
        return b''.join(raw[y*screen.stride+64:y*screen.stride+2624] for y in range(240))
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    phase(1);frames(120)
    position=schedule(b,p,[320,120],(620,232));frames(80)
    before=scan('before-virtual')
    b.poke16(sy['VDIGo'],1);phase(2);frames(80)
    require(before==scan('after-virtual'),'Virtual open changed physical pixels')
    position=schedule(b,p,position,(70,57));frames(20)
    b.poke16(sy['VDIGo'],2);phase(3);frames(160)
    model=expected(font_bytes(out/'selected/src/vdi/font8x8.c'))
    report['vdi_pixels']=pixels(b,out,overlay(model,position),palette=DESKTOP_PALETTE)
    report['virtual_open_pixels']='unchanged'
    report['fast_text_units']=[int.from_bytes(b.memdump(sy['VDITextUnits']+i*2,2),'little') for i in range(2)]
    require(all(report['fast_text_units']),'Both clients must use the accelerated text path')
    report['backend_units']=[int.from_bytes(b.memdump(sy['VDIUnits']+i*2,2),'little') for i in range(2)]
    position=schedule(b,p,position,(620,232));frames(80)
    report['cursor_restored_pixels']=pixels(b,out,overlay(model,position),palette=DESKTOP_PALETTE)
    b.poke16(sy['VDIGo'],3);phase(4);frames(120)
    report['covered_pixels']=pixels(b,out,overlay(expected(model.font,True),position),palette=DESKTOP_PALETTE)
    b.poke16(sy['VDIGo'],4);phase(5);frames(120)
    report['exposed_pixels']=pixels(b,out,overlay(model,position),palette=DESKTOP_PALETTE)
    position=schedule(b,p,position,(235,100));frames(40)
    b.poke16(sy['VDIGo'],5);phase(6);frames(80)
    model=clipped_scene(model.font)
    report['clip_native_runs']=[b.peek16(sy['VDIClipNative']+i*2) for i in range(12)]
    report['clip_device_glyphs']=[b.peek16(sy['VDIClipGlyphs']+i*2) for i in range(12)]
    report['clip_pixels']=pixels(b,out,overlay(model,position),palette=DESKTOP_PALETTE)
    position=schedule(b,p,position,(620,232));frames(80)
    report['clip_cursor_restored_pixels']=pixels(b,out,overlay(model,position),palette=DESKTOP_PALETTE)
    b.poke16(sy['VDIGo'],6);phase(7);frames(40)
    report['mode_pixels']=pixels(b,out,overlay(mode_scene(model.font),position),palette=DESKTOP_PALETTE)
    b.poke16(sy['VDIGo'],7);b.bp_clear_all()
