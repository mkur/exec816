#!/usr/bin/env python3
"""AES donor pixel oracle through the real shared VBXE owner."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from build_bitmap_console import drawing,prepare
from native_program import ROOT,build,compiler,require,sha256,read_build,verify_machine
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_gem_interactive import pixels
from stack_budget import stack_usage
from desktop_budget import delta
from console_turn_profile import flat_markers,analyze_events
from sio_transaction_trace import read_events

def expected(stage):
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
    device.dev.fill_rect(0,0,639,239,3)
    if 17<=stage<=21:
        if stage>=20:device.dev.fill_rect(17,42,624,57,8)
        return bytes(device.dev.s.mem[:76800])
    if stage==16:
        for case in range(16):
            x=9 if case in (1,3,5,6,8,10,12) else 8;y=8+case*16
            if case==13:x=-3
            if case==14:y=-3
            if case==15:y=237
            count=63 if case==0 else 64 if case==1 else 65
            device.wrt_mode=1;device.text_color=0 if case==8 else 2
            device.clip=1;device.xmn=12 if case==6 else 0;device.xmx=518 if case==6 else 639
            device.ymn=y+2 if case==7 else 0 if case==14 else y;device.ymx=y+5 if case==7 else 239 if case==15 else y+7
            for i in range(count):
                device._glyph(ord(' ' if case==4 or (case==5 and i%3==0) else 'A'),x+i*8,y)
        return bytes(device.dev.s.mem[:76800])
    if 13<=stage<=15:
        if stage!=15:
            left,top,right,bottom=(0,0,640,240) if stage==13 else (608,208,640,240)
            for x in range(left,right):
                device.dev.plot_xor(x,top);device.dev.plot_xor(x,bottom-1)
            for y in range(top+1,bottom-1):
                device.dev.plot_xor(left,y);device.dev.plot_xor(right-1,y)
        return bytes(device.dev.s.mem[:76800])
    if stage==11:
        # Several objects intersect this strip. Its first chunk must
        # remain offscreen, including across a rejected continuation.
        return bytes(device.dev.s.mem[:76800])
    if stage==7:
        for i in range(64):
            x=16+(i%8)*32+(i&1);y=8+(i//8)*16
            device.wrt_mode=(i>>1)&1;device.text_color=0 if i&4 else 2
            device.clip=1;device.xmn=x+1;device.xmx=x+1+(i>>3)
            device.ymn=y+1;device.ymx=y+5
            device._glyph(ord('A' if i%7 else ' '),x,y)
        device.clip=0;device.wrt_mode=1;device.text_color=0
        for x,y in ((-3,150),(637,150),(300,-3),(300,237)):
            device._glyph(ord('A'),x,y)
        return bytes(device.dev.s.mem[:76800])
    tree=[a.Obj(-1,1,6,a.G_BOX,0,0,0x11178,17,19,320,160)]
    for i in range(1,7):
        tree.append(a.Obj(i+1 if i<6 else 0,-1,-1,a.G_BUTTON,a.SELECTABLE,0,0,9+(i-1)*50,23,40,24))
    tree[1].ob_flags|=a.EXIT|a.DEFAULT
    tree[2].ob_state=a.SELECTED;tree[3].ob_state=a.DISABLED
    tree[4].ob_state=a.SELECTED|a.DISABLED
    tree[5].ob_type=a.G_STRING;tree[5].ob_flags=0;tree[5].ob_spec=4
    tree[6].ob_type=a.G_IBOX;tree[6].ob_flags=a.LASTOB;tree[6].ob_spec=0x21170
    if stage>=5:
        tree[0].ob_width=608;tree[0].ob_tail=8;tree[6].ob_next=7;tree[6].ob_flags=0
        tree.append(a.Obj(8,-1,-1,a.G_STRING,0,0,8,24,70,504,24))
        tree.append(a.Obj(0,-1,-1,a.G_STRING,a.LASTOB,0,4,65,26,40,24))
    if stage==22:
        tree=[a.Obj(-1,1,1,a.G_BOX,0,0,0x78,17,19,608,160),
              a.Obj(0,-1,-1,a.G_BUTTON,a.SELECTABLE|a.LASTOB,
                    a.SELECTED|a.DISABLED,8,9,23,504,24)]
    if 8<=stage<=10:
        # Transparent and hidden roots still receive the client's background.
        # Several children intersect one strip, so this also checks that a
        # continuation preserves pixels drawn by its preceding chunk.
        device.dev.fill_rect(17,19,624,178,8)
        tree[0].ob_type=a.G_IBOX if stage==8 else a.G_BOX
        tree[0].ob_spec=0x11108
        tree[0].ob_flags=a.HIDETREE if stage==10 else 0
    aes=a.AES(device,tree,{0:a.Text('Abc'),4:a.Text('XYZ'),8:a.Text('A'*63)});aes.gsx_start()
    aes.gsx_sclip(a.Rect(32,45,263,12) if stage==2 else a.Rect(17,42,608,16) if stage==12 else a.Rect(17,19,608 if stage>=5 else 320,160))
    aes.ob_draw(0,7)
    if stage==4:
        for x in range(29,63):device.dev.plot_xor(x,63)
    if stage==22:
        for x in range(29,527):device.dev.plot_xor(x,63)
    return bytes(device.dev.s.mem[:76800])

def run(out,mode,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    report=dict(slice='AW1',tier='development',status='running',mode=mode,observations=[])
    if replay:
        p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text())
    else:
        f=drawing(out,mode=='opt',widget_probe=True)
        source=out/'probe.act';source.write_text('MODULE AESPIXELS\nPROC Main()\nRETURN\nENDMODULE\n')
        launcher=prepare(source,out,f)
        p=build(compiler(ROOT/'build/actionc'),launcher,out/'program',optimize=mode=='opt',
            tasks=True,task_capacity=8,console=False,console_deferred=True,foreign_image=f)
    # Calypsi shares epilogues with nested drawing callbacks. Pair the RTL
    # with the entry stack, so a primitive return cannot truncate the sample.
    listing=next((out/'drawing').glob('*widgets-render.lst')).read_text()
    body=listing.split('WidgetPaint:',1)[1].split('.section ',1)[0]
    entry=f['symbols']['WidgetPaint']
    exits=list(re.finditer(r'\\ ([0-9a-f]{6}) (6b|5c[.]{6})\s+(?:rtl|jmp\s+long:)',body))
    require(len(exits)==1,'WidgetPaint must have one local exit')
    returns=[entry+int(exits[0][1],16)]
    def linked(pc,size):
        return next(bytes(s['bytes'][pc-s['address']:pc-s['address']+size])
            for s in f['segments'] if s['address']<=pc and pc+size<=s['address']+len(s['bytes']))
    for pc in returns:
        require(linked(pc,1)[0]==int(exits[0][2][:2],16),'Unlinked WidgetPaint exit')
    if exits[0][2].startswith('5c'):
        target=int.from_bytes(linked(returns[0]+1,3),'little')
        require(re.fullmatch(b'\x7a\x84.\x7a\x84.\x6b',linked(target,7),re.S),
            'Unknown shared WidgetPaint epilogue')
        returns=[target+6]
    spans={'paint':dict(entry=entry,returns=returns,match_return_stack=True)}
    points={n:p['labels'][n] for n in ('native_irq','native_nmi','interrupt_schedule')}
    points.update(turn=f['symbols']['WidgetPaint'],selected=p['labels']['context_restore']+4,
        worker_retire=p['labels']['done'])
    definition=dict(spans=spans,points=points,
        task_dps=[pool['dp'] for pool in p['build']['memory']['task_pools']])
    os.environ.update(EXEC816_LATENCY_TRACE='1',
        EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in flat_markers(definition).values()))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            report['machine']=verify_machine(b,ROM,PIN)
            def before(b):
                b.profile_start()
                previous=b.eval_expr('@clk') & 0xffffffff
                for stage in range(1,23):
                    marker=p['labels']['native_nmi'];condition='dw($%x)=%d'%(f['symbols']['WidgetPixelStage'],stage)
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    run_to(b,marker,condition=condition,frame_limit=6000,timeout=120)
                    condition='@frame>=%d'%(b.eval_expr('@frame')+2)
                    b.bp_clear_all();b.bp_set(marker,condition=condition)
                    run_to(b,marker,condition=condition,frame_limit=20,timeout=20)
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    require(b.peek16(f['symbols']['WidgetPixelFailures'])==0,'Target paint assertion')
                    report['observations'].append(dict(stage=stage,
                        next_index=b.peek16(f['symbols']['WidgetPixelIndex']),
                        window=[previous,b.eval_expr('@clk') & 0xffffffff],
                        pixels=pixels(b,folder,expected(stage))))
                    previous=b.eval_expr('@clk') & 0xffffffff
                    b.memload(f['symbols']['WidgetPixelGate'],stage.to_bytes(2,'little'))
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,frame_limit=12000,timeout=180)
            ownership(b,p,p['output'])
            require(b.peek16(f['symbols']['WidgetPixelFailures'])==0,'Target paint assertion')
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'Widget stack floor')
            b.profile_stop()
        events=read_events(out/'emulator.log',kinds={'cpu'})
        profile=analyze_events(events,definition)
        require(profile['routine_spans'],'No measured paint steps')
        align=lambda t:t+round((events[0][0]-t)/(1<<32))*(1<<32)
        for row in report['observations']:
            lo,hi=map(align,row['window'])
            samples=[s for s in profile['routine_spans'] if lo<=s['start']<s['end']<=hi]
            row['paint_steps']=len(samples)
            row['max_step_cpu_ms']=max((s['charged_cpu_ms'] for s in samples),default=0)
        report['timing_scope']=profile['scope']+' WidgetPaint entry through stack-matched RTL, including nested primitives, callback return, publication and fence; only its RTL instruction is excluded.'
        report.update(status='pass',bank_zero_delta=delta(p['build']['memory']),
            build_sha256=sha256(out/'program/build.json'),xex_sha256=sha256(p['xex']),provenance=f['provenance'])
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'pixel-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Widget pixels passed',mode,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');a.add_argument('--replay',action='store_true')
    args=a.parse_args();run(args.output,args.mode,args.replay)
