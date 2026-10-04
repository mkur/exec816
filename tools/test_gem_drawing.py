#!/usr/bin/env python3
"""Shared drawing library and aligned C input records, with no GEM IPC linked."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract,PORT
from generate_input import expected_layout
from library_paths import read_source
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from gem_render_oracle import Raster,font_bytes
from test_gem_interactive import pixels
from test_heap_api import clean_ownership
from stack_budget import stack_usage
import adapter_state as adapter


def run(out,mode):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    extraction=extract(out/'selected');src=out/'selected/src';ad=PORT/'adapter'
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',ROOT/'c/calypsi/input.c',
             ROOT/'platform/altirraos/vbxe.c',src/'vdi/vdi.c',src/'vdi/font.c',
             src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',ad/'gem-vbxe.c',ROOT/'tests/programs/gem_drawing.c']
    admission=(ROOT/'c/calypsi/display.c').read_text().replace(
        'UWORD DisplayCheck(struct DisplayLease *p) {',
        'extern volatile UWORD ownerChecks;\nUWORD DisplayCheck(struct DisplayLease *p) { ++ownerChecks;')
    (out/'display-probe.c').write_text(admission)
    sources[sources.index(ROOT/'c/calypsi/display.c')]=out/'display-probe.c'
    backend=(ad/'gem-vbxe.c').read_text().replace('static void drain(void)\n{',
        'extern void DrawingAdmissionProbe(void);\nstatic void drain(void)\n{\n    DrawingAdmissionProbe();')
    (out/'gem-vbxe.c').write_text(backend)
    sources[sources.index(ad/'gem-vbxe.c')]=out/'gem-vbxe.c'
    foreign=emit(out,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/input.s',ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s'],['DrawingPeer'],
        optimize=mode=='opt',includes=[src,ad],definitions={
            'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
            'gem-vbxe.c':['-DGEM_DRAWING_ONLY']},probes=[(ROOT/'c/calypsi/input-layout.c',expected_layout())])
    for name in ('GemServiceWorker','GemClientInit','GemVbxeBackend','cursor_show','cursor_hide'):
        require(name not in foreign['symbols'],'Unexpected GUI policy: '+name)
    foreign['provenance'].update(extraction=extraction,source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in sources})
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    sy=foreign['symbols'];inc=out/'c-image.inc'
    inc.write_text(''.join(f'CONST C_{n.upper()}=${sy[n]:x}\n' for n in ('main','stage','ExecDisplayEntries','ExecInputEntries')))
    source=out/'launcher.act';source.write_text(read_source(ROOT/'tests/programs/gem_text_launcher.act',{
        'c-image.inc':inc,'../../c/calypsi/display-bridge.inc':ROOT/'c/calypsi/display-bridge.inc',
        '../../c/calypsi/input-bridge.inc':ROOT/'c/calypsi/input-bridge.inc'}))
    p=build(compiler(ROOT/'build/actionc'),source,out/'program',optimize=mode=='opt',tasks=True,
            task_capacity=8,console=False,foreign_image=foreign)
    report=dict(status='running',tier='development',mode=mode,build=p['build'],provenance=foreign['provenance'],
                bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned bridge')
            report['machine']=verify_machine(b,ROM,PIN);b._cmd_ok('MOUSE ST')
            saved={}
            def before(b):
                saved['screen_at']=b.peek16(0x58);saved['screen']=b.memdump(saved['screen_at'],960)
                saved['dma']=b.memdump(0x22f,3)
                condition=f'dw(${sy["checkpoint"]:x})=1';marker=p['labels']['native_nmi']
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=10000,timeout=180)
                b.bp_clear_all();require(b.peek16(sy['failures'])==0,'Shared library or input failure')
                condition=f'@frame>{b.eval_expr("@frame")+1}'
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=10,timeout=5);b.bp_clear_all()
                model=Raster(font_bytes(src/'vdi/font8x8.c'));model.apply(25,ints=[5]);model.apply(11,[0,0,639,239])
                for pen in range(16):
                    for i,ch in enumerate(b'AB W 09'):
                        for row in range(8):
                            for col in range(8):
                                if model.font[row*256+ch]&(128>>col):
                                    model.pixel(32+(pen&1)+i*8+col,8+pen*9+row,pen)
                report['pixels_sha256']=pixels(b,out,model.packed())
                b.memload(sy['gate'],b'\1\0')
                condition=f'dw(${sy["checkpoint"]:x})=2'
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=4000,timeout=60)
                b.bp_clear_all();require(b.peek16(sy['failures'])==0,'Text run boundary failure')
                condition=f'@frame>{b.eval_expr("@frame")+1}'
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=10,timeout=5);b.bp_clear_all()
                model=Raster(font_bytes(src/'vdi/font8x8.c'));model.apply(25,ints=[5]);model.apply(11,[0,0,639,239])
                def text_run(x,y,text,ink,paper):
                    for i,ch in enumerate(text):
                        for row in range(8):
                            for col in range(8):
                                model.pixel(x+i*8+col,y+row,ink if model.font[row*256+ch]&(128>>col) else paper)
                for i in range(4):text_run(0,i*8,range(i*64,(i+1)*64),i,5)
                cross=[i*7&255 for i in range(80)]
                text_run(0,200,cross,1,5);text_run(512,204,cross[:16],0,3)
                text_run(632,232,b'A',0,1)
                report['text_run_pixels_sha256']=pixels(b,out,model.packed())
                b.memload(sy['gate'],b'\2\0')
                condition=f'dw(${sy["checkpoint"]:x})=3'
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=4000,timeout=60)
                b.bp_clear_all();require(b.peek16(sy['failures'])==0,'Combined text/fill failure')
                condition=f'@frame>{b.eval_expr("@frame")+1}'
                b.bp_set(marker,condition=condition);run_to(b,marker,condition=condition,frame_limit=10,timeout=5);b.bp_clear_all()
                model=Raster(font_bytes(src/'vdi/font8x8.c'));model.apply(25,ints=[5]);model.apply(11,[0,0,639,239])
                for x,y,text,ink,paper,fx,fy,w,h,pen in (
                    (8,8,b'A',1,5,16,15,8,1,1),
                    (0,24,range(32),0,3,256,31,8,1,0),
                    (0,40,range(32,65),1,5,264,47,8,1,1),
                    (0,64,range(128,208),2,5,0,80,640,4,3),
                    (0,104,range(64,128),0,5,0,120,384,8,0),
                    (0,144,b'AB W 09',1,5,0,147,56,2,7),
                    (624,232,b'A',1,5,632,239,8,1,1),
                    (0,200,[i*7&255 for i in range(33)],1,5,264,207,8,1,1)):
                    text_run(x,y,text,ink,paper)
                    for row in range(fy,fy+h):
                        for col in range(fx,fx+w):model.pixel(col,row,pen)
                report['text_fill_pixels_sha256']=pixels(b,out,model.packed())
                b.memload(sy['gate'],b'\3\0')
            runtime,_=execute(b,p,before_run=before,frame_limit=4000,timeout=120)
            require(b.peek16(sy['finished'])==1 and b.peek16(sy['failures'])==0,'Incomplete fixture')
            clean_ownership(b,p,p['output'])
            require(b.memdump(saved['screen_at'],960)==saved['screen'] and b.memdump(0x22f,3)==saved['dma'],'OS display changed')
            usage=stack_usage(b,p['build']['memory'])
            require(all(item['remaining_above_floor']>0 for item in usage.values()),'Stack budget exhausted')
            report.update(status='pass',runtime=runtime,checks=b.peek16(sy['checks']),stack_usage=usage)
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt');a=parser.parse_args();run(a.output,a.mode)
