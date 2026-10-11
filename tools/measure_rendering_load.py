#!/usr/bin/env python3
"""Matched public VDI loads, passive call timing and physical Panel/pointer feedback.

The diagnostic app is loaded from a development-only WORK disk. Boot and SYS
come from the unchanged exact ZIP. Only the app's documented mode word is set
by the observer; normal GEM calls, input and scheduling do all the measured work.
"""
import argparse,gzip,json,os,shutil,zipfile
from pathlib import Path
from collections import Counter
from bisect import bisect_left,bisect_right
from native_program import ROOT,read_build,require,sha256
from test_demo import run
from build_c_program import build
from make_data_disk import make
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import MODELS,instances,symbols
from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
from test_gem_cursor import ARROW
from loadable_gem_feedback import measure
from measure_desktop import distribution
from sio_transaction_trace import BASE_HZ
from g4bench_trace import definition,marker_pcs,read_trace,loaded_markers,calls
from console_turn_profile import Timeline,analyze_events
from stack_budget import stack_usage

NAMES={1:'even64',2:'even80',3:'odd64',4:'odd79',5:'even-bar',6:'odd-bar'}


class Load:
    def __init__(self,out,modes,count,pointer_waits=(15,)):
        self.out=out;self.modes=modes;self.count=count;self.pointer_waits=pointer_waits

    def prepare_work(self,path,item):
        source=self.out/'load-media';source.mkdir()
        shutil.copyfile(self.out/'bitmap-console/apps/renderload/program.app',source/'RENDER.APP')
        make(path,source,binary_names={'RENDER.APP'},sector_bytes=item['sector_bytes'],
             filesystem=item['filesystem'],sectors=item['sectors'])
        self.media=dict(path=path.name,sha256=sha256(path),scope='Development WORK fixture only')

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        panel=symbols(b,s.p,directory,'panel',s.number(shared['GEMDesktopChildren'],4))['GEMPanel']
        cursor=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(cursor(n),2) for n in ('cursorX','cursorY')]
            position=schedule(b,s.p,old,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(cursor('cursorX'),position[0],cursor('cursorY'),position[1]))
            s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(35)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        menus.select('Counter');menus.close();s.frames(100)
        menus.select('Shell');previous=s.begin('RUN WORK:RENDER.APP');s.ready(previous);s.result()
        job=s.at('job');identity=s.number(job,4)
        self.live=next(a for a in instances(b,s.p,directory) if a['name']=='renderload' and a['identity']==identity)
        sy=self.live['symbols'];s.rendezvous('dw($%x)=1'%sy['RenderReady']);s.frames(100)
        menus.select('Control Panel');move(600,80);s.frames(60)
        font=font_bytes(self.out/s.manifest['font_source'])
        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
        colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
        self.results=[];b.profile_start()
        for mode in self.modes:
            b.poke16(sy['RenderMode'],mode)
            s.rendezvous('dw($%x)=%d'%(sy['RenderPhase'],mode))
            at=sy['RenderCalls']+4*mode
            s.rendezvous('dw($%x)>=3'%at)
            start=b.eval_expr('@clk')&0xffffffff;initial=s.number(at,4)
            s.rendezvous('dw($%x)>=%d'%(at,initial+self.count))
            end=b.eval_expr('@clk')&0xffffffff
            require(s.number(sy['RenderFailed'],2)==0,'Load app failed')
            s.rendezvous('dw($%x)=0'%sy['RenderBusy'])
            model=Raster(font);model.clip=(8,160,631,231)
            if mode<=4:
                count=64 if mode in (1,3) else 80 if mode==2 else 79
                model.text=4;model.apply(8,[9 if mode>=3 else 8,230],[65+i%26 for i in range(count)])
                region=(8,224,632,232)
            else:
                model.fill=4;model.apply(11,[9 if mode==6 else 8,160,108 if mode==6 else 107,209])
                region=(8,160,110,212)
            path=self.out/'load-pixels.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            for y in range(region[1],region[3]):
                for x in range(region[0],region[2]):
                    offset=y*frame.stride+(x+16)*4
                    require(raw[offset:offset+3]==colors[model.pixels[y*640+x]],f'{NAMES[mode]} pixel {x},{y}')
            record=dict(mode=mode,name=NAMES[mode],steady_start=start,steady_end=end,pixels=(region[2]-region[0])*(region[3]-region[1]))
            if mode in (2,4,6):
                before=s.number(at,4);measure(s,panel,move,NAMES[mode],count=self.count)
                record['panel']=s.saved['loaded_panel_feedback'][NAMES[mode]]
                move(600,80);samples=[]
                for i in range(self.count):
                    target=(602 if i%2==0 else 600,80)
                    started=b.eval_expr('@clk')&0xffffffff
                    old=[s.number(cursor(n),2) for n in ('cursorX','cursorY')]
                    position=schedule(b,s.p,old,target);s.saved['pointer']=position
                    s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(cursor('cursorX'),position[0],cursor('cursorY'),position[1]))
                    for attempt in range(20):
                        path=self.out/'pointer-load.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
                        if all(raw[(target[1]+y)*frame.stride+(target[0]+x+16)*4: (target[1]+y)*frame.stride+(target[0]+x+16)*4+3]==
                               colors[15 if char=='X' else 0]
                               for y,line in enumerate(ARROW) for x,char in enumerate(line) if char!='.'):break
                        s.frames(1)
                    else:raise RuntimeError('Pointer did not reach scanout')
                    samples.append(((b.eval_expr('@clk')-started)&0xffffffff)/BASE_HZ*1000)
                    s.frames(self.pointer_waits[i%len(self.pointer_waits)])
                record['pointer']=dict(samples_ms=samples,wait_frames=list(self.pointer_waits),**distribution(samples),scope='Small physical motion to matching arrow pixels; frame-granular polling')
                record['concurrent_calls']=s.number(at,4)-before
                require(record['concurrent_calls']>=self.count,'Rendering made no progress during feedback')
            self.results.append(record)
            print('Render load',NAMES[mode],{k:{f:v[f] for f in ('median_ms','p95_ms','max_ms')} for k,v in record.items() if k in ('panel','pointer')},flush=True)
        b.poke16(sy['RenderMode'],0);s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(sy['RenderPhase'],sy['RenderBusy']))
        b.profile_stop();require(s.number(sy['RenderFailed'],2)==0,'Load failed on completion')
        s.saved['gem_stacks']=stack_usage(b,s.p['build']['memory'])
        (self.out/'load-samples.json').write_text(json.dumps(dict(live=self.live,rows=self.results,media=self.media),indent=2)+'\n')
        menus.select('GEM render load');menus.close();s.rendezvous('db($%x)=3'%(job+12));s.frames(100)
        menus.select('Shell');s.command('HELLO',b'Hello from disk!');s.save_screen(self.out/'boot-smoke.png')
        s.saved['integration']=dict(profile='rendering-load',closed=True,shell=True)
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def analyze(out,d,probe):
    events=read_trace(out/'emulator.log',d,probe.live)
    entries,returns=loaded_markers(d,probe.live)
    draw=next(pc for pc,name in entries.items() if name=='BenchDraw')
    dps={int(e[9],16) for _,e in events if int(e[4],16)==draw};require(len(dps)==1,'Load Task changed')
    dp=dps.pop();spans,unfinished=calls(events,entries,returns,dp)
    timeline=Timeline(analyze_events(events,d['timeline'],include_segments=True)['segments'],dp)
    kind='drawing_borrow' if 'drawing_borrow' in entries.values() else 'GemDrawingBorrow'
    all_draws=sorted((s for s in spans if s['kind']=='BenchDraw'),key=lambda s:s['start'])
    starts=[s['start'] for s in all_draws];all_borrows={mode:[] for mode in NAMES}
    all_held={mode:[] for mode in NAMES}
    admissions=sorted((s for s in spans if s['kind']=='DisplayEnter'),key=lambda s:s['start'])
    releases=sorted((s for s in spans if s['kind']=='DisplayLeave'),key=lambda s:s['start'])
    admission_starts=[s['start'] for s in admissions];release_starts=[s['start'] for s in releases]
    for borrow in (s for s in spans if s['kind']==kind):
        i=bisect_right(starts,borrow['start'])-1
        if i>=0 and borrow['end']<=all_draws[i]['end']:
            mode=all_draws[i]['argument']
            all_borrows[mode].append((borrow['end']-borrow['start'])*1000/BASE_HZ)
            enter=admissions[bisect_left(admission_starts,borrow['start'])]
            leave=releases[bisect_left(release_starts,borrow['start'])]
            require(borrow['start']<=enter['start']<enter['end']<=leave['start']<leave['end']<=borrow['end'],'Incomplete measured borrow lifecycle')
            all_held[mode].append((leave['start']-enter['end'])*1000/BASE_HZ)
    for row in probe.results:
        row['all_activity']=dict(
            completion_elapsed_ms=distribution([(s['end']-s['start'])*1000/BASE_HZ for s in all_draws if s['argument']==row['mode']]),
            borrow_elapsed_ms=distribution(all_borrows[row['mode']]),
            held_after_admission_ms=distribution(all_held[row['mode']]),
            scope='All completed drawing calls of this mode, including warmup and physical-input cohorts; clear-on-mode-change excluded.')
        # The bridge trace has an extended clock; debugger @clk is 32-bit.
        start=row['steady_start']+round((events[0][0]-row['steady_start'])/(1<<32))*(1<<32)
        end=start+((row['steady_end']-row['steady_start'])&0xffffffff)
        selected=[s for s in spans if s['kind']=='BenchDraw' and s['argument']==row['mode'] and start<=s['start']<s['end']<=end]
        require(len(selected)>=probe.count-1,'Missing steady load samples')
        measurements=[];borrows=[];held=[];counts=[]
        for call in selected:
            measurements.append(timeline.measure(call['start'],call['end']))
            children=[s for s in spans if call['start']<=s['start']<s['end']<=call['end']]
            counts.append(dict(Counter(s['kind'] for s in children)))
            for borrow in [s for s in children if s['kind']==kind]:
                borrows.append(timeline.measure(borrow['start'],borrow['end']))
                enter=[s for s in children if s['kind']=='DisplayEnter' and borrow['start']<=s['start']<s['end']<=borrow['end']]
                leave=[s for s in children if s['kind']=='DisplayLeave' and borrow['start']<=s['start']<s['end']<=borrow['end']]
                require(len(enter)==len(leave)==1,'Incomplete borrow lifecycle')
                held.append(timeline.measure(enter[0]['end'],leave[0]['start']))
        row['completion']={metric:distribution([s[metric] for s in measurements]) for metric in measurements[0]}
        row['borrow']={metric:distribution([s[metric] for s in borrows]) for metric in borrows[0]}
        row['held_after_admission']={metric:distribution([s[metric] for s in held]) for metric in held[0]}
        row['calls_per_operation']={name:{k.removesuffix('_ms'):v for k,v in distribution([c.get(name,0) for c in counts]).items()} for name in ('GemDrawingBorrow','GemDrawingSolidBorrow','_VbxeTextUpload','_VbxeUpload','start','GemSolidFill','solid_record')}
        if 'pointer' in row:
            row['pointer']['scope']='Physical positioning schedule to matching arrow scanout; includes the helper’s 70,000-cycle (39.47 ms) delay for the mild profile, with frame-granular polling. Compare matched schedules, not raw pointer-driver latency.'
        if row['mode'] in (1,3):
            require(all(c.get('GemDrawingBorrow')==1 and c.get('_VbxeTextUpload')==1 and c.get('start')==1 for c in counts),'Complete 64-cell row lost its single launch')
    with gzip.open(out/'cpu-trace.log.gz','wt') as f:
        f.write('[SIOTXN] anchor '+str(int(events[0][0]))+'\n')
        for _,fields in events:f.write('[SIOTXN] '+' '.join(fields)+'\n')
    return dict(rows=probe.results,trace_sha256=sha256(out/'cpu-trace.log.gz'),task_dp=dp,unfinished=unfinished,
        scope='Public call includes its own UPDATE pair. Steady cohorts exclude warmup and physical-input cohorts. Borrow includes admission; held interval excludes DisplayEnter/Leave. Long inputs clip at framed work right=632.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--count',type=int,default=40)
    p.add_argument('--modes',default='1,2,3,4,5,6');p.add_argument('--analyze',action='store_true')
    p.add_argument('--pointer-waits',default='15',help='Comma-separated inter-motion frame waits for a matched phase sweep')
    args=p.parse_args()
    out=args.output.resolve()
    if args.analyze:
        saved=json.loads((out/'load-samples.json').read_text())
        probe=Load(out,[],args.count);probe.live=saved['live'];probe.results=saved['rows'];probe.media=saved['media']
        report=json.loads((out/'load-results.json').read_text())
        if not (out/'load-capture.json').exists():
            (out/'load-capture.json').write_text(json.dumps(report,indent=2)+'\n')
        profile=analyze(out,json.loads((out/'trace-definition.json').read_text()),probe)
        report.update(status='pass',profile=profile,development_media=probe.media,analysis_sha256=sha256(Path(__file__)))
        if 'error' in report:
            report['capture_analysis_error']=report.pop('error')
            report['execution_scope']='test_demo.run returned normally before the original observer window analysis failed. Its return dictionary was not retained; exact-ZIP machine/stack/lifetime evidence is also recorded by the separate final walkthrough.'
        (out/'load-results.json').write_text(json.dumps(report,indent=2)+'\n');return
    require(args.bundle is not None,'--bundle is required for capture')
    require(not out.exists(),'Use a fresh output directory')
    shutil.copytree(args.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','g4bench-extracted-*','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    directory=out/'bitmap-console';app=build(directory/'apps/renderload',[ROOT/'tests/programs/gem_render_load.c'])
    MODELS['renderload']=('RenderReady',0,0)
    d=definition(read_build(out),json.loads((directory/'c-image.json').read_text()),app,directory,
                 app_names=('BenchDraw',),app_directory=directory/'apps/renderload')
    (out/'trace-definition.json').write_text(json.dumps(d,indent=2)+'\n')
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in marker_pcs(d)))
    probe=Load(out,[int(v) for v in args.modes.split(',')],args.count,[int(v) for v in args.pointer_waits.split(',')])
    report=dict(status='running',tier='development',qualification=False,archive_sha256=sha256(out/'exec816-demo.zip'),application_sha256=app['sha256'],runner_sha256=sha256(Path(__file__)))
    try:
        result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
        report['run']=result
        report.update(profile=analyze(out,d,probe),development_media=probe.media,status='pass',analysis_sha256=sha256(Path(__file__)))
    except BaseException as error:
        report.update(status='fail',error=type(error).__name__+': '+str(error));raise
    finally:(out/'load-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
