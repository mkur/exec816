#!/usr/bin/env python3
"""Physical application button latency on the unchanged GEM body, with replay."""
import argparse,hashlib,json,os,re
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from desktop_mouse import schedule,raw_record
from make_data_disk import make
from gem_input_oracle import address,state,paint
from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
from test_gem_cursor import overlay
from measure_desktop import distribution
from sio_transaction_trace import read_events,BASE_HZ
from console_turn_profile import markers,flat_markers,analyze_events,Timeline
from bitmap_console_performance import native_markers


def analyze_timing(out,report,definition):
    points=report['points']
    events=read_events(out/'emulator.log');profile=analyze_events(events,definition,include_segments=True)
    timelines={};cpu=[(t,e) for t,e in events if e[0]=='cpu']
    times=lambda pc:[(t,e) for t,e in cpu if int(e[4],16)==pc]
    notices=times(points['pointer_notify']);routes=times(points['route']);returns=times(points['event_return'])
    align=lambda value:value+round((notices[0][0]-value)/(1<<32))*(1<<32)
    for window in report['windows'].values():
        window['start']=align(window['start']);window['end']=align(window['end'])
    for row in report['samples']:
        for key in ('submitted','captured_observed','visible'):
            row[key+'_raw']=row[key];row[key]=align(row[key])
        notices_in=[t for t,e in notices if row['submitted']<=t<=row['captured_observed']]
        require(len(notices_in)==1,'Ambiguous physical capture provenance')
        capture_tick=notices_in[0]
        routed=[(t,e) for t,e in routes if capture_tick<=t<=row['visible']]
        require(len(routed)==1,'Ambiguous application routing provenance')
        returned=[(t,e) for t,e in returns if routed[0][0]<=t<=row['visible'] and int(e[5],16)&2]
        require(len(returned)==1,'Ambiguous application button return')
        route_tick,route_event=routed[0];return_tick,return_event=returned[0]
        row.update(capture=capture_tick,route=route_tick,event_return=return_tick,
            caller_dp=int(return_event[9],16),presenter_dp=int(route_event[9],16))
        for metric,start,end in [('capture_to_route',capture_tick,route_tick),('route_to_return',route_tick,return_tick),
                                 ('return_to_visible',return_tick,row['visible']),('capture_to_visible',capture_tick,row['visible'])]:
            row[metric+'_ms']=(end-start)/BASE_HZ*1000
        for role in ('caller','presenter'):
            dp=row[role+'_dp']
            if dp not in timelines:timelines[dp]=Timeline(profile['segments'],dp)
            row[role+'_cpu_ms']=timelines[dp].measure(capture_tick,row['visible'])['charged_cpu_ms']
    metrics=('capture_to_route_ms','route_to_return_ms','return_to_visible_ms','capture_to_visible_ms','caller_cpu_ms','presenter_cpu_ms')
    report['timing']={load:{k:distribution([s[k] for s in report['samples'] if s['load']==load]) for k in metrics} for load in report['windows']}
    reads=[t for t,e in times(points['pointer_port_read'])]
    starts=[t for t,e in times(points['pointer_sample'])];ends=[t for t,e in times(points['pointer_sample_return'])]
    from bisect import bisect_left
    report['capture_cost']={}
    for load,window in report['windows'].items():
        selected=[t for t in reads if window['start']<=t<=window['end']]
        costs=[]
        for t in starts:
            if window['start']<=t<=window['end']:
                i=bisect_left(ends,t)
                if i<len(ends):costs.append((ends[i]-t)/BASE_HZ*1000)
        report['capture_cost'][load]=dict(sample_elapsed=distribution(costs),sample_gap=distribution([(b-a)/BASE_HZ*1000 for a,b in zip(selected,selected[1:])]))

def run(out,program,count=20,unobserved=False):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);foreign=json.loads((p['output'].parent/'c-image.json').read_text());sy=foreign['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    definition=markers(p,foreign,p['output'].parent/'drawing');definition['spans']={}
    points=flat_markers(definition)
    points['route']=native_markers(p,[('AESMOUSE_ROUTE','route')])['route']['entry']
    listing=next(path for path in (p['output'].parent/'drawing').glob('*.lst') if re.fullmatch(r'[0-9]+-input.lst',path.name))
    body=listing.read_text().replace('\r\n','\n').split('InputRun:',1)[1].split('.section ',1)[0]
    calls=re.findall(r'\\ ([0-9a-f]{6}) 22[.]+\s+jsl\s+long:evnt_multi\b',body)
    require(len(calls)==1,'Ambiguous InputRun event return')
    points['event_return']=sy['InputRun']+int(calls[0],16)+4
    for name in ('pointer_notify','pointer_sample','pointer_sample_return','pointer_port_read'):
        points[name]=p['labels'][name]
    names=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MOUSE_TRACE','EXEC816_MASK_TRACE')
    saved_env={name:os.environ.pop(name,None) for name in names}
    if not unobserved:
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MOUSE_TRACE='1',
                          EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in set(points.values())))
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i&255 for i in range(32768)))
    make(out/'disk.atr',media,binary_names={'DATA.BIN'},filesystem='sdfs')
    report=dict(slice='AI7',tier='development',qualification=False,status='running',observer=not unobserved,
                image_sha256=sha256(p['xex']),pin=PIN,samples=[],windows={},points=points,cost_definition=definition,
                scope='Unchanged production GEM application and binding; test root supplies continuous verified reads or console writes. Visible time observes full control pixels in completed scanout, an upper bound including frame scanout. One physical edge is outstanding at a time; no PI4/HY4 closure claim.')
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(out/'disk.atr'));b._cmd_ok('MOUSE ST')
            b.config('diskemu','generic56k')
            get=lambda a,n=2:int.from_bytes(b.memdump(a,n),'little')
            clock=lambda:b.eval_expr('@clk')&0xffffffff
            capture=p['build']['memory']['input_storage']['POINTER_CAPTURE']
            fault=int(re.search(r'al ([0-9A-Fa-f]+) \.heap_fault$',(p['output']/'hosted.lbl').read_text(),re.M)[1],16)+2
            def reach(condition):
                marker=p['labels']['native_irq'];b.bp_clear_all();b.bp_set(marker,condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                b.bp_set(fault,condition=f'@xpc=${fault:x}')
                original=b.regs
                def regs():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==fault:
                        raise RuntimeError('Native assertion '+r['A']+' at input-load check '+str(get(at('INPUTLOAD','checks')))+'; heap before/retired='+str([get(at('INPUTLOAD',n),4) for n in ('available','retiredAvailable')]))
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Input load guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=regs
                try:run_to(b,marker,condition=condition,timeout=240,frame_limit=12000)
                finally:b.regs=original
            def frames(n=3):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(level):b._cmd_ok('MOUSE AT 2000 0 0 '+str(level));frames(3)
            font=font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
            rgb=bytes((v&254)+(v>>7) for v in PALETTE)
            colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
            def expected(down):
                s=state(b,sy,1);s['armed']=down
                r=Raster(font);paint(r,s,True);packed=overlay(r,position)
                x,y,_,_=s['work'];bounds=(x+8,y+48,x+136,y+72)
                want=b''.join(colors[(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
                    for yy in range(bounds[1],bounds[3]) for xx in range(bounds[0],bounds[2]))
                return bounds,want
            def visible(bounds,want):
                f=b.rawscreen(str(out/'scanout.bgra'));raw=(out/'scanout.bgra').read_bytes()
                actual=b''.join(raw[y*f.stride+(x+16)*4:y*f.stride+(x+16)*4+3]
                    for y in range(bounds[1],bounds[3]) for x in range(bounds[0],bounds[2]))
                return actual==want,hashlib.sha256(actual).hexdigest()
            def before(bridge):
                # Start tracing in a Task, before the native entry machinery.
                if not unobserved:b.profile_start('basicblock')
                reach('dw($%x)=1'%at('INPUTLOAD','ready'));frames(80)
                x,y,_,_=state(b,sy,1)['work'];move(x+96,y-10);edge(1);edge(0);frames(30)
                move(x+48,y+60);frames(8)
                for load,mode in (('idle',0),('scroll',2),('disk',3)):
                    b.poke16(at('INPUTLOAD','mode'),mode)
                    reach('dw($%x)=%d'%(at('INPUTLOAD','runningMode'),mode))
                    before_counts={n:get(at('INPUTLOAD',n)) for n in ('reads','writes')}
                    begin=clock()
                    for i in range(count):
                        down=1-(i&1);bounds,want=expected(down)
                        head=b.peek(capture+1)[0];submitted=clock()
                        b._cmd_ok(f'MOUSE AT {2000+(i*379)%7000} 0 0 {down}')
                        reach('db($%x)!=%d'%(capture+1,head));captured=clock()
                        raw=raw_record(b,p,capture,head)
                        require(raw[11]==down,'Wrong captured physical edge')
                        row=dict(load=load,index=i,buttons=down,record=raw.hex(),submitted=submitted,captured_observed=captured)
                        for attempt in range(300):
                            okay,digest=visible(bounds,want)
                            if okay and get(address(sy,1,'armed'))==down:break
                            reach('@clk>=%d'%(clock()+1800))
                        require(okay and get(address(sy,1,'armed'))==down,'Button feedback did not complete')
                        row.update(visible=clock(),scanout_sha256=digest,polls=attempt+1)
                        report['samples'].append(row)
                        # Physical levels exceed the supported 10-ms hold time.
                        frames(1)
                    if mode:
                        metric='writes' if mode==2 else 'reads'
                        reach('dw($%x)>%d'%(at('INPUTLOAD',metric),before_counts[metric]))
                    end=clock();after={n:get(at('INPUTLOAD',n)) for n in ('reads','writes')}
                    report['windows'][load]=dict(start=begin,end=end,before=before_counts,after=after,
                        live_tasks=get(p['build']['task_storage']['LIVE'],1))
                    if mode:require(after['writes' if mode==2 else 'reads']>before_counts['writes' if mode==2 else 'reads'],'Load made no progress')
                    print(load,'physical edges',count,'pass',flush=True)
                require(state(b,sy,1)['activations']==count*3//2,'Missing or duplicate activation')
                require(state(b,sy,0)['activations']==0,'Input crossed applications')
                panel=next((d['address'] for d in p['image']['data'] if '_DESKAPP_WINDOWID_' in d['name']),None)
                if panel is not None and get(panel,4):
                    # Rapid keys and a click continue through the same app while
                    # the root performs verified reads. This is outside timings.
                    count_before=state(b,sy,1)['activations']
                    edge(1)
                    for key in ('A','B','C'):
                        b._cmd_ok('KEY '+key+' down');frames(2)
                        b._cmd_ok('KEY '+key+' up');frames(2)
                    edge(0)
                    reach('dw($%x)=%d'%(address(sy,1,'activations'),count_before+1));frames(30)
                    require(state(b,sy,1)['key']=='Key: 2E63','Rapid keys while drawing/disk lost their recipient')
                    require(state(b,sy,0)['key']=='Key: 0000','Rapid keys crossed applications')
                    reads_before=get(at('INPUTLOAD','reads'));updates=get(at('DESKAPP','updates'))
                    move(536,86);edge(1);edge(0);frames(20)
                    move(480,128);edge(1);edge(0)
                    reach('dw($%x)>%d'%(at('DESKAPP','updates'),updates));frames(30)
                    require(get(at('INPUTLOAD','reads'))>reads_before,'Native panel stopped disk progress')
                    report['native_panel']=dict(updates_before=updates,updates_after=get(at('DESKAPP','updates')),
                        live_tasks=get(p['build']['task_storage']['LIVE'],1),disk_reads=get(at('INPUTLOAD','reads'))-reads_before)
                    require(report['native_panel']['live_tasks']==7,'Native-panel fixture exceeded its Task budget')
                report['models']=[state(b,sy,i) for i in range(2)]
                b.poke16(at('INPUTLOAD','mode'),9)
                reach('dw($%x)=2'%at('INPUTLOAD','ready'))
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            ownership(b,p,p['output'])
            if not unobserved:b.profile_stop()
            require(get(sy['GEMInputsFailure'])==0,'Application failure')
        if not unobserved:analyze_timing(out,report,definition)
        report['observed_feedback']={load:distribution([(s['visible']-s['captured_observed'])/BASE_HZ*1000 for s in report['samples'] if s['load']==load]) for load in report['windows']}
        report['status']='pass'
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:
        for key,value in saved_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=20);parser.add_argument('--unobserved',action='store_true')
    args=parser.parse_args();require(args.count>0 and args.count%2==0,'Use a positive even edge count')
    run(args.output.resolve(),args.program.resolve(),args.count,args.unobserved)
