#!/usr/bin/env python3
"""Ordinary GEM input: pixels, physical controls, events and retirement."""
import argparse,json,struct
from pathlib import Path
import adapter_state as adapter
from native_program import read_build,require,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from desktop_mouse import schedule
from gem_render_oracle import Raster,font_bytes
from test_desktop_presentation import desktop, rectangle,frame
from test_gem_interactive import pixels
from test_gem_cursor import overlay
from generate_aes_server import ABI


def run(out,program):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);f=json.loads((p['output'].parent/'c-image.json').read_text());sy=f['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    report=dict(status='running',slice='AI6',tier='development',qualification=False,build=p['build'],cases=[])
    from stack_budget import stack_usage
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def get(a,n=2):return int.from_bytes(b.memdump(a,n),'little')
            def c(n,i=0):return get(sy[n]+i*2)
            from gem_input_oracle import address,state,paint
            def app(i,field):return address(sy,i,field)
            def model(i):return state(b,sy,i)
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Input guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
            def frames(n=4):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def until(a,value=1,op='='):reach('dw($%x)%s%d'%(a,op,value))
            def pause(i):
                b.poke16(sy['InputPause']+i*2,1);until(sy['InputHeld']+i*2)
            def resume(i):b.poke16(sy['InputPause']+i*2,0)
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames()
            def message(i,kind,rect=(0,0,0,0)):
                old=c('InputPostDone')
                for index,value in enumerate((ABI['constants'][kind],0,0,0,*rect)):
                    b.poke16(sy['InputPostWords']+index*2,value & 65535)
                b.poke16(sy['InputPostCommand'],i+1)
                until(sy['InputPostDone'],old,'>')
                require(c('InputPostStatus')==1,'Message publication failed')
            def snapshot(name,focused=True):
                frames(60)
                contexts=get(sy['contexts'],4);directory=get(contexts+128,4);top=get(directory+10)
                ids=[get(app(i,'window')) for i in range(2)]
                order=[1,0] if top==ids[0] else [0,1]
                r=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
                desktop(r);frame(r,(32,24,560,208),b'Exec816 Shell',focused and top==0)
                states=[]
                for i in order:
                    if not get(app(i,'ready')):continue
                    current=model(i);paint(r,current,focused and top==ids[i]);states.append(current)
                (out/'last-model.json').write_text(json.dumps(dict(name=name,states=states,top=top),indent=2)+'\n')
                digest=pixels(b,out,overlay(r,position))
                report['cases'].append(dict(name=name,states=states,top=top,pixels=digest))
                print(name,'pixels pass',flush=True)
            def before(b):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                until(at('INPUTTEST','ready'));frames(150)
                pause(0);pause(1);move(620,232);snapshot('initial-timers')
                require(c('GEMInputsFailure')==0,'Input startup failed')
                require(all(c('InputEvents',i)>1 for i in range(2)),'Timers did not advance')
                # Only the focused work area starts a control gesture.
                resume(1);message(1,'WM_TOPPED');frames(60)
                x,y,_,_=model(1)['work']
                move(x+48,y+60);edge(1);until(app(1,'armed'));pause(1)
                snapshot('pressed')
                require(model(1)['activations']==0,'Press activated before release')
                move(620,232);snapshot('held-outside')
                resume(1);edge(0);until(app(1,'down'),0);pause(1)
                require(model(1)['activations']==0 and model(1)['armed']==0,'Outside release activated')
                snapshot('outside-cancel')
                resume(1);move(x+48,y+60);edge(1);edge(0)
                until(app(1,'activations'),1);pause(1);snapshot('released-inside')
                # Ctrl-C is a translated GEM shortcut, not console cancellation.
                resume(1);b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY C down');frames(3)
                b._cmd_ok('KEY C up');b._cmd_ok('KEY CTRL up');frames(6);pause(1)
                require(model(1)['key']=='Key: 2E03','Wrong GEM Ctrl-C label: '+model(1)['key'])
                snapshot('translated-shortcut')
                require(model(0)['key']=='Key: 0000','Keyboard crossed recipient')
                # Hold actual BEG_UPDATE while a quick content click queues.
                resume(1);b.poke16(sy['InputPaintPause'],1)
                message(1,'WM_REDRAW',(0,0,640,240));until(sy['InputPaintHeld'])
                move(x+48,y+60);edge(1);edge(0)
                b.poke16(sy['InputPaintPause'],0)
                until(app(1,'activations'),2);pause(1);snapshot('quick-click-during-redraw')
                # Overflow the keyboard FIFO while a button remains armed.
                resume(1);edge(1);until(app(1,'armed'));pause(1)
                for _ in range(18):
                    b._cmd_ok('KEY A down');frames(3);b._cmd_ok('KEY A up');frames(3)
                resume(1);until(app(1,'armed'),0);edge(0);until(app(1,'down'),0);pause(1)
                require(model(1)['activations']==2,'Input loss activated the control')
                snapshot('input-loss-reset')
                resume(1);edge(1);edge(0);until(app(1,'activations'),3);pause(1)
                snapshot('release-rearmed')
                # An inactive content click only tops; it cannot activate A.
                resume(0);ax,ay,_,_=model(0)['work'];move(ax+48,ay+60);edge(1);edge(0)
                frames(60);pause(0)
                require(model(0)['activations']==0,'Activation click reached content')
                snapshot('activation-isolated')
                resume(0);edge(1);until(app(0,'armed'));edge(0);until(app(0,'activations'),1);pause(0)
                snapshot('independent-activation')
                # A physical title drag moves through WM_MOVED.
                resume(0);old=c('InputMessages',2)
                move(ax+96,ay-10);edge(1);move(ax+113,ay+1);edge(0)
                until(sy['InputMessages']+4,old,'>');frames(60);pause(0)
                require(model(0)['work'][:2]==[ax+17,ay+11],'Physical move lost coordinates')
                move(620,232);snapshot('physical-move')
                # Escape cancels an armed button without closing the app.
                resume(0);ax,ay,_,_=model(0)['work'];move(ax+48,ay+60);edge(1);until(app(0,'armed'))
                b._cmd_ok('KEY BREAK down');frames(3);b._cmd_ok('KEY BREAK up');frames(6)
                until(app(0,'armed'),0);edge(0);until(app(0,'down'),0);pause(0)
                require(model(0)['activations']==1,'Escape activated the button')
                snapshot('escape-cancel')
                resume(1);old_tick=model(1)['tick'];frames(75);pause(1)
                require(c('InputEvents',1)>0,'Timer/message progress stopped')
                # Physical closer retires one owner; repeated startup returns heap.
                resume(0);move(ax,ay-10);edge(1);edge(0)
                until(sy['GEMInputsDone'],1,'>=');move(620,232)
                resume(1);frames(80);pause(1)
                snapshot('physical-close',focused=False)
                for iteration in range(2):
                    resume(0);resume(1);b.poke16(at('INPUTTEST','mode'),1)
                    until(at('INPUTTEST','restarts'),iteration+1);frames(120)
                    pause(0);pause(1);snapshot('restart-'+str(iteration+1))
                report['events']=[c('InputEvents',i) for i in range(2)]
                report['both_ready']=[c('InputBoth',i) for i in range(2)]
                resume(0);resume(1);b.poke16(at('INPUTTEST','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output'])
            report['native_checks']=get(at('INPUTTEST','checks'))
            require(c('GEMInputsFailure')==0,'Input failed')
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            report['status']='pass'

    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.program.resolve())
