#!/usr/bin/env python3
"""Existing ST controller -> INPUT -> GEM controls and exact visible pixels."""
import argparse
import json
import os
import re
import time
from pathlib import Path
import adapter_state as adapter
from build_gem_interactive import build_interactive
from native_program import ROOT,execute,read_build,require,sha256,verify_machine
from os_boundary import emulator
from stack_budget import stack_usage
from test_heap_api import clean_ownership
from test_gem_interactive import scene,pixels
from test_mouse_observe import PIN,BRIDGE,ROM
from sio_transaction_trace import BASE_HZ,stats
from bisect import bisect_left


def run(output,mode,cases=None,replay=False,production=False,unobserved=False):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='M5' if any(n in ('rate','latency','burst') for n in (cases or [])) else 'M4',mode=mode,production=production,
                observer=not unobserved,cases=[])
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned mouse bridge')
        if replay:
            p=read_build(output/'program'); foreign=json.loads((output/'c-image.json').read_text())
        else:
            p,foreign=build_interactive(output,mode=='opt',not production)
        require(foreign['provenance']['diagnostic']==(not production),'Wrong instrumentation')
        sy=foreign['symbols']; memory=p['build']['memory']
        if production:
            require(all(n in sy for n in ('UiPostMouse','mouseInput','mouseReceived')),'Missing physical source association')
            require(not any(n in sy for n in ('UiProbe','UiInjector','injectRequest','injectEvents','holdCursor','faultNext')),
                    'Diagnostic producer/storage in production')
            require(not any(n.startswith(('pointer_probe_','timer_probe_')) for n in p['labels']),
                    'Diagnostic native entry in production')
            if (output/'Exec-gem-vdi.xex').exists():
                require(sha256(output/'Exec-gem-vdi.xex')==sha256(p['xex']) and
                        sha256(output/'graphics.atr')==sha256(output/'system.atr'),'Packaged pair differs')
                p={**p,'xex':output/'Exec-gem-vdi.xex'}
        report.update(build=p['build'],pin=PIN,xex_sha256=sha256(p['xex']),media_sha256=sha256(output/'system.atr'),
                      harness_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
        if unobserved: os.environ.pop('EXEC816_MOUSE_TRACE',None)
        else: os.environ['EXEC816_MOUSE_TRACE']='1'
        for name in cases or ['controls']:
            timed=name in ('rate','latency')
            if timed and not unobserved:
                os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',
                    EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k,v in p['labels'].items()
                        if k.startswith(('sio_','timer_','native_','signal_route','dispatch_','context_restore','pointer_'))))
            else:
                for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(key,None)
            folder=output/name; folder.mkdir(exist_ok=True)
            case=dict(name=name,status='running',commands=[],observations=[],pictures=[]); report['cases'].append(case)
            with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
                b.mount(0,str(output/'system.atr')); b._cmd_ok('MOUSE ST')
                case['machine']=verify_machine(b,ROM,PIN)
                get=lambda key,n=2:int.from_bytes(b.memdump(sy[key],n),'little')
                ex=lambda key:f'dw(${sy[key]:x})'
                saved={}
                expected_position=[320,120]
                def hardware():
                    values={key:b.memdump(address,n).hex() for key,address,n in
                            [('mask',16,1),('skctl',0x232,1),('timer_vector',0x210,2),('key_vector',0x208,2),
                             ('break_vector',0x236,2),('display',0x22f,3),('memac',0xd65e,2)]}
                    pia=b.pia()
                    port2=int(pia.pop('PORTA').lstrip('$'),16)&0xf0
                    values.update(pia=pia,port2=port2,gractl=b.gtia()['GRACTL'])
                    return values
                def observe(kind):
                    value=dict(kind=kind,tick=b.peek16(adapter.VBI_COUNT),frame=b.eval_expr('@frame'),
                               phase=b.peek(p['labels']['SD_PHASE'])[0],mouse_received=get('mouseReceived'),
                               x=get('pointerX'),y=get('pointerY'),buttons=get('pointerButtons'),
                               count=get('count'),focus=get('focus'),losses=get('inputLosses'))
                    case['observations'].append(value)
                    return value
                def reach(condition,label='native_nmi'):
                    marker=p['labels'][label]
                    b.bp_clear_all(); b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    initial=b.eval_expr('@frame'); deadline=time.monotonic()+80
                    b.resume()
                    while time.monotonic()<deadline:
                        regs=b.regs()
                        if int(regs['PC'].lstrip('$'),16)==marker and b.eval_expr(condition):
                            b.pause(); return
                        if b.peek16(adapter.STATE)!=0xffff or b.eval_expr('@frame')-initial>6000: break
                        time.sleep(.02)
                    b.pause()
                    case['debug']={key:get(key) for key in ('initialReady','finished','failures','firstFailure','mouseStatus',
                                  'mouseReceived','pointerEvents','pointerX','pointerY','pointerReady','pointerButtons',
                                  'armed','inputLosses','dirty','pointerDirty','submitted','collected')}
                    case['debug']['state']=b.peek16(adapter.STATE)
                    case['debug']['capture']=b.memdump(memory['input_storage']['POINTER_CAPTURE'],128).hex()
                    raise RuntimeError('No mouse checkpoint: '+condition)
                def frames(n): reach(f'@frame>={b.eval_expr("@frame")+n}')
                def command(delay,dx=0,dy=0,left=-1):
                    text=f'MOUSE AT {delay} {dx} {dy} {left}'
                    case['commands'].append(dict(command=text,**b._cmd_ok(text)))
                def idle():
                    condition=(f'({ex("dirty")}=0)&({ex("pointerDirty")}=0)&({ex("uiQueued")}=0)&'
                               f'(dw(${sy["client"]+12:x})=0)&(dw(${sy["client"]+14:x})=0)')
                    for attempt in range(100):
                        reach(condition)
                        state=(get('diskProgress'),b.peek16(sy['boot']+46))
                        frames(2)
                        # A disk progress message can arrive between completion
                        # and scanout. Compare only a stable, completed frame.
                        if b.eval_expr(condition) and state==(get('diskProgress'),b.peek16(sy['boot']+46)):return
                    raise RuntimeError('Scene did not reach a stable completed frame')
                def move(x,y):
                    old=list(expected_position); dx=x-old[0];dy=y-old[1];index=0
                    while dx or dy:
                        step_x=max(-8,min(8,dx));step_y=max(-8,min(8,dy))
                        command(2000+index*85000,step_x*16,step_y*16)
                        dx-=step_x;dy-=step_y;index+=1
                    if index:
                        reach(f'({ex("pointerX")}!={old[0]})|({ex("pointerY")}!={old[1]})')
                        observe('first-motion')
                        reach(f'({ex("pointerX")}={x})&({ex("pointerY")}={y})')
                    expected_position[:]=[x,y];observe('position')
                def button(down):
                    command(2000,left=1 if down else 0)
                    reach(f'{ex("pointerButtons")}={1 if down else 0}')
                    observe('press' if down else 'release')
                def click():
                    button(True); frames(1); button(False)
                def key(name):
                    before=get('received')
                    require(b._cmd_ok(f'KEY {name} down')['raw_scan'],'Not physical keyboard')
                    reach(f'{ex("received")}>{before}')
                    b._cmd_ok(f'KEY {name} up');frames(4)
                def picture(label):
                    idle(); target=folder/label;target.mkdir(exist_ok=True)
                    text=b.memdump(sy['text'],get('length'))
                    packed=scene(output,text,get('focus'),get('count'),get('diskProgress'),
                                 bool(b.peek16(sy['boot']+46)),cursor=tuple(expected_position))
                    case['pictures'].append(dict(name=label,sha256=pixels(b,target,packed),observation=observe('visible')))
                def before(bridge):
                    saved.update(hardware()); b._cmd_ok('KEY ALL up')
                    if timed and not unobserved:b.profile_start()
                    reach(f'{ex("initialReady")}=1')
                    require(get('mouseStatus')==0 and b.peek16(sy['mouseInput']+24)==2,'Pointer admission failed')
                    mouse_acq=int.from_bytes(b.memdump(sy['mouseInput']+12,4),'little')
                    mouse_route=int.from_bytes(b.memdump(sy['mouseInput']+16,4),'little')
                    require(mouse_acq!=int.from_bytes(b.memdump(sy['input']+12,4),'little'),'Source acquisitions alias')
                    # Source association is distinct from the private queue's canonical keyboard identity.
                    case['association']=dict(acquisition=mouse_acq,route=mouse_route,session=b.peek16(sy['boot']+4))
                    phase=p['labels']['SD_PHASE'];reach(f'(db(${phase:x})>0)&(db(${phase:x})<13)','native_irq')
                    observe('active-sio')
                    if name=='burst':
                        command(2000,4096,4096)
                        frames(40)
                        expected_position[:]=[get('pointerX'),get('pointerY')]
                        observe('outside-envelope');picture('burst')
                        b._cmd_ok('KEY ESC down');b.bp_clear_all();return
                    if name=='rate':
                        # Maintain sixteen phases of backlog: the existing controller
                        # emits at 16 scanlines (1.028 ms), its fastest in-envelope
                        # quantization. Independent phase tracing verifies this.
                        command(2000,272,272)
                        for i in range(80):command(2000+(16+16*i)*114,16,16)
                        command(25000,left=1);command(65000,left=0)
                        expected_position[:]=[417,217]
                        reach(f'({ex("pointerX")}=417)&({ex("pointerY")}=217)&({ex("pointerButtons")}=0)')
                        observe('rate-complete');key('A');picture('rate')
                        require(get('pointerActivations')==0,'Background click activated a control')
                        b._cmd_ok('KEY ESC down');b.bp_clear_all();return
                    if name=='latency':
                        from gem_mouse_observe import visible
                        case['latency']=visible(b,p,foreign,output,folder,reach,get,command,expected_position,observe)
                        picture('latency');b._cmd_ok('KEY ESC down');b.bp_clear_all();return
                    move(210,64);click();key('A');picture('field')
                    require(get('length')==1 and get('focus')==0,'Field click/typing failed')
                    move(60,100);click();picture('count')
                    require(get('count')==1 and get('focus')==1,'Count click failed')
                    button(True);move(120,100);button(False);picture('outside')
                    require(get('count')==1,'Release outside activated Count')
                    if name=='close-held':
                        move(60,100);button(True)
                        b._cmd_ok('KEY ESC down');b.bp_clear_all();return
                    move(190,100);button(True);frames(1)
                    command(2000,left=0);b.bp_clear_all()
                runtime,_=execute(b,p,before_run=before,timeout=360,frame_limit=24000)
                if timed and not unobserved:b.profile_stop()
                b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE CLEAR')
                require(get('finished')==1 and get('failures')==0,'Application did not finish cleanly')
                require(get('count')==(0 if name in ('rate','latency','burst') else 1) and (name=='burst' or get('inputLosses')==0),'Lost or duplicated physical input')
                require(get('submitted')==get('collected'),'Graphics request retained')
                require(b.memdump(sy['input'],32)==bytes(32) and b.memdump(sy['mouseInput'],32)==bytes(32),'Input lease retained')
                require(get('closed')==1 and get('uiQueued')==0,'GUI admission remains open')
                case.update(hardware_before=saved,hardware_after=hardware())
                require(case['hardware_after']==saved,'Hardware not restored')
                clean_ownership(b,p,p['output'])
                case.update(runtime=runtime,hardware_before=saved,hardware_after=hardware(),
                            stack_usage=stack_usage(b,memory),final_position=[get('pointerX'),get('pointerY')],
                            counters={key:get(key) for key in ('checks','mouseReceived','pointerEvents','pointerActivations',
                                                             'inputLosses','cursorPackets','received','submitted','collected')})
            trace=[list(map(int,m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)',(folder/'emulator.log').read_text())]
            if not unobserved:
                phases=[0,2,3,1]; previous=0; x,y=320,120; last=[None,None]; gaps=[]; edges=0
                for cycle,bits,_,_ in trace:
                    for axis,shift in enumerate((0,2)):
                        old=phases.index((previous>>shift)&3);new=phases.index((bits>>shift)&3)
                        delta=(new-old)%4
                        require(delta!=2,'Observer skipped a controller phase')
                        if delta:
                            amount=1 if delta==1 else -1
                            if axis==0:x=max(0,min(639,x+amount))
                            else:y=max(0,min(239,y+amount))
                            if last[axis] is not None:gaps.append(cycle-last[axis])
                            last[axis]=cycle
                    edges+=bool((bits^previous)&256); previous=bits
                require(name=='burst' or case['final_position']==[x,y],'Unreported physical phase/count error')
                require(name=='burst' or not gaps or min(gaps)/BASE_HZ>=.001,'Fixture exceeds declared transition envelope')
                if timed:
                    from gem_mouse_observe import timing
                    case['timing'],reads=timing(folder/'emulator.log',p['labels'])
                    delays=[]
                    for cycle,*_ in trace:
                        index=bisect_left(reads,cycle)
                        if index<len(reads):delays.append(reads[index]-cycle)
                    case['timing']['controller_to_capture']=stats(delays)
                case.update(controller_trace=trace,controller_position=[x,y],controller_button_edges=edges,
                            minimum_axis_transition_us=min(gaps)/BASE_HZ*1e6 if gaps else None)
            case['status']='pass'
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        if report['cases']:report['cases'][-1].update(status='fail',error=str(error))
        raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Physical GEM mouse passed:',mode,','.join(case['name'] for case in report['cases']),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['raw','opt'],default='opt')
    parser.add_argument('--case',choices=['controls','close-held','rate','latency','burst'],action='append')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true');parser.add_argument('--production',action='store_true')
    parser.add_argument('--unobserved',action='store_true')
    args=parser.parse_args();run(args.output,args.mode,args.case,args.replay,args.production,args.unobserved)
