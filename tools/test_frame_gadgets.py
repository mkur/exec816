#!/usr/bin/env python3
"""Small optimized atlas lifetime and independent frame-pixel fixture."""
import argparse
import json
from pathlib import Path
from build_bitmap_console import drawing
from library_paths import read_source
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import PIN, BRIDGE, ROM
from stack_budget import stack_usage
from gem_render_oracle import Raster, font_bytes, DESKTOP_PALETTE
from test_desktop_presentation import frame, tile, rectangle
from test_gem_interactive import pixels
import adapter_state as adapter_state


def expected(font,number):
    if number==9:number=1
    r=Raster(font);rectangle(r,(0,0,640,240),3)
    if number==8:
        rectangle(r,(27,0,43,240),0)
        for distance in (2,4,6):
            for step in range(distance):
                rectangle(r,(39-2*step,240-distance+step,41-2*step,241-distance+step),1)
        return r.packed()
    if number in (6,7):
        frame(r,(20,20,220,200) if number==6 else (21,0,221,240),b'SYS:',True,
              background=3,close=True,kind=4|32|448,slider=(140,18) if number==6 else (22,8))
        return r.packed()
    picture=Raster(font)
    left=21 if number==2 else 20
    if number==5:
        tile(picture,(20,20,108,31),b'SYS:')
        bounds=(20,20,108,31)
    else:
        frame(picture,(left,20,left+200,200),b'Shell' if number==4 else b'SYS:',
              number!=2,close=number!=4,kind=4)
        bounds=(left,20,left+200,31) if number!=3 else (27,21,210,31)
    l,t,right,bottom=bounds
    for y in range(t,bottom):
        r.pixels[y*640+l:y*640+right]=picture.pixels[y*640+l:y*640+right]
    return r.packed()


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    adapter=ROOT/'ports/gem4xe/adapter/gem-vbxe.c'
    source=adapter.read_text()
    needle='latch(VbxeOwnerWrite(&display,GEM_FRAME_GADGET_BASE,GemFramePixels,sizeof(GemFramePixels)));'
    require(source.count(needle)==1,'Atlas upload boundary changed')
    source=source.replace('static UWORD dirty, fault;','static UWORD dirty, fault;\nUWORD FrameAtlasFail;')
    source=source.replace(needle,'{ if (FrameAtlasFail) { FrameAtlasFail=0;latch(DISPLAY_DEVICE_FAULT); } else '+needle+' }')
    source+='''
/* Fixture-only readback and neighboring sentinels; absent from production. */
UWORD FrameAtlasMemory(UWORD initialize)
{
    static UBYTE saved[sizeof(GemFramePixels)];
    UBYTE sentinel[2]={0xa5,0x5a};
    UWORD good=1;
    if (render_enter()!=DISPLAY_OK) return 0;
    if (VbxeOwnerRead(&display,GEM_FRAME_GADGET_BASE,saved,sizeof(saved)) ||
        memcmp(saved,GemFramePixels,sizeof(saved))) good=0;
    if (initialize) {
        if (VbxeOwnerWrite(&display,GEM_FRAME_GADGET_BASE-2,sentinel,2) ||
            VbxeOwnerWrite(&display,GEM_FRAME_GADGET_BASE+4096,sentinel,2)) good=0;
    } else {
        if (VbxeOwnerRead(&display,GEM_FRAME_GADGET_BASE-2,saved,2) ||
            memcmp(saved,sentinel,2)) good=0;
        if (VbxeOwnerRead(&display,GEM_FRAME_GADGET_BASE+4096,saved,2) ||
            memcmp(saved,sentinel,2)) good=0;
    }
    render_exit(DISPLAY_OK);
    return good;
}
UWORD FrameScratchGuard(UWORD initialize)
{
    static UBYTE expected[16],actual[16];
    UWORD status;
    if (render_enter()!=DISPLAY_OK) return 0;
    if (initialize) {
        memset(expected,0xa5,sizeof(expected));
        status=VbxeOwnerWrite(&display,WIDGET_STRIP_BASE+3840,expected,sizeof(expected));
    } else {
        status=VbxeOwnerRead(&display,WIDGET_STRIP_BASE+3840,actual,sizeof(actual));
        if (memcmp(expected,actual,sizeof(expected))) status=DISPLAY_DEVICE_FAULT;
    }
    render_exit(DISPLAY_OK);
    return status==DISPLAY_OK;
}
'''
    backend=out/'gem-vbxe.c';backend.write_text(source)
    f=drawing(out,True,widgets=True,client_sources=[ROOT/'tests/programs/frame_gadgets.c'],
              client_roots=['FrameRun','stage','finished'],renderer_source=backend)
    sy=f['symbols']
    inc=out/'c-image.inc';inc.write_text(f'CONST C_MAIN=${sy["FrameRun"]:x}\n'+''.join(f'CONST C_{n.upper()}=${sy[n]:x}\n' for n in ('stage','ExecDisplayEntries')))
    # No input lease or binding is needed for static frame/readback checks.
    raw=(ROOT/'tests/programs/gem_text_launcher.act').read_text().replace('USE INPUT\n','').replace('  BindInput()\n','').replace('INCLUDE "../../c/calypsi/input-bridge.inc"\n','')
    sourcefile=out/'launcher.act';sourcefile.write_text(raw.replace('INCLUDE "c-image.inc"',inc.read_text()).replace('INCLUDE "../../c/calypsi/display-bridge.inc"',read_source(ROOT/'c/calypsi/display-bridge.inc')))
    p=build(compiler(ROOT/'build/actionc',release=True),sourcefile,out/'program',
            tasks=True,task_capacity=8,console=False,optimize=True,foreign_image=f)
    report=dict(tier='development',status='running',bank_zero_delta=dict(fixed=0,per_task=[0]*8,idle=0),provenance=f['provenance'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def before(b):
                report['pixels']=[]
                font=font_bytes(out/'selected/src/vdi/font8x8.c')
                for number in range(1,10):
                    condition=f'dw(${sy["checkpoint"]:x})={number}'
                    marker=p['labels']['native_nmi']
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter_state.STOPPED)
                    run_to(b,marker,condition=condition,timeout=60,frame_limit=3000)
                    require(not b.peek16(sy['failures']),f'Frame {number}: check {b.peek16(sy["firstFailure"])} status {b.peek16(sy["frameStatus"])}')
                    # Let scanout finish a frame after the synchronous drawing.
                    condition=f'@frame>={b.eval_expr("@frame")+2}'
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    run_to(b,marker,condition=condition,timeout=10,frame_limit=10)
                    folder=out/f'pixels-{number}';folder.mkdir(exist_ok=True)
                    report['pixels'].append(pixels(b,folder,expected(font,number),palette=DESKTOP_PALETTE))
                    b.poke16(sy['gate'],number)
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=4000)
            ownership(b,p,p['output'])
            require(b.peek16(sy['finished'])==1 and not b.peek16(sy['failures']),'Atlas assertion failed')
            report['checks']=b.peek16(sy['checks'])
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'Stack floor')
            report['status']='pass'
    except Exception as e:
        report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Frame atlas passed',report['checks'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
