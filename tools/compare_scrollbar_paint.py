#!/usr/bin/env python3
"""Build a direct scrollbar comparison image without changing production sources."""
import argparse
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import adapter_state as adapter
import build_bitmap_console
import calypsi_build
from generate_aes_server import ABI
from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sio_transaction_trace import read_events
from test_aes_server import applications
from test_mouse_observe import BRIDGE, PIN, ROM
from test_screnmgr import build_scroll


RENDERER = ROOT/'ports/gem4xe/adapter/gem-vbxe.c'
FRAME = ROOT/'lib/desktop/desktop-frame.c'
DIRECT = '''UWORD CompareDirectScrollbar(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,UWORD (*draw)(void *),void *context)
{
    UWORD status=DisplayEnter(grant),completed;
    if (status!=DISPLAY_OK) return status;
    if (display.operationPending) status=DISPLAY_BUSY;
    else if (!fault) {
        GemDrawingPrepare(left,top,right,bottom);
        if (!fault && !draw(context)) status=DISPLAY_BAD_ARGUMENT;
    }
    completed=borrow_leave(grant);
    return status==DISPLAY_OK ? completed:status;
}

'''


def insert(source, needle, replacement):
    require(source.count(needle)==1,'Changed comparison boundary: '+needle)
    return source.replace(needle,replacement,1)


def sources(out):
    folder=out/'direct-source'
    folder.mkdir(parents=True,exist_ok=True)
    renderer=folder/RENDERER.name
    renderer.write_text(insert(RENDERER.read_text(),'UWORD GemDrawingFrameBorrow(',
                               DIRECT+'UWORD GemDrawingFrameBorrow('))
    frame=folder/FRAME.name
    declaration='''extern UWORD CompareDirectScrollbar(struct DisplayGrant *,UWORD,UWORD,
    UWORD,UWORD,UWORD (*)(void *),void *);

'''
    text=insert(FRAME.read_text(),'UWORD DesktopFrameBorrow(',
                declaration+'UWORD DesktopFrameBorrow(')
    call='    return GemDrawingFrameBorrow(grant,l,t,l+frame->clip.g_w,'
    frame.write_text(insert(text,call,'''    if (frame->start==GEM_O_VSCROLL || frame->start==GEM_O_HSCROLL)
        return CompareDirectScrollbar(grant,l,t,l+frame->clip.g_w,
                                      t+frame->clip.g_h,fragment,p);
'''+call))
    return {RENDERER:renderer,FRAME:frame}


def observe_overlap(bridge, program, symbols, out, reference):
    """Sample the current two-window fixture while the setter still holds UPDATE."""
    labels=program['labels']
    fields=ABI['constants']
    selected={13:'WF_HSLIDE',15:'WF_HSLIDE',25:'WF_HSLIDE',26:'WF_HSLSIZE',
              29:'WF_VSLIDE',30:'WF_VSLSIZE'}

    def word(name):
        return int.from_bytes(bridge.memdump(symbols[name],2),'little')

    def reach(condition):
        bridge.bp_clear_all()
        bridge.bp_set(labels['native_irq'],condition=condition)
        bridge.bp_set(labels['done'],condition=adapter.STOPPED)
        run_to(bridge,labels['native_irq'],condition=condition,timeout=30,frame_limit=600)

    def point(phase,step):
        reach(f'(dw(${symbols["FramePhase"]:x})={phase})&(dw(${symbols["FramePoint"]:x})={step})')

    def scan(phase,stage):
        reach('@frame>=%d'%(bridge.eval_expr('@frame')+3))
        path=out/f'slider-{phase}-{stage}.bgra'
        picture=bridge.rawscreen(str(path))
        raw=path.read_bytes()
        require(picture.stride==672*4 and len(raw)==672*240*4,'Unexpected scanout dimensions')
        if reference:
            require(raw==(reference/path.name).read_bytes(),f'Phase {phase} {stage}: direct scanout differs')
        return raw,sha256(path)

    rows=[]
    for phase in range(1,max(selected)+1):
        point(phase,0)
        if phase in selected:
            before,before_hash=scan(phase,'before')
        bridge.poke16(symbols['FrameGo'],phase*3-2)
        point(phase,3)
        if phase in selected:
            field=selected[phase]
            require(word('FrameField')==fields[field] and word('FrameHeld')==1
                    and word('FrameResult')==1 and word('FrameStatus')==0,
                    f'Phase {phase}: expected successful {field} under UPDATE')
            after,after_hash=scan(phase,'return')
            changed=[(i%672-16,i//672) for i in range(672*240)
                     if before[i*4:i*4+4]!=after[i*4:i*4+4]]
            if phase in (25,26):
                require(all(32<=x<80 and 180<=y<194 for x,y in changed),
                        f'Phase {phase}: root slider touched pixels beyond its visible end')
            elif phase in (29,30):
                require(all(303<=x<322 and 64<=y<194 for x,y in changed),
                        f'Phase {phase}: peer slider touched pixels outside its column')
            rows.append(dict(phase=phase,field=field,before_sha256=before_hash,return_sha256=after_hash,
                             changed_pixels=len(changed),matched_scratch=bool(reference)))
            print(f'{field} phase {phase}: {len(changed)} changed pixels',flush=True)
        bridge.poke16(symbols['FrameGo'],phase*3)
    bridge.bp_clear_all()
    return rows


def frame_comparison(out, program, foreign, paint, reference):
    symbols=foreign['symbols']
    begin,end=symbols['FrameCallBegin'],symbols['FrameCallEnd']
    draw=symbols['CompareDirectScrollbar' if paint=='frame' else 'GemDrawingFrameBorrow']
    trace=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in (begin,end,draw)))
    labels=program['labels']
    with patch.dict(os.environ,trace), emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        bridge.boot(str(program['xex']))
        run_to(bridge,labels['loader_start'],frame_limit=1800,timeout=180)
        bridge.bp_set(labels['start'])
        run_to(bridge,labels['start'])
        bridge.profile_start()
        rows=observe_overlap(bridge,program,symbols,out,reference)
        bridge.profile_stop()

    phase=0
    active=False
    calls={}
    for _,event in read_events(out/'emulator.log',{'cpu'}):
        pc=int(event[4],16)
        if pc==begin:
            phase+=1
            active=True
        elif pc==end:
            active=False
        elif pc==draw and active:
            calls[phase]=calls.get(phase,0)+1
    require(phase==rows[-1]['phase'] and not active,'Incomplete frame call trace')
    for row in rows:
        row['paint_calls']=calls.get(row['phase'],0)
        require(row['paint_calls']>0,f'Phase {row["phase"]}: selected paint path did not run')
    require(all(row['changed_pixels'] for row in rows if row['phase'] not in (25,26)),
            'Uncovered slider checkpoints produced no visible changes')
    result=dict(status='pass',tier='development',paint=paint,machine=machine,
                xex_sha256=program['build']['xex_sha256'],samples=rows)
    (out/'overlap.json').write_text(json.dumps(result,indent=2)+'\n')


def build(out, suite, baseline, reference=None, replay=False):
    out=out.resolve()
    require(out.is_relative_to(ROOT/'build'),'Use a comparison directory under build/')
    replacements=sources(out) if suite!='scratch-frame' and not replay else {}
    emit=build_bitmap_console.emit
    drawing=build_bitmap_console.drawing
    command=calypsi_build.command
    reused={};recompiled=[]
    if suite=='viewer':
        provider=json.loads((baseline/'c-image.json').read_text())['provenance']
        for name,digest in {**provider['source_inputs'],**provider['header_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Changed baseline input '+name)
        shutil.copytree(baseline/'drawing',out/'drawing',dirs_exist_ok=True)
        inputs=provider['source_inputs']
        source_digests={(Path(name).name,digest) for name,digest in inputs.items()}

    def emit_comparison(output, inputs,*args,**kwargs):
        return emit(output,[replacements.get(source,source) for source in inputs],*args,**kwargs)

    def draw_comparison(folder,*args,**kwargs):
        with patch('build_bitmap_console.emit',emit_comparison):
            result=drawing(folder,*args,**kwargs)
        recorded=result['provenance']['source_inputs']
        for original,copy in replacements.items():
            del recorded[str(original.relative_to(ROOT))]
            recorded[str(copy.relative_to(ROOT))]=sha256(copy)
        result['provenance']['scrollbar_comparison']=True
        (folder/'c-image.json').write_text(json.dumps(result,indent=2)+'\n')
        return result

    def reuse_command(args,**kwargs):
        if '-c' in args and '-o' in args:
            obj=Path(args[args.index('-o')+1]);source=Path(args[-1])
            if source not in replacements.values():
                require(obj.is_file(),'Missing frozen object '+str(obj))
                if not obj.name.startswith('layout-') and source.parent.name!='runtime-source':
                    require((source.name,sha256(source)) in source_digests,
                            'Changed object input '+str(source))
                reused[obj.name]=sha256(obj)
                return ''
            recompiled.append(obj.name)
        return command(args,**kwargs)

    if suite=='viewer':
        with patch('build_gem_desktop.drawing',draw_comparison),patch('calypsi_build.command',reuse_command):
            build_scroll(out,apps_from=baseline)
        require(len(recompiled)==2,'Unexpected comparison object builds')
        (out/'objects.json').write_text(json.dumps(dict(reused=reused,recompiled=recompiled),indent=2)+'\n')
    else:
        with patch('test_aes_server.drawing',draw_comparison if replacements else drawing):
            program,foreign=applications(out,'frame',replay=replay,build_only=True)
        frame_comparison(out,program,foreign,suite,reference)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suite',choices=('viewer','frame','scratch-frame'),required=True)
    parser.add_argument('--baseline',type=Path,default=ROOT/'build/gem-mouse-show/viewer')
    parser.add_argument('--reference-frame',type=Path)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args()
    if args.suite=='viewer' and (args.replay or args.reference_frame):
        parser.error('Frame replay and reference require a frame suite')
    build(args.output,args.suite,args.baseline.resolve(),args.reference_frame,args.replay)
