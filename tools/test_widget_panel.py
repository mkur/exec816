#!/usr/bin/env python3
"""AW5: complete panel interaction, two contexts, matched redraw and load timing."""
import argparse
from bisect import bisect_left, bisect_right
import hashlib
import json
import os
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT, read_build, require, verify_machine, sha256
from build_widget_panel import build
from os_boundary import emulator, run_to
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from desktop_mouse import schedule
from generate_desktop import layout
from generate_layers import layout as layer_layout
from desktop_budget import delta
from stack_budget import stack_usage
from gem_render_oracle import Raster, font_bytes, PALETTE, PENS
from control_panel_oracle import panel
from test_gem_cursor import overlay
from measure_desktop import distribution
from make_data_disk import make
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, flat_markers
from sio_transaction_trace import read_events, BASE_HZ

POSITIONS = {2:(480,128),3:(568,128),4:(480,160),5:(568,160),6:(480,192),7:(568,192)}


def observers(p):
    sy=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']
    spans=native_markers(p,[('DESKWIDGETS_INPUT','commit'),('DESKWIDGETS_PAINT','paint'),
        ('DESKPAINT_PUMP','pump'),('DESKWIDGETS_RUN','model_call'),('DESKAPP_REFRESHSTATUS','application'),('DESKINPUT_CONSUME','consume')])
    points={n:p['labels'][n] for n in ('native_irq','native_nmi','interrupt_schedule')}
    restore=p['labels']['context_restore']
    require((p['output']/'hosted.bin').read_bytes()[restore-0x1400:restore-0x1400+8]==bytes.fromhex('c230ab2b7afa6840'),'Unknown restore boundary')
    points.update(turn=spans['pump']['entry'],selected=restore+4,worker_retire=p['labels']['done'])
    definition=dict(points=points,spans={k:v for k,v in spans.items() if k!='application'},
        task_dps=[x['dp'] for x in p['build']['memory']['task_pools']])
    marks=flat_markers(definition)
    marks.update(capture=p['labels']['pointer_notify'],application=spans['application']['entry'])
    for name in ('GemWidgetFill','GemWidgetText','start','VbxeOwnerSubmit','vram_win',
                 'WidgetUpdate'):
        if name in sy:marks[name]=sy[name]
    return spans,marks,definition


def run(out, program, count=100, unobserved=False, comparison_only=False,
        idle_only=False, feedback=False):
    out.mkdir(parents=True, exist_ok=True)
    p=read_build(program)
    foreign=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    spans,marks,definition=observers(p)
    for name in ('EXEC816_MOUSE_TRACE','EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE'):
        os.environ.pop(name,None)
    if not unobserved:
        os.environ.update(EXEC816_MOUSE_TRACE='1',EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='0',
            EXEC816_LATENCY_PCS=','.join(f'{x:x}' for x in set(marks.values())))
    media=out/'media/TOOLS/SUB';media.mkdir(parents=True,exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk=out/'disk.atr';make(disk,out/'media',binary_names={'TOOLS/SUB/DATA.BIN'},filesystem='sdfs')
    font=font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
    colors={hw:bytes((v & 254)+(v >> 7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen,hw in enumerate(PENS)}
    report=dict(slice='AW5',status='running',tier='development',qualification=False,observer=not unobserved,
        count_per_load=0 if comparison_only else count,idle_only=idle_only,
        feedback_observer=feedback,samples=[],windows={},functional=[],comparison=[],build=p['build'],
        reserved_bank_zero_delta=delta(p['build']['memory']),marks=marks,
        timing_scope='Capture to commit/application: passive boundaries or IRQ observation upper bounds. Visible feedback: first matching completed scanout, <=1 frame observation quantization.',
        targets=dict(idle=dict(p95_ms=40,max_ms=60,button_max_ms=40),loaded=dict(p95_ms=60,max_ms=100,button_max_ms=100)))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.mount(0,str(disk));b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            report['machine']=verify_machine(b,ROM,PIN)
            get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
            read=lambda mod,n,size=2:get(at(mod,n),size)
            clock=lambda:b.eval_expr('@clk') & 0xffffffff
            def reach(condition):
                marker=p['labels']['native_irq'];b.bp_clear_all();b.bp_set(marker,condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def registers():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=registers
                try:run_to(b,marker,condition=condition,frame_limit=14000,timeout=180)
                finally:b.regs=original
            def frames(n=1):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            position=[320,120];context=second=service=0
            state=dict(toggle=0,radio=4,focus=2,status='Ready')
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def scan(region):
                l,t,rr,bb=region
                f=b.rawscreen(str(out/'scanout.bgra'));raw=(out/'scanout.bgra').read_bytes()
                return b''.join(raw[y*f.stride+(x+16)*4:y*f.stride+(x+16)*4+3]
                               for y in range(t,bb) for x in range(l,rr))
            def visible(pressed=-1, region=(432,80,624,224), previous=None):
                r=Raster(font);panel(r,True,**state,pressed=pressed)
                packed=overlay(r,position)
                l,t,rr,bb=region
                want=b''.join(colors[packed[(y*640+x)//2] >> (0 if x & 1 else 4) & 15] for y in range(t,bb) for x in range(l,rr))
                invalid_frames=max_invalid=0
                for attempt in range(500):
                    actual=scan(region)
                    if previous is not None:
                        invalid=0
                        for y in range(t,bb):
                            for x in range(l,rr):
                                # Pointer save/restore has its own presentation
                                # timing; measure the control pixels around it.
                                if position[0]-1<=x<position[0]+17 and position[1]<=y<position[1]+16:
                                    continue
                                at_pixel=((y-t)*(rr-l)+x-l)*3
                                pixel=actual[at_pixel:at_pixel+3]
                                invalid+=pixel!=previous[at_pixel:at_pixel+3] and pixel!=want[at_pixel:at_pixel+3]
                        invalid_frames+=invalid>0;max_invalid=max(max_invalid,invalid)
                    if actual==want:return dict(clock=clock(),sha256=hashlib.sha256(actual).hexdigest(),scans=attempt+1,
                        invalid_frames=invalid_frames,max_invalid_pixels=max_invalid)
                    frames()
                b.screenshot(str(out/'failure.png'))
                raise RuntimeError('Panel pixels differ: '+str(state)+' pressed='+str(pressed))
            def settled():
                scene=service+layout()['Service']['fields']['scene']
                lf=layer_layout()
                busy=scene+lf['Scene']['fields']['busy']
                dirty=scene+lf['Scene']['fields']['items']+2*lf['Layer']['size']+lf['Layer']['fields']['dirty']
                queued=service+layout()['Service']['fields']['widgetCount']
                reach('(db($%x)=0)&(db($%x)=0)&(db($%x)=0)&(db($%x)=0)'%(busy,dirty,at('DESKAPP','refresh'),queued))
            def model():
                states=[get(context+24+24*i+10) for i in range(8)]
                require(states==[0,0,state['toggle'],8,int(state['radio']==4),int(state['radio']==5),0,0],'Wrong panel states: '+str(states))
                require(get(context+18)==state['focus'],'Wrong keyboard focus')
                offset=get(context+24+24+12,4)
                label=b.memdump(context+792+offset,21).split(b'\0')[0].decode('ascii')
                require(label==state['status'],'Wrong status: '+label)
                require(get(second+24+24+10)==1,'Other widget context changed')
            def status(obj):
                if obj==2:
                    state['toggle']^=1
                    state['status']='Toggle on [2]' if state['toggle'] else 'Toggle off [2]'
                elif obj in (4,5):
                    state['radio']=obj;state['status']='Small [4]' if obj==4 else 'Large [5]'
                else:state['status']='Applied [6]' if obj==6 else 'Cancelled [7]'
            def click(obj,load=None):
                move(*POSITIONS[obj]);settled();state['focus']=obj
                before=read('DESKAPP','updates');samples=[]
                for down in (1,0):
                    x,y=POSITIONS[obj]
                    border=3 if obj==6 else 2 if obj==7 else 1
                    button_region=(x-32-border,y-8-border,x+40+border,y+8+border)
                    if feedback:
                        frames(2)
                        previous_pixels=scan(button_region)
                    item=dict(load=load,object=obj,edge='press' if down else 'release',submitted=clock())
                    b._cmd_ok('MOUSE AT 2000 0 0 '+str(down))
                    reach('dw($%x)=%d'%(at('DESKINPUT','buttons'),down));item['consumed']=clock()
                    reach('(dw($%x)=%d)&(dw($%x)=%d)'%(context+20,obj if down else 65535,context+22,down))
                    item['committed']=clock()
                    if not down:
                        reach('dw($%x)>%d'%(at('DESKAPP','updates'),before));item['application']=clock()
                        status(obj)
                        if read('DESKAPP','benchmarkFull',1):state['focus']=2
                    x,y=POSITIONS[obj]
                    # Press feedback is an exact button crop; release feedback
                    # is the changed application label, followed by full panel.
                    region=(x-32,y-8,x+40,y+8) if down else (448,104,608,112)
                    if feedback:
                        item['button_feedback']=visible(obj if down else -1,button_region,previous_pixels)
                    item['visible']=visible(obj if down else -1,region)['clock']
                    samples.append(item)
                settled();digest=visible();model()
                require(read('DESKAPP','updates')==before+1,'Duplicate semantic action')
                if load is not None:report['samples'].extend(samples)
                return dict(samples=samples,scene=digest,epoch=get(context,4),state=dict(state))
            def key(name,obj=None,shift=False):
                previous=read('DESKAPP','updates')
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                if obj is not None:
                    reach('dw($%x)>%d'%(at('DESKAPP','updates'),previous))
                    if obj<0:state['status']='Cancelled (Esc)'
                    else:status(obj)
                frames(3)
            def load(value):
                b.poke16(at('DESKTEST','mode'),value)
                reach('dw($%x)=%d'%(at('DESKTEST','runningMode'),value));frames(4)
            def before(bridge):
                nonlocal context,second,service
                if not unobserved:b.profile_start()
                reach('dw($%x)=1'%at('DESKTEST','ready'))
                service=read('DESKSTATE','service',3);sf=layout()['Service']['fields'];wf=layout()['Window']['fields'];ws=layout()['Window']['size']
                second=get(service+sf['windows']+ws+wf['widgets'],3)
                context=get(service+sf['windows']+2*ws+wf['widgets'],3)
                require(context and second and context!=second,'Contexts alias')
                load(4);move(88,96)
                for down in (1,0):
                    b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));reach('dw($%x)=%d'%(at('DESKINPUT','buttons'),down));frames(4)
                # Loaded peers can defer model consumption beyond four frames;
                # wait for the semantic result, then measure latency separately.
                reach('(dw($%x)=1)&(dw($%x)=65535)&(dw($%x)=0)'%
                    (second+24+24+10,second+20,second+22))
                require(get(second+24+24+10)==1,'Second form did not toggle')
                load(0)
                report['functional'].append(dict(name='second context toggled',contexts=[context,second]))
                report['functional'].append(dict(name='toggle',result=click(2)))
                # Disabled clicks and arbitrary raw keys do not become actions.
                old=read('DESKAPP','updates');move(*POSITIONS[3])
                for down in (1,0):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(4)
                key('A');require(read('DESKAPP','updates')==old,'Disabled/raw input activated')
                visible();model();report['functional'].append(dict(name='disabled and raw key ignored'))
                key('TAB');state['focus']=4;visible();model()
                key('TAB',shift=True);state['focus']=2;visible();model()
                key('SPACE',2);visible();model()
                key('RETURN',6);visible();model()
                key('ESCAPE',-1);visible();model()
                key('BREAK',-1);visible();model()
                report['functional'].append(dict(name='Tab, Shift-Tab, Space, Return, Escape and BREAK'))
                for name,value in (() if comparison_only else (('idle',0),) if idle_only else (('idle',0),('scroll',2),('disk',3))):
                    load(value);begin=clock();writes=read('DESKTEST','writes');reads=read('DESKTEST','reads')
                    aes_before={name:get(foreign[name]) for name in ('AESMessages','AESTimers') if name in foreign}
                    for index in range(count):
                        click((2,5,6,4,7)[index%5],name)
                        if (index+1)%10==0:print(name,index+1,flush=True)
                    report['windows'][name]=[begin,clock()]
                    report.setdefault('progress',{})[name]=dict(writes=read('DESKTEST','writes')-writes,reads=read('DESKTEST','reads')-reads)
                    if aes_before:
                        report.setdefault('aes_progress',{})[name]={
                            key:(get(foreign[key])-old)&65535 for key,old in aes_before.items()}
                        report['aes_workload']='Unchanged continuous request/reply loop with a 100 ms caller timer after each exchange; completed counts are measured over each gesture cohort, not fixed offered throughput.'
                    if value==2:require(read('DESKTEST','writes')>writes,'Console stopped under widget load')
                    if value==3:require(read('DESKTEST','reads')>reads,'Physical SDFS stopped under widget load')
                load(0)
                # End every action with identical state and focus. The only
                # experimental difference is the application's patch/SetTree.
                recovery=any('_DESKAPP_STALEONCE_' in d['name'] for d in p['image']['data'])
                if recovery:
                    retries=read('DESKAPP','staleRetries')
                    b.poke(at('DESKAPP','staleOnce'),1)
                click(2)
                if recovery:
                    require(read('DESKAPP','staleRetries')==retries+1,'Missing stale patch retry')
                    report['functional'].append(dict(name='stale action patch retries from fresh snapshot'))
                if state['toggle']:click(2)
                for full in (0,1):
                    b.poke(at('DESKAPP','benchmarkFull'),full)
                    begin=clock();result=click(2)
                    report['comparison'].append(dict(full_redraw=bool(full),begin=begin,end=clock(),result=result,
                        status_damage_pixels=176*120 if full else 160*8))
                    b.poke(at('DESKAPP','benchmarkFull'),0);click(2)
                require(report['comparison'][0]['result']['scene']['sha256']==report['comparison'][1]['result']['scene']['sha256'],'Matched redraw produced different pixels')
                report['stack_usage']=stack_usage(b,p['build']['memory'])
                b.poke16(at('DESKTEST','mode'),9);reach('dw($%x)=2'%at('DESKTEST','ready'));b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=15000)
            ownership(b,p,p['output']);report['ownership']='restored'
        if not unobserved:
            analyze(report,out,p,spans,marks,definition)
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def analyze(report, out, p, spans, marks, definition):
    if report.get('feedback_observer'):
        report['label_observation_scope']='With feedback enabled, the label check follows the button check and may overestimate first label visibility; compare button_feedback clocks for button latency.'
    trace=out/'emulator.log'
    events=read_events(trace, kinds={'cpu'})
    by_pc={}
    for tick,event in events:
        by_pc.setdefault(int(event[4],16),[]).append(tick)
    times=lambda pc:by_pc.get(pc,[])
    captures=times(marks['capture']);entries=times(spans['commit']['entry'])
    model_returns=sorted(t for pc in spans['model_call']['returns'] for t in times(pc))
    align=lambda t:t+round((events[0][0]-t)/(1<<32))*(1<<32)
    measured=report['samples']+[s for row in report['functional'] if 'result' in row for s in row['result']['samples']]+[s for row in report['comparison'] for s in row['result']['samples']]
    for sample in measured:
        lo,hi=align(sample['submitted']),align(sample['consumed'])
        captured=[t for t in captures if lo<=t<=hi]
        require(captured,'Missing physical capture')
        captured=captured[-1];sample['capture']=captured
        entry=entries[bisect_left(entries,captured)]
        commit=model_returns[bisect_left(model_returns,entry)]
        require(commit<=align(sample['visible']),'Missing model commit before feedback')
        sample['capture_to_commit_ms']=(commit-captured)/BASE_HZ*1000
        sample['capture_to_button_consumed_ms']=(align(sample['consumed'])-captured)/BASE_HZ*1000
        sample['capture_to_visible_ms']=(align(sample['visible'])-captured)/BASE_HZ*1000
        if 'button_feedback' in sample:
            sample['capture_to_button_pixels_ms']=(align(sample['button_feedback']['clock'])-captured)/BASE_HZ*1000
        if 'application' in sample:
            sample['capture_to_application_ms']=(align(sample['application'])-captured)/BASE_HZ*1000
            # The actual retained-model patch is distinct from the client
            # merely receiving its semantic action. Keep both IPC/scene wait
            # and patch-to-scanout latency visible without changing the oracle.
            if sample.get('load') is not None:
                patches=times(marks['WidgetUpdate'])
                patch=patches[bisect_left(patches,commit)]
                require(patch<=align(sample['visible']),'Missing status patch before feedback')
                sample['commit_to_patch_ms']=(patch-commit)/BASE_HZ*1000
                sample['patch_to_visible_ms']=(align(sample['visible'])-patch)/BASE_HZ*1000
    profile=analyze_events(events,definition)
    report['render_cost']=dict(routines=profile['routines'],max_charged_cpu_ms=profile['max_charged_cpu_ms'],
        scope=profile['scope'],maximum_quantum_scope='Paint call charged CPU is a conservative upper bound on uninterrupted rendering; IRQ and other-Task time excluded.')
    for comparison in report['comparison']:
        lo,hi=align(comparison['begin']),align(comparison['end'])
        comparison['work']={name:bisect_right(times(marks[name]),hi)-bisect_left(times(marks[name]),lo) for name in ('GemWidgetFill','GemWidgetText','start','VbxeOwnerSubmit','vram_win') if name in marks}
        spans_in=[s for s in profile['routine_spans'] if s['kind']=='paint' and lo<=s['start']<s['end']<=hi]
        comparison['paint_cpu_ms']=sum(s['charged_cpu_ms'] for s in spans_in)
        comparison['paint_quanta']=len(spans_in)
    report['latency']={}
    for load in report['windows']:
        selected=[s for s in report['samples'] if s['load']==load]
        report['latency'][load]={key:distribution([s[key] for s in selected if key in s]) for key in ('capture_to_commit_ms','capture_to_application_ms','capture_to_button_consumed_ms','capture_to_visible_ms','capture_to_button_pixels_ms','commit_to_patch_ms','patch_to_visible_ms')}
        report['latency'][load]['press_feedback']=distribution([s['capture_to_visible_ms'] for s in selected if s['edge']=='press'])
        report['latency'][load]['application_label']=distribution([s['capture_to_visible_ms'] for s in selected if s['edge']=='release'])
        if report.get('feedback_observer'):
            feedback=[s['button_feedback'] for s in selected]
            report.setdefault('feedback',{})[load]=dict(
                scope='Completed scanouts after model/application observation until the first exact button match; pointer footprint excluded. A pixel must match its pre-edge or final colour. This is not a continuous scanout or whole-gesture flicker proof.',
                edges=len(feedback),edges_with_invalid_pixels=sum(s['invalid_frames']>0 for s in feedback),
                invalid_frames=sum(s['invalid_frames'] for s in feedback),
                max_invalid_pixels=max(s['max_invalid_pixels'] for s in feedback))
        lo,hi=map(align,report['windows'][load])
        paints=[s for s in profile['routine_spans'] if s['kind']=='paint' and lo<=s['start']<s['end']<=hi]
        report.setdefault('work',{})[load]=dict(paint_quanta=len(paints),
            paint_cpu_ms=sum(s['charged_cpu_ms'] for s in paints),
            max_quantum_cpu_ms=max(s['charged_cpu_ms'] for s in paints),
            primitive_entries={name:bisect_right(times(marks[name]),hi)-bisect_left(times(marks[name]),lo)
                for name in ('GemWidgetFill','GemWidgetText','start','VbxeOwnerSubmit','vram_win') if name in marks})
    # Count logical damage independently from the Control Panel geometry. Its
    # controls are disjoint; each focus underline fits inside its own button.
    focus,radio=2,4
    for load in report['windows']:
        pixels=0
        actions=[s['object'] for s in report['samples'] if s['load']==load and s['edge']=='press']
        def area(objects):
            pixels=0
            for obj in set(objects):
                x,y=POSITIONS[obj];border=3 if obj==6 else 2 if obj==7 else 1
                pixels+=(72+2*border)*(16+2*border)
            return pixels
        for obj in actions:
            pixels+=area([obj])+(66 if focus!=obj else 0)
            pixels+=area([radio,obj] if obj in (4,5) and obj!=radio else [obj])+160*8
            focus=obj
            if obj in (4,5):radio=obj
        report['work'][load]['logical_requested_damage_pixels']=pixels
        report['work'][load]['damage_scope']='Independent sum of disjoint button bounds, previous focus underline and 160x8 status; new focus is contained by the pressed button. Excludes Layers exposure and physical overdraw.'
    report['trace_sha256']=sha256(trace)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output',type=Path,required=True);a.add_argument('--program',type=Path,required=True)
    a.add_argument('--count',type=int,default=100);a.add_argument('--unobserved',action='store_true')
    a.add_argument('--comparison-only',action='store_true',help='Functional checks and matched patch/full-redraw control without the load cohorts')
    a.add_argument('--idle-only',action='store_true',help='Run only the focused idle button cohort')
    a.add_argument('--feedback',action='store_true',help='Observe intermediate button pixels for erase/redraw flicker')
    a.add_argument('--analyze-only',action='store_true',help='Recompute passive metrics from the completed guest run')
    args=a.parse_args()
    if args.analyze_only:
        out=args.output.resolve();report=json.loads((out/'results.json').read_text())
        require(report.get('ownership')=='restored','Guest run did not complete cleanly')
        p=read_build(args.program.resolve());spans,marks,definition=observers(p)
        analyze(report,out,p,spans,marks,definition)
        report['status']='pass';report.pop('error',None)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    else:run(args.output.resolve(),args.program.resolve(),args.count,args.unobserved,args.comparison_only,args.idle_only,args.feedback)
