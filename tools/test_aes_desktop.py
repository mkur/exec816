#!/usr/bin/env python3
"""Observe actual native pixels and retained input across resident AES locks."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import adapter_state as adapter
from bitmap_console_performance import native_markers
from desktop_mouse import schedule
from generate_desktop import layout
from generate_layers import layout as layer_layout
from make_data_disk import make
from native_program import read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sio_transaction_trace import read_events
from stack_budget import stack_usage
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out, program, unobserved=False, integrated=False, trace_calls=False):
    require(not trace_calls or (integrated and not unobserved),'Call tracing requires the observed integrated proof')
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program)
    sy=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    marks=native_markers(p,[('DESKHOST_CONTROLS','turn')])
    aes_marks={}
    if trace_calls:
        from aes_latency_trace import markers as aes_markers
        aes_marks=aes_markers(p,json.loads((p['output'].parent/'c-image.json').read_text()))
    for name in ('EXEC816_MOUSE_TRACE','EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE'):
        os.environ.pop(name,None)
    if not unobserved:
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in [marks['turn']['entry'],*aes_marks.values()]))
    media=out/'media/TOOLS/SUB';media.mkdir(parents=True,exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk=out/'disk.atr';make(disk,out/'media',binary_names={'TOOLS/SUB/DATA.BIN'},filesystem='sdfs')
    report=dict(slice='HY4' if integrated else 'HY4-locks',status='running',tier='development',qualification=False,
        observer=not unobserved,build=p['build'],cases=[],idle_windows=[],
        reserved_bank_zero_delta=dict(fixed=0,per_public_task=[0]*8))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.mount(0,str(disk));b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
            report['machine']=verify_machine(b,ROM,PIN)
            get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
            read=lambda mod,n,size=2:get(at(mod,n),size)
            c=lambda name:get(sy[name])
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
                try:run_to(b,marker,condition=condition,frame_limit=12000,timeout=600)
                finally:b.regs=original
            def frames(n=1):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            position=[320,120]
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(down):
                b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(3)
            def scan(region):
                l,t,r,bb=region
                f=b.rawscreen(str(out/'scanout.bgra'));raw=(out/'scanout.bgra').read_bytes()
                return b''.join(raw[y*f.stride+(x+16)*4:y*f.stride+(x+16)*4+3]
                    for y in range(t,bb) for x in range(l,r))
            def before(bridge):
                if not unobserved:b.profile_start()
                reach('dw($%x)=1'%at('DESKTEST','ready'));frames(160)
                print('AES desktop ready',flush=True)
                if integrated:
                    b.poke16(sy['AESCommand'],6)
                    reach('dw($%x)=1'%sy['AESRestarts'])
                    require(c('AESReady')==2 and c('AESFailures')==0,'Loaded client restart failed')
                service=read('DESKSTATE','service',3)
                sf=layout()['Service']['fields'];wf=layout()['Window']['fields'];ws=layout()['Window']['size']
                scene=service+sf['scene'];lf=layer_layout()
                busy=scene+lf['Scene']['fields']['busy']
                panel=service+sf['windows']+2*ws
                context=get(panel+wf['widgets'],3)
                require(context!=0,'Missing production panel')
                layer=scene+lf['Scene']['fields']['items']+2*lf['Layer']['size']
                bounds=layer+lf['Layer']['fields']['bounds']
                report['task_stacks_before']=stack_usage(b,p['build']['memory'])
                for command in (1,2):
                    print('Lock cohort',command,flush=True)
                    # Root owns real disk traffic. Both C Tasks retain ordinary
                    # Exec contexts and use GEM messages/timers under the lock.
                    b.poke16(at('DESKTEST','mode'),3)
                    reach('dw($%x)=3'%at('DESKTEST','runningMode'))
                    reads=read('DESKTEST','reads')
                    b.poke16(sy['AESCommand'],command)
                    reach('dw($%x)=2'%sy['AESPhase'])
                    held_from=clock()
                    print('Lock granted; timer armed',flush=True)
                    require(get(busy,1)==0,'Layers token survived lock grant')
                    frames(30)
                    require(read('DESKTEST','reads')>reads,'Disk stopped under AES lock')
                    updates=read('DESKAPP','updates');old_bounds=b.memdump(bounds,8)
                    focus=get(service+sf['focus'],4)
                    # A click and a title drag are retained together. Capture
                    # moves the cursor now; semantic input waits for unlock.
                    left=int.from_bytes(old_bounds[:2],'little');top=int.from_bytes(old_bounds[2:4],'little')
                    move(left+48,top+48);edge(1);edge(0)
                    move(left+48,top+6);edge(1);move(left+64,top+14);edge(0)
                    move(620,232)
                    require(read('DESKAPP','updates')==updates,'Widget changed while mouse owned')
                    require(b.memdump(bounds,8)==old_bounds,'Geometry changed while mouse owned')
                    require(get(service+sf['focus'],4)==focus,'Focus changed while mouse owned')
                    panel_before=scan((left+8,top+24,left+176,top+136))
                    console_before=scan((264,40,416,216))
                    b.poke16(at('DESKTEST','mode'),2)
                    reach('dw($%x)=2'%at('DESKTEST','runningMode'))
                    writes=read('DESKTEST','writes');frames(12)
                    write_from=clock()
                    begin=clock();frames(20);finish=clock()
                    require(c('AESPhase')==2,'Lock hold too short for observation')
                    require(scan((left+8,top+24,left+176,top+136))==panel_before,'Panel pixels changed under mouse lock')
                    if command==1:
                        require(get(busy,1)==0,'Layers token appeared under update lock')
                        require(scan((264,40,416,216))==console_before,'Console pixels changed under update lock')
                        require(read('DESKTEST','writes')==writes,'Console write progressed under update lock')
                        report['idle_windows'].append([begin,finish])
                    else:
                        # A clipped 512-byte write can exceed this short pixel
                        # observation window; require completion before unlock.
                        reach('(dw($%x)>%d)|(dw($%x)=3)'%(at('DESKTEST','writes'),writes,sy['AESPhase']))
                        from sio_transaction_trace import BASE_HZ
                        report['mouse_hold_progress']=dict(writes_before=writes,writes_after=read('DESKTEST','writes'),
                            phase=c('AESPhase'),hold_elapsed_ms=((clock()-held_from)&0xffffffff)/BASE_HZ*1000,
                            write_elapsed_ms=((clock()-write_from)&0xffffffff)/BASE_HZ*1000)
                        require(read('DESKTEST','writes')>writes and c('AESPhase')==2,
                            'Explicit mouse hold blocked console paint')
                    print('Frozen pixels/independent work checked',flush=True)
                    b.poke16(at('DESKTEST','mode'),0)
                    reach('(dw($%x)=3)&(dw($%x)=3)'%(sy['AESPhase'],sy['AESPeerPhase']))
                    reach('dw($%x)>%d'%(at('DESKAPP','updates'),updates))
                    print('Retained click delivered',flush=True)
                    frames(150)
                    require(read('DESKAPP','updates')==updates+1,'Lost or duplicated retained click')
                    require(b.memdump(bounds,8)!=old_bounds,'Retained drag did not resume')
                    require(c('AESFailures')==0,'C application check '+str(c('AESFirstFailure')))
                    report['cases'].append(dict(lock='update' if command==1 else 'mouse',
                        disk_reads=read('DESKTEST','reads')-reads,messages=c('AESMessages'),timers=c('AESTimers'),
                        old_bounds=list(old_bounds),new_bounds=list(b.memdump(bounds,8)),
                        deferred_clicks=1,token_at_grant=0))
                if integrated:
                    # The blocked-paint assertion above needs instruction
                    # history. Later phases check progress and ownership, with
                    # bounded call/deadline tracing in measure_aes_calls. Avoid
                    # profiling every instruction in three long exchanges unless
                    # the caller explicitly requests the full call trace.
                    if not unobserved and not trace_calls:
                        b.profile_stop()
                    report['observation_scope']=(
                        'No CPU instruction observation; state, progress and pixel checks.' if unobserved else
                        'Whole-run presenter and AES call markers, plus state/progress/pixel checks.' if trace_calls else
                        'Presenter markers during GUI lock phases; progress/state checks during CPU, message and restart phases.')
                    for command in (3,4,6,4,6,4):
                        load=3 if command==3 else 2 if command==4 else 0
                        b.poke16(at('DESKTEST','mode'),load)
                        reach('dw($%x)=%d'%(at('DESKTEST','runningMode'),load))
                        reads=read('DESKTEST','reads');writes=read('DESKTEST','writes')
                        restarts=c('AESRestarts')
                        b.poke16(sy['AESCommand'],command)
                        if command==6:
                            reach('dw($%x)>%d'%(sy['AESRestarts'],restarts))
                        else:
                            reach('dw($%x)=%d'%(sy['issued'],command))
                            reach('(dw($%x)=3)&(dw($%x)=3)'%(sy['AESPhase'],sy['AESPeerPhase']))
                        require(c('AESFailures')==0,'Integrated GEM failure '+str(c('AESFirstFailure')))
                        item=dict(command=command,reads=read('DESKTEST','reads')-reads,
                            writes=read('DESKTEST','writes')-writes,restarts=c('AESRestarts'))
                        if command==3:
                            item['cpu_iterations']=get(sy['AESBurns'],4)
                            require(item['cpu_iterations']>1000 and item['reads']>0,'CPU peer prevented timer/disk progress')
                        report['cases'].append(item)
                        print('Integrated phase',command,'passed',flush=True)
                report['stack_usage']=stack_usage(b,p['build']['memory'])
                b.poke16(at('DESKTEST','mode'),9)
                reach('dw($%x)=2'%at('DESKTEST','ready'));b.bp_clear_all()
            try:
                report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=16000)
            except Exception:
                report['failure_state']={name:c(name) for name in ('AESReady','AESDone','AESPhase','AESPeerPhase','AESChecks','AESFailures','AESFirstFailure')}
                report['native_state']={name:read('DESKTEST',name) for name in ('mode','runningMode','ready','writes','reads')}
                raise
            report['checks']=c('AESChecks');report['failures']=c('AESFailures')
            require(report['failures']==0,'AES retirement failed')
            ownership(b,p,p['output']);report['ownership']='restored'
            if integrated:
                meta=(p['output']/'timermeta.act').read_text()
                timer_base=int(re.search(r'PUBLIC CONST BASE=\$([0-9a-f]+)',meta,re.I)[1],16)
                report['final_timer_clock']=get(timer_base+4,4)
            if not unobserved and (not integrated or trace_calls):b.profile_stop()
        if not unobserved:
            events=read_events(out/'emulator.log',kinds={'cpu'})
            align=lambda t:t+round((events[0][0]-t)/(1<<32))*(1<<32)
            counts=[sum(align(lo)<=t<=align(hi) and int(e[4],16)==marks['turn']['entry'] for t,e in events)
                    for lo,hi in report['idle_windows']]
            report['blocked_paint_turns']=counts
            if trace_calls:
                from aes_latency_trace import analyze
                report['aes_latency']=analyze(events,aes_marks,report['final_timer_clock'])
            require(counts==[0],'Presenter spins over blocked paint: '+str(counts))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        report['xex_sha256']=sha256(p['xex'])
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AES native gates:',report['status'],report['checks'],'C checks')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--unobserved',action='store_true')
    parser.add_argument('--integrated',action='store_true')
    parser.add_argument('--trace-calls',action='store_true',help='Record every AES call throughout the long proof; bounded load distributions normally use measure_aes_calls')
    args=parser.parse_args();run(args.output.resolve(),args.program.resolve(),args.unobserved,args.integrated,args.trace_calls)
