#!/usr/bin/env python3
"""Ordinary GEM counter: pixels, physical controls, events and retirement."""
import argparse,json,struct
from pathlib import Path
import adapter_state as adapter
from native_program import read_build,require,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from desktop_mouse import schedule
from gem_render_oracle import Raster,font_bytes
from test_desktop_presentation import rectangle,frame
from test_gem_interactive import pixels
from test_gem_cursor import overlay
from generate_aes_server import ABI


def run(out,program):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);f=json.loads((p['output'].parent/'c-image.json').read_text());sy=f['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    report=dict(status='running',slice='WA5',tier='development',qualification=False,build=p['build'],cases=[])
    from counter_timing import setup,restore,result
    timing=setup(p,f)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def get(a,n=2):return int.from_bytes(b.memdump(a,n),'little')
            def c(n,i=0):return get(sy[n]+i*2)
            def app(i,field):return sy['GEMCounters']+196*i+dict(id=4,window=8,ready=12,count=14,paints=18,work=38)[field]
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Counter guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
            def frames(n=4):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def until(a,value=1,op='='):reach('dw($%x)%s%d'%(a,op,value))
            def pause(i):
                b.poke16(sy['CounterPause']+i*2,1);until(sy['CounterHeld']+i*2)
            def resume(i):b.poke16(sy['CounterPause']+i*2,0)
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames()
            def message(i,kind,rect=(0,0,0,0)):
                old=c('CounterPostDone')
                for index,value in enumerate((ABI['constants'][kind],0,0,0,*rect)):
                    b.poke16(sy['CounterPostWords']+index*2,value & 65535)
                b.poke16(sy['CounterPostCommand'],i+1)
                until(sy['CounterPostDone'],old,'>')
                require(c('CounterPostStatus')==1,'Message publication failed')
            def snapshot(name,focused=True):
                frames(60)
                contexts=get(sy['contexts'],4);directory=get(contexts+128,4);top=get(directory+10)
                ids=[get(app(i,'window')) for i in range(2)]
                order=[1,0] if top==ids[0] else [0,1]
                r=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
                rectangle(r,(0,0,640,240),8);frame(r,(32,24,560,208),b'Exec816 Shell',focused and top==0)
                states=[]
                for i in order:
                    if not get(app(i,'ready')):continue
                    x,y,w,h=struct.unpack('<4h',b.memdump(app(i,'work'),8));count=get(app(i,'count'),4)
                    frame(r,(x-8,y-16,x+w+8,y+h+8),b'Counter B' if i else b'Counter A',focused and top==ids[i],close=True)
                    r.clip=(x,y,x+w-1,y+h-1);r.text=2 if i else 4
                    r.apply(8,(x+8,y+14),b'GEM counter')
                    r.apply(8,(x+8,y+30),('Count: %06d'%count).encode())
                    r.clip=(0,0,639,239)
                    states.append(dict(instance=i,work=[x,y,w,h],count=count,paints=get(app(i,'paints'),4)))
                digest=pixels(b,out,overlay(r,position))
                report['cases'].append(dict(name=name,states=states,top=top,pixels=digest))
                print(name,'pixels pass',flush=True)
            def before(b):
                b.profile_start()
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                until(at('COUNTERTEST','ready'));frames(150)
                pause(0);pause(1);move(620,232);snapshot('initial-timers')
                require(c('GEMCountersFailure')==0,'Counter startup failed')
                require(all(get(app(i,'count'),4)>0 for i in range(2)),'Timers did not advance')
                # Top request is deferred while the owner is outside its event loop.
                top_before=get(get(get(sy['contexts'],4)+128,4)+10)
                inactive=0 if top_before==get(app(1,'window')) else 1
                x,y,_,_=struct.unpack('<4h',b.memdump(app(inactive,'work'),8))
                old=c('CounterMessages',inactive*4+1)
                move(x+96,y-10);edge(1);edge(0);frames(20)
                require(get(get(get(sy['contexts'],4)+128,4)+10)==top_before,'Top committed before application acknowledgment')
                resume(inactive);until(sy['CounterMessages']+inactive*8+2,old,'>');frames(60);pause(inactive)
                move(620,232);snapshot('acknowledged-top')
                # A physical pixel-position title drag must reach the same body.
                resume(inactive);old=c('CounterMessages',inactive*4+2)
                move(x+96,y-10);edge(1);move(x+113,y+1);edge(0)
                until(sy['CounterMessages']+inactive*8+4,old,'>');frames(80);pause(inactive)
                work=struct.unpack('<4h',b.memdump(app(inactive,'work'),8))
                require(work[:2]==(x+17,y+11),'Counter drag changed pixel coordinates: '+str(work))
                resume(1-inactive);frames(100);pause(1-inactive)
                move(620,232);snapshot('physical-move')
                # Cover A exactly with B, keep A's model ticking without pixels.
                ax,ay,_,_=struct.unpack('<4h',b.memdump(app(0,'work'),8))
                resume(1);message(1,'WM_MOVED',(ax-8,ay-16,208,104));message(1,'WM_TOPPED')
                frames(180);pause(1);resume(0);before_count=get(app(0,'count'),4)
                frames(180);pause(0)
                require(get(app(0,'count'),4)>before_count,'Covered application model stopped')
                snapshot('fully-covered-model')
                resume(1);message(1,'WM_MOVED',(241,97,208,104));frames(140);pause(1)
                resume(0);frames(100);pause(0);snapshot('latest-model-exposed')
                # Let an armed alarm expire while a redraw queues, then resume
                # the same pending evnt_multi decision. Both bits must be handled.
                old=c('CounterBoth',0);b.poke16(sy['CounterTimerPause'],1);resume(0)
                until(sy['CounterTimerHeld']);frames(80)
                message(0,'WM_REDRAW',(0,0,640,240))
                b.poke16(sy['CounterTimerPause'],0)
                until(sy['CounterBoth'],old,'>');frames(80);pause(0)
                snapshot('simultaneous-message-timer')
                # Several retained redraws while delayed cannot erase later work.
                for _ in range(3):message(0,'WM_REDRAW',(0,0,640,240))
                resume(0);frames(160);pause(0);snapshot('repeated-redraw')
                # Close B with its physical closer while A remains live.
                resume(1);move(241+8,97+6);edge(1);edge(0)
                until(sy['GEMCountersDone'],1,'>=');move(620,232);resume(0);frames(100);pause(0)
                snapshot('physical-close',focused=False)
                for iteration in range(2):
                    resume(0);resume(1);b.poke16(at('COUNTERTEST','mode'),1)
                    until(at('COUNTERTEST','restarts'),iteration+1);frames(120)
                    pause(0);pause(1);snapshot('restart-'+str(iteration+1))
                report['events']=[c('CounterEvents',i) for i in range(2)]
                report['both_ready']=[c('CounterBoth',i) for i in range(2)]
                resume(0);resume(1);b.poke16(at('COUNTERTEST','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output'])
            report['native_checks']=get(at('COUNTERTEST','checks'))
            require(c('GEMCountersFailure')==0,'Counter failed')
            b.profile_stop()
            report['status']='pass'
        report['timing']=result(out,timing)
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:
        restore(timing)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.program.resolve())
