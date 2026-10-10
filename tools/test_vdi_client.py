"""Private application VDI, independent full-screen pixels and virtual-open preservation."""
from pathlib import Path
from native_program import require,sha256
from os_boundary import run_to
from desktop_mouse import schedule
from gem_render_oracle import Raster,font_bytes
from test_desktop_presentation import rectangle,frame,desktop,text
from test_gem_cursor import overlay
from test_gem_interactive import pixels
import adapter_state as adapter


def extract_with_preemption(folder):
    from extract_gem_vdi import extract
    record=extract(folder)
    path=folder/'src/hosted-dispatch.inc'; source=path.read_text()
    needle='    vwk.h_align=vwk.v_align=vwk.text_effects=0;'
    require(source.count(needle)==1,'Private workstation selection boundary changed')
    source='extern void VDIYield(void);\nextern void VDITextYield(void);\n'+source.replace(needle,needle+'\n    VDIYield();')
    fast='        vbxe_text_run(u->x,u->top,text,u->count,u->textColor,0);'
    require(source.count(fast)==1,'VDI text upload boundary changed')
    source=source.replace(fast,'        VDITextYield();\n'+fast)
    path.write_text(source)
    record['fixture_override']=dict(reason='Yield after private workstation selection and fast text scratch packing',vdi_sha256=sha256(path))
    return record


def expected(font, covered=False):
    r=Raster(font);desktop(r)
    frame(r,(32,24,560,208),b'Exec816 Shell',False)
    long_text=bytes(65+i%26 for i in range(192))
    for who,(x,y) in enumerate(((33,17),(33,17) if covered else (201,65))):
        frame(r,(x,y,x+300,y+140),b'VDI B' if who else b'VDI A',bool(who),close=True)
        l,t,right,bottom=x+8,y+16,x+292,y+132
        r.clip=(l,t,right-1,bottom-1)
        r.fill=2 if who else 4;r.apply(11,(-300,-300,1000,1000))
        r.clip=(l+8,t+12,l+78,t+14);r.fill=3;r.apply(11,(-300,-300,1000,1000))
        r.text=6 if who else 1;r.apply(8,(l+4,t+15),b'ABCDEFGHIJKLMN')
        r.clip=(l,t,right-1,bottom-1)
        r.apply(8,(l-140*8,t+30),long_text)
        r.apply(8,(l,t+46),bytes(48+i%10 for i in range(40)))
        bank_text=bytes(65+i%26 if i%4<2 else 32 for i in range(40))
        r.apply(8,(l+1,t+62),bank_text)
        r.apply(8,(l+1,t+78),bank_text)
        r.text=0;r.apply(8,(l+1,t+94),b'Zero ink       ')
        r.clip=(0,0,639,239)
    rectangle(r,(0,0,640,15),0);rectangle(r,(0,15,640,16),1)
    text(r,8,4,b'VDI B');text(r,440,4,b'Windows')
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
    report['vdi_pixels']=pixels(b,out,overlay(model,position))
    report['virtual_open_pixels']='unchanged'
    report['fast_text_units']=[int.from_bytes(b.memdump(sy['VDITextUnits']+i*2,2),'little') for i in range(2)]
    require(all(report['fast_text_units']),'Both clients must use the accelerated text path')
    report['backend_units']=[int.from_bytes(b.memdump(sy['VDIUnits']+i*2,2),'little') for i in range(2)]
    position=schedule(b,p,position,(620,232));frames(80)
    report['cursor_restored_pixels']=pixels(b,out,overlay(model,position))
    b.poke16(sy['VDIGo'],3);phase(4);frames(120)
    report['covered_pixels']=pixels(b,out,overlay(expected(model.font,True),position))
    b.poke16(sy['VDIGo'],4);phase(5);frames(120)
    report['exposed_pixels']=pixels(b,out,overlay(model,position))
    b.poke16(sy['VDIGo'],5);b.bp_clear_all()
