#!/usr/bin/env python3
"""Matched panel workloads with optional direct-drawing GEM clients."""
import argparse,json
from collections import deque
from pathlib import Path
import adapter_state as adapter
from native_program import read_build,require,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from desktop_mouse import schedule
from make_data_disk import make
from console_model import read_cells
from generate_console import constants
from bitmap_console_oracle import Terminal
from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
from desktop_oracle import compose
from test_gem_interactive import pixels
from sio_transaction_trace import read_events,BASE_HZ
from measure_desktop import distribution
import counter_timing


def run(out,program,counters,trace=True):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);foreign=json.loads((p['output'].parent/'c-image.json').read_text());sy=foreign['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    media=out/'media/TOOLS/SUB';media.mkdir(parents=True,exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk=out/'disk.atr';make(disk,out/'media',binary_names={'TOOLS/SUB/DATA.BIN'},filesystem='sdfs')
    report=dict(status='running',tier='development',qualification=False,counters=counters,build=p['build'],loads=[],pixels=[])
    config=counter_timing.setup(p,foreign,lean=True,notifications=True)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.mount(0,str(disk));b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
            report['machine']=verify_machine(b,ROM,PIN)
            get=lambda a,n=2:int.from_bytes(b.memdump(a,n),'little')
            app=lambda i,f:sy['GEMCounters']+196*i+dict(window=8,ready=12,count=14,paints=18,work=38)[f]
            def reach(condition):
                marker=p['labels']['native_irq'];b.bp_clear_all()
                condition=f'(@xpc=${marker:x})&({condition})'
                b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def registers():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Coexistence guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=registers
                try:run_to(b,marker,condition=condition,frame_limit=12000,timeout=240)
                finally:b.regs=original
            def frames(n=3):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def until(a,v=1,op='='):reach(f'dw(${a:x}){op}{v}')
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(v):
                b._cmd_ok('MOUSE AT 2000 0 0 '+str(v))
                until(at('DESKINPUT','buttons'),v)
                if v:frames(4)
            def mode(v):
                b.poke16(at('DESKTEST','mode'),v);until(at('DESKTEST','runningMode'),v)
            def pause(i):
                b.poke16(sy['CounterPause']+i*2,1)
                reach(f'(dw(${sy["CounterHeld"]+i*2:x})=1)|(@frame>={b.eval_expr("@frame")+120})')
                require(get(sy['CounterHeld']+i*2)==1,'Counter pause not reached: '+str(dict(index=i,ready=get(app(i,"ready")),count=get(app(i,"count"),4),paints=get(app(i,"paints"),4),failure=get(sy["GEMCountersFailure"]),text_token=get(at("CONSOLEBITMAP","desktopToken"),4),paint_token=get(at("DESKPAINT","paintToken"),4),dma=get(at("CONSOLEBITMAP","drawingPending"),1))))
            def resume(i):b.poke16(sy['CounterPause']+i*2,0)
            font=font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
            def external(r,title,bounds):
                require(title in (b'Counter A',b'Counter B'),'Unexpected counter title')
                i=int(title==b'Counter B');l,t,rr,bb=bounds
                r.clip=(l+8,t+16,rr-9,bb-9);r.text=2 if i else 4
                r.apply(8,(l+16,t+30),b'GEM counter')
                r.apply(8,(l+16,t+46),('Count: %06d'%get(app(i,'count'),4)).encode())
                r.clip=(0,0,639,239)
            def snapshot(name):
                mode(0)
                if counters:pause(0);pause(1)
                move(620,232);frames(100)
                c=constants();row=p['build']['memory']['console_storage']['WINDOWS']+c['WINDOWS_ITEMS']
                instance=get(row+c['WINDOW_INSTANCE'],3)
                require(get(instance+c['INSTANCE_DIRTYROWS'],1)==0,'Console not settled')
                terminal=Terminal(64,20);terminal.cells[:]=read_cells(lambda a,n:b.memdump(a,n),instance)
                cursor=get(instance+54)+get(instance+10);terminal.column=cursor%64;terminal.row=cursor//64
                packed=compose(b,p,font,terminal,position,external)
                folder=out/name;folder.mkdir(exist_ok=True)
                (folder/'expected.bin').write_bytes(packed)
                (folder/'model.bin').write_bytes(terminal.cells)
                report['pixels'].append(dict(name=name,digest=pixels(b,folder,packed)))
                print(name,'pixels pass',flush=True)
                if counters:resume(0);resume(1)
            def toggle():
                move(480,128);old=get(at('DESKAPP','updates'))
                edge(1)
                begin=b.eval_expr('@clk') & 0xffffffff
                edge(0)
                reach(f'(dw(${at("DESKAPP","updates"):x})>{old})&(db(${at("DESKAPP","refresh"):x})=0)')
                model_end=b.eval_expr('@clk') & 0xffffffff
                require(get(at('DESKAPP','updates'))==old+1,'Duplicate native toggle')
                # Observe actual completed scanout, independently rendering the
                # known application label. One-frame upper-bound quantization.
                from control_panel_oracle import panel
                r=Raster(font);selected=(old+1)%2
                panel(r,True,status='Toggle on [2]' if selected else 'Toggle off [2]',toggle=selected)
                packed=r.packed();rgb=bytes((v&254)+(v>>7) for v in PALETTE)
                colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                want=b''.join(colors[packed[(y*640+x)//2] >> (0 if x&1 else 4) & 15]
                    for y in range(104,112) for x in range(448,608))
                for attempt in range(300):
                    frame=b.rawscreen(str(out/'scanout.bgra'));raw=(out/'scanout.bgra').read_bytes()
                    actual=b''.join(raw[y*frame.stride+(x+16)*4:y*frame.stride+(x+16)*4+3]
                        for y in range(104,112) for x in range(448,608))
                    if actual==want:break
                    frames(1)
                require(actual==want,'Native label did not repaint')
                end=b.eval_expr('@clk') & 0xffffffff
                return dict(start=begin,end=end,elapsed_ms=((end-begin)&0xffffffff)/BASE_HZ*1000,
                    model_ms=((model_end-begin)&0xffffffff)/BASE_HZ*1000,scans=attempt+1)
            def drag_panel():
                from generate_desktop import layout
                from generate_layers import layout as layers
                service=get(at('DESKSTATE','service'),3)
                bounds=service+layout()['Service']['fields']['scene']+layers()['Scene']['fields']['items']+layers()['Layer']['size']+4
                require(get(bounds)==432,'Unexpected panel geometry')
                for left,target in ((432,440),(440,432)):
                    move(left+48,86);edge(1)
                    reach(f'db(${at("DESKDRAG","phase"):x})=1')
                    move(target+48,86);edge(0)
                    reach(f'(db(${at("DESKDRAG","phase"):x})=0)&(dw(${bounds:x})={target})&(dw(${at("DESKMOVE","moveToken"):x})=0)')
                    frames(4)

            def before(b):
                if trace:b.profile_start()
                until(at('DESKTEST','ready'))
                b.poke(at('DESKTEST','runCounters'),int(counters));b.poke(at('DESKTEST','startGate'),1)
                until(at('DESKTEST','ready'),2);frames(120)
                if counters:
                    report['window_handles']=[get(app(i,'window')) for i in range(2)]
                    require(set(report['window_handles'])=={1,2},'Notification marker identity differs')
                report['task_count']=get(p['build']['task_storage']['LIVE'],1)
                require(report['task_count']==(5 if counters else 3),'Unexpected coexistence Task count')
                snapshot('initial')
                for name,value in [('idle',0),('scroll',2),('disk',3)]:
                    mode(value);frames(15)
                    begin=b.eval_expr('@clk') & 0xffffffff
                    progress=get(at('DESKTEST','writes' if value==2 else 'reads'))
                    observations=[]
                    for index in range(8):
                        observations.append(toggle());drag_panel();frames(8)
                        print(name,index+1,flush=True)
                    end=b.eval_expr('@clk') & 0xffffffff
                    delta=get(at('DESKTEST','writes' if value==2 else 'reads'))-progress
                    if value:require(delta>0,'Native workload stopped')
                    report['loads'].append(dict(name=name,start=begin,end=end,progress=delta,task_count=get(p['build']['task_storage']['LIVE'],1),
                        feedback=distribution([r['elapsed_ms'] for r in observations]),samples=observations))
                    snapshot(name)
                if counters:
                    # A delayed event consumer owns neither GUI nor hardware;
                    # both the peer timer and native service must make progress.
                    pause(0);old=get(app(1,'count'),4);mode(3);reads=get(at('DESKTEST','reads'))
                    observations=[toggle() for _ in range(3)];frames(150)
                    require(get(app(1,'count'),4)>old and get(at('DESKTEST','reads'))>reads,'Delayed app blocked its peer/service')
                    report['delayed_app']=dict(peer_ticks=get(app(1,'count'),4)-old,disk_reads=get(at('DESKTEST','reads'))-reads,native_updates=len(observations))
                    resume(0);snapshot('delayed-peer-recovery')
                b.poke16(at('DESKTEST','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            ownership(b,p,p['output'])
            if trace:b.profile_stop()
            if counters:require(get(sy['GEMCountersFailure'])==0,'Counter failure')
        if not trace:
            report['status']='pass'
            return report
        report['timing']=counter_timing.result(out,config)
        # Correlate the single GUI record per window, from producer marker just
        # before PutMsg to the application's message-ready hook. FIFO pairing
        # preserves a second publication before the first hook has executed.
        events=read_events(out/'emulator.log');points=config[0]['notifications'];pending={1:deque(),2:deque()};notifications=[]
        for tick,e in events:
            if e[0]!='cpu':continue
            pc=int(e[4],16)
            for i in (1,2):
                if pc==points['notice'+str(report.get('window_handles',[1,2])[i-1])]:pending[i].append(tick)
                elif pc==points['received'+str(i)] and pending[i]:
                    begin=pending[i].popleft();notifications.append(dict(instance=i,start=begin,end=tick,elapsed_ms=(tick-begin)/BASE_HZ*1000))
        require(not any(pending.values()),'Undelivered GUI notification at retirement')
        report['notifications']=notifications
        for load in report['loads']:
            # Host clock wraps independently of the extended trace timeline.
            first=events[0][0]
            align=lambda v:v+round((first-v)/(1<<32))*(1<<32)
            start,end=align(load['start']),align(load['end'])
            selected=[r for r in report['timing']['rows'] if start<=r['start'] and r['end']<=end]
            load['counter_timing']={kind:{metric:distribution([r[metric] for r in selected if r['kind']==kind])
                for metric in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')}
                for kind in sorted({r['kind'] for r in selected})}
            load['gui_notification']=distribution([r['elapsed_ms'] for r in notifications if start<=r['start'] and r['end']<=end])
        report['scope']='Same image, same native panel toggles/title drags and idle/scroll/disk root workload, with zero or two counter Tasks. Feedback is physical release stimulus scheduling after a four-frame press hold through the first exact native label scanout; includes input injection delay and up to one-frame scanout observation quantization. Counter/GUI markers add development-only work. No PI4/HY4 qualification.'
        report['status']='pass'
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:
        counter_timing.restore(config)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--counters',action='store_true');p.add_argument('--no-trace',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.program.resolve(),a.counters,not a.no_trace)
