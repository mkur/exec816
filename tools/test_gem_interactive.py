#!/usr/bin/env python3
"""Focused interactive keyboard/lifetime checks on the pinned physical SIO machine."""
import argparse
import hashlib
import json
from stack_budget import current_task_memory
from pathlib import Path
import adapter_state as adapter
from build_gem_interactive import build_interactive
from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
from native_program import ROOT,execute,read_build,verify_machine,require,sha256
from os_boundary import emulator,run_to
from test_gem_concurrent import media,MEDIA_ERRORS
from test_heap_api import clean_ownership
from test_cooperative import data
from stack_budget import stack_usage
from test_calypsi import pattern
from test_large_stacks import observe
from test_console_display import terminal
from console_model import read_cells
from generate_console import constants as console_constants
PIN=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
CASES=['keyboard','early-escape','late-escape','break','root-stop','input-busy','display-busy',
       'client-allocation','renderer-allocation','admission','wrong-disk','no-disk','short-file','corrupt-file',
       'latency','latency-wrap','context','app-signal','input-signal','ready-exhausted','raw-full',
       'render-timeout','render-busy','escape-sio','escape-render',
       'mouse-signal','mouse-after-signal','mouse-after-lease','mouse-after-route','mouse-busy']
MOUSE_VARIANTS={'mouse-signal':30,'mouse-after-signal':31,'mouse-after-lease':32,'mouse-after-route':33,'mouse-busy':34}

def scene(output,text=b'',focus=0,count=0,progress=2048,done=True,cursor=(320,120),mouse_status=0):
    r=Raster(font_bytes(output/'selected/src/vdi/font8x8.c'))
    labels=[b'GEM/Exec',text.ljust(24)[0:8],text.ljust(24)[8:16],text.ljust(24)[16:24],
            f'Count{count%1000:03}'.encode(),b'Exit    ',f'Disk{progress*100//2048:03}%'.encode(),b'Tab/Ente',
            b'KeysOnly' if mouse_status else b'Done    ' if done else b'Reading ']
    for tile,label in enumerate(labels):
        x=32+(tile-1)*64 if 1<=tile<=3 else 176 if tile==5 else 32
        y=24 if tile==0 else 64 if tile<=3 else 104 if tile<=5 else 144 if tile==6 else 168 if tile==7 else 184
        pen=2+count%14 if tile==4 else 0
        if (1<=tile<=3 and focus==0) or (tile==5 and focus==2):pen=6
        r.apply(25,ints=[pen]);r.apply(11,[x,y-10,x+63,y-8]);r.apply(22,ints=[2 if tile==4 and focus==1 else 1]);r.apply(8,[x,y],label)
    from test_gem_cursor import overlay
    return overlay(r,cursor)

def pixels(b,folder,expected):
    b.screenshot(str(folder/'scene.png'))
    frame=b.rawscreen(str(folder/'scanout.bgra'));raw=(folder/'scanout.bgra').read_bytes()
    require((frame.width,frame.height)==(672,240),'Wrong geometry')
    rgb=bytes((v&254)+(v>>7) for v in PALETTE);hardware=[None]*16
    for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
    cropped=b''.join(raw[y*frame.stride+64:y*frame.stride+2624] for y in range(240))
    actual=b''.join(cropped[i:i+3] for i in range(0,len(cropped),4))
    want=b''.join(hardware[v>>4]+hardware[v&15] for v in expected)
    require(actual==want,'Scene pixels differ: '+str(next((i//3 for i,(a,c) in enumerate(zip(actual,want)) if a!=c),None)))
    return hashlib.sha256(actual).hexdigest()

def run(output,mode,cases=None,replay=False,production=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='I6',mode=mode,cases=[],production=production)
    try:
        if replay:
            p=read_build(output/'program');foreign=json.loads((output/'c-image.json').read_text())
        else:p,foreign=build_interactive(output,mode=='opt',not production)
        require(foreign['provenance']['diagnostic']==(not production),'Wrong instrumentation')
        require(p['build']['foreign_image']==foreign['provenance'],'C image/build provenance differs')
        require(p['build']['optimize']==(mode=='opt') and sha256(p['xex'])==p['build']['xex_sha256'],'Wrong or changed replay image')
        packaged=production and (output/'Exec-gem-vdi.xex').exists()
        if packaged:
            require(sha256(output/'Exec-gem-vdi.xex')==sha256(p['xex']) and
                    sha256(output/'graphics.atr')==sha256(output/'system.atr'),'Packaged pair differs from recorded build')
            p={**p,'xex':output/'Exec-gem-vdi.xex'}
        report['booted_image']=str(p['xex'].relative_to(ROOT))
        sy=foreign['symbols'];memory=p['build']['memory']
        if production:
            require(not any(k in sy for k in ('UiProbe','UiInjector','UiUnusedTask','UiCursorGate','UiLossAck','UiBusy','faultNext')),
                    'Diagnostic hook in production image')
        baseline=current_task_memory()
        for k in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[k]==baseline[k],'Bank-zero change: '+k)
        report.update(build=p['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),
            observation_sha256=sha256(ROOT/'tools/gem_interactive_observe.py'),
            xex_sha256=sha256(p['xex']),media_sha256=sha256(output/'system.atr'),
            bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0),layout=foreign['provenance']['checked_layout'])
        for name in cases or ['keyboard']:
            folder=output/name;folder.mkdir(exist_ok=True)
            case=dict(name=name,status='running',stimuli=[]);report['cases'].append(case)
            with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
                b.config('diskemu','generic56k');disk=media(output,folder,name)
                if packaged and disk==output/'system.atr':disk=output/'graphics.atr'
                case['mounted_media']=str(disk.relative_to(ROOT)) if disk is not None else None
                if disk is not None:b.mount(0,str(disk))
                case['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
                read=lambda k,n=2:int.from_bytes(b.memdump(sy[k],n),'little')
                hardware=lambda:{k:b.memdump(a,n).hex() for k,a,n in (
                    ('mask',16,1),('skctl',0x232,1),('key_vector',0x208,2),('break_vector',0x236,2),
                    ('display',0x22f,3),('memac',0xd65e,2))}
                saved={}
                aperture=bytes((i*37+11)&255 for i in range(4096))
                expr=lambda k:f'dw(${sy[k]:x})'
                def reach(condition,label='native_nmi'):
                    marker=p['labels'][label];b.bp_clear_all();b.bp_set(marker,condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    try:run_to(b,marker,frame_limit=3000,timeout=45,condition=condition)
                    except Exception:
                        case['debug']={k:read(k) for k in ('finished','failures','firstFailure','stage','received','dirty','initialReady','submitted','collected')}
                        case['debug']['boot']=b.memdump(sy['boot'],48).hex()
                        case['debug']['state']=b.peek16(adapter.STATE)
                        case['debug']['adapter']=b.memdump(adapter.STATE,64).hex()
                        case['debug']['ports']={k:b.memdump(sy[k],27).hex() for k in ('rootPort','rootReplies','appPort','exitReplies')}
                        case['debug']['tasks']={k:b.memdump(int.from_bytes(b.memdump(sy['boot']+o,3),'little'),62).hex() for k,o in [('root',8),('app',12)]}
                        raise
                def frames(n):reach(f'@frame>={b.eval_expr("@frame")+n}')
                def key(name,state):
                    response=b._cmd_ok(f'KEY {name} {state}');require(response['raw_scan'],'Not physical keyboard')
                    case['stimuli'].append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
                def press(name):
                    before=read('received');key(name,'down');reach(f'{expr("received")}>{before}');key(name,'up');frames(4)
                def idle():
                    reach(f'({expr("dirty")}=0)&(dw(${sy["client"]+12:x})=0)&(dw(${sy["client"]+14:x})=0)&(dw(${sy["boot"]+46:x})=1)')
                    frames(2)
                def interact(bridge):
                    saved.update(hardware())
                    b.memload(0x8000,aperture)
                    key('ALL','up')
                    if 'variant' in sy:b.memload(sy['variant'],MOUSE_VARIANTS.get(name,CASES.index(name)).to_bytes(2,'little'))
                    if name=='context':
                        for slot in (0,6,7):
                            reach(f'db(${adapter.CURRENT:x})={slot}','task_start' if slot==0 else 'general_task_start')
                            dp=memory['task_pools'][slot]['dp']
                            b.memload(dp+8,pattern(slot)[8:16]); b.memload(dp+20,pattern(slot)[20:])
                        b.memload(adapter.KERNEL_DP,pattern(4))
                        case['c_preemption']=observe(b,p,[sy['submitted']]*2,code_bank=12,pc_range=(0xc0000,0xd0000))
                    if name in ('latency','latency-wrap'):
                        from gem_interactive_observe import latency
                        case['latency']=latency(b,p,foreign,folder,name=='latency-wrap',output)
                        return
                    if name in MEDIA_ERRORS or name in ('root-stop','input-busy','display-busy','client-allocation','renderer-allocation','app-signal','input-signal'):
                        return
                    if name in ('keyboard','early-escape'):
                        reach(f'(dw(${sy["input"]+24:x})=2)&(dw(${sy["client"]+12:x})!=0)')
                        if name=='early-escape':
                            key('ESC','down');b.bp_clear_all();return
                        press('A')
                    reach(f'{expr("initialReady")}=1')
                    storage=p['build']['task_storage']
                    live=[]
                    for slot,pool in enumerate(memory['task_pools']):
                        record=b.memdump(storage['BASE']+slot*storage['SIZE'],storage['SIZE'])
                        item=int.from_bytes(record[storage['TCB_ITEM']:storage['TCB_ITEM']+3],'little')
                        live.append(dict(slot=slot,task=item,state=record[storage['TCB_STATE']],pool=pool,record=record.hex()))
                    case['task_pools']=live
                    require(int.from_bytes(b.memdump(sy['boot']+12,3),'little')==live[6]['task'],'Application did not use slot 6')
                    require(int.from_bytes(b.memdump(sy['server']+8,4),'little')==live[7]['task'],'Renderer did not use slot 7')
                    case['renderer_owner']=int.from_bytes(b.memdump(sy['server']+4,4),'little')
                    require(case['renderer_owner']==live[6]['task'],'Root became renderer supervisor')
                    if name in ('escape-sio','escape-render'):
                        phase=p['labels']['SD_PHASE']; posts=p['labels']['SD_POSTS']
                        if name=='escape-render':
                            key('A','down'); reach(f'(dw(${sy["client"]+12:x})!=0)&({expr("received")}>0)')
                            key('A','up')
                        else:reach(f'(db(${phase:x})>0)&(db(${phase:x})<13)','native_irq')
                        case['exit_observation']=dict(phase=b.peek(phase)[0],terminal_posts=b.peek16(posts),pending=read('client',16)>>96)
                        key('ESC','down')
                    elif name=='raw-full':
                        b.memload(sy['holdInput'],b'\x01\x00'); reach(f'{expr("inputHeld")}=1')
                        capture=memory['input_storage']['CAPTURE']
                        for i in range(65):
                            previous=b.peek16(capture+10)
                            key('A' if i%2==0 else 'B','down')
                            reach(f'dw(${capture+10:x})!={previous}')
                            key('ALL','up'); frames(1)
                        case['raw_full']=b.memdump(capture,48).hex()
                        require(((b.peek(capture+1)[0]-b.peek(capture+2)[0])&255)==64,'Raw ring not full')
                        require(b.peek16(capture+44)!=0,'Raw loss not durable')
                        b.memload(sy['holdInput'],bytes(2)); reach(f'{expr("inputLosses")}>0'); key('ESC','down')
                    elif name in ('ready-exhausted','render-timeout','render-busy'):
                        idle()
                        if name=='ready-exhausted':
                            b.memload(sy['exhaustReady'],b'\x01\x00'); key('A','down')
                            reach(f'{expr("exhaustedReady")}=1'); key('A','up'); idle()
                            require(read('length')==1,'No redraw under exhaustion')
                            case['scanout_sha256']=pixels(b,folder,scene(output,b'a'))
                            key('ESC','down')
                        else:
                            if name=='render-busy':b.memload(sy['permanent'],b'\x01\x00')
                            b.memload(sy['faultNext'],b'\x01\x00'); key('A','down')
                    elif name in MOUSE_VARIANTS:
                        idle()
                        require(read('mouseStatus')==(2 if name=='mouse-busy' else 7), 'Wrong optional mouse status')
                        require(b.memdump(sy['mouseInput'],32)==bytes(32), 'Partial mouse admission retained a lease')
                        press('A'); idle()
                        require(read('length')==1, 'Keyboard fallback is not usable')
                        case['scanout_sha256']=pixels(b,folder,scene(output,b'a',cursor=None,mouse_status=read('mouseStatus')))
                        key('ESC','down')
                    elif name in ('keyboard','context'):
                        if name=='context':press('A')
                        press('B');press('BACKSPACE');press('TAB');press('RETURN');idle()
                        require(read('focus')==1 and read('count')==1 and read('length')==1 and b.memdump(sy['text'],1)==b'a','Keyboard state differs')
                        case['scanout_sha256']=pixels(b,folder,scene(output,b'a',1,1))
                        press('TAB');key('RETURN','down')
                    else:
                        if name in ('late-escape','break'):idle()
                        key('BREAK' if name=='break' else 'ESC','down')
                    b.bp_clear_all()
                def before(bridge):
                    interact(bridge)
                    if name=='render-busy':return
                    checkpoint=next(d['address'] for d in p['image']['data'] if '_CHECKPOINT_' in d['name'])
                    inst=memory['console_storage']['INSTANCE']; view=memory['console_storage']['PRESENTATION']
                    layout=console_constants()
                    instance=lambda field:inst+layout['INSTANCE_'+field]
                    presentation=lambda field:view+layout['PRESENTATION_'+field]
                    reach(f'(db(${checkpoint:x})=3)&(dw(${instance("DIRTYROWS"):x})=0)&'
                          f'(db(${instance("OPERATION"):x})=0)&(db(${presentation("CURSORON"):x})=1)&'
                          f'(dw(${presentation("PREVIOUSCURSOR"):x})='
                          f'dw(${instance("LINESTART"):x})+dw(${instance("COLUMN"):x}))')
                    payload=b'GEM disk error\nMount gem-vdi/graphics.atr\n' if name in MEDIA_ERRORS else (
                        b'GEM renderer failed\n' if name=='render-timeout' else b'GEM startup failed\n' if name in
                        ('input-busy','display-busy','client-allocation','renderer-allocation','app-signal','input-signal') else b'GEM session complete\n')
                    if name=='no-disk':payload+=b'SIO offline; reset required\n'
                    expected=terminal(payload); pointer=lambda a:int.from_bytes(b.memdump(a,3),'little')
                    require(read_cells(b.memdump,inst)==expected[0],'Completion text differs')
                    require(b.memdump(pointer(view+3),960)==expected[1],'Completion scanout differs')
                    case['completion_text']=payload.decode(); b.bp_clear_all()
                runtime,_=execute(b,{**p,'output':folder},before_run=before,expected_status=0xff93 if name in ('no-disk','render-busy') else 0,frame_limit=24000,timeout=360)
                key('ALL','up')
                case.update(runtime=runtime,checks=read('checks'),failures=read('failures'),first_failure=read('firstFailure'),
                    media_error=data(b,p['image'],'mediaError',True)[0],
                    counters={k:read(k) for k in ('received','submitted','collected','inputWhilePending','maxCommands','maxGlyphs')},
                    stack_usage=stack_usage(b,memory))
                if name=='render-busy':
                    require(read('faultInjected')==1 and read('stopped')==1 and not read('finished'),'No permanent-busy park')
                    require(b.peek16(sy['display']+17)&255==4,'Faulted display released')
                    require(read('input',26)>>192==2,'Input ownership released before renderer quiescence')
                    require(all(int.from_bytes(b.memdump(sy['server']+o,n),'little') for o,n in ((8,4),(12,3),(24,3),(36,4),(40,4),(56,4))), 'Renderer resources freed')
                    pending=int.from_bytes(b.memdump(sy['client']+12,4),'little')
                    require(pending==int.from_bytes(b.memdump(sy['client']+8,4),'little')!=0,'Pending packet lost')
                    case.update(status='pass',retained_request=b.memdump(pending,236).hex()); continue
                require(read('finished')==1 and not read('failures'),'Incomplete application/assertion failure')
                require(b.peek16(sy['boot']+42)==1,'Application did not retire')
                require(b.memdump(sy['input'],32)==bytes(32) and b.memdump(sy['mouseInput'],32)==bytes(32),'Input lease leaked')
                require(read('submitted')==read('collected'),'Render packet leaked')
                require(runtime['root_task'][16:20]==[255,255,0,0],'Root signal leaked')
                require(b.memdump(sy['boot']+24,12)==bytes(12) and
                        b.memdump(sy['selfLease'],12)==bytes(12) and b.memdump(sy['rootLease'],12)==bytes(12),'Application Task lease leaked')
                require(all(b.memdump(sy['server']+o,n)==bytes(n) for o,n in
                            ((8,4),(12,12),(24,12),(36,8),(56,8),(80,4))),'Renderer resource leaked')
                require(read('outstanding')==0 and read('closed')==1 and read('uiQueued')==0,'Control/queue ownership remains')
                if name=='keyboard':require(read('inputWhilePending')>0,'No input during outstanding rendering')
                require(case['media_error']==MEDIA_ERRORS.get(name,0),'Wrong media result')
                if name=='render-timeout':
                    require(read('faultInjected')==1 and read('stopped')==1,'Fault did not follow hardware launch')
                    require(data(b,p['image'],'runtimeError',True)[0]==6,'Lost renderer error')
                if name=='context':
                    for slot in (0,6,7):
                        dp=memory['task_pools'][slot]['dp']
                        require(b.memdump(dp+20,108)==pattern(slot)[20:],'C lower DP changed')
                    require(b.memdump(memory['task_pools'][0]['dp']+8,8)==pattern(0)[8:16],'C preserved registers changed')
                    require(b.memdump(adapter.KERNEL_DP,128)==pattern(4),'Kernel DP changed')
                case['hardware_before']=saved
                case['hardware_after']=hardware()
                require(b.memdump(0x8000,4096)==aperture,'Mapped aperture RAM changed')
                if name!='no-disk':
                    clean_ownership(b,p,p['output'])
                    require(hardware()==saved,'OS/keyboard hardware not restored')
                else:
                    for key in ('key_vector','break_vector','display','memac'):
                        require(hardware()[key]==saved[key],'Keyboard/display retained with offline SIO: '+key)
                if name in ('input-busy','display-busy','client-allocation','renderer-allocation','app-signal','input-signal'):
                    require(data(b,p['image'],'startError',True)[0]!=0,'Startup conflict was not rejected')
                case['status']='pass'
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        if report['cases']:report['cases'][-1].update(status='fail',error=str(error))
        raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Interactive',mode,'pass:',','.join(c['name'] for c in report['cases']),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['raw','opt'],default='opt');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append');p.add_argument('--replay',action='store_true');p.add_argument('--production',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.case,a.replay,a.production)
