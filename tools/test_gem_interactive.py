#!/usr/bin/env python3
"""Focused interactive keyboard/lifetime checks on the pinned physical SIO machine."""
import argparse
import hashlib
import json
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
PIN=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
CASES=['keyboard','early-escape','late-escape','break','root-stop','input-busy','display-busy',
       'client-allocation','renderer-allocation','admission','wrong-disk','no-disk','short-file','corrupt-file']

def scene(output,text=b'',focus=0,count=0,progress=2048,done=True):
    r=Raster(font_bytes(output/'selected/src/vdi/font8x8.c'))
    labels=[b'GEM/Exec',text.ljust(24)[0:8],text.ljust(24)[8:16],text.ljust(24)[16:24],
            f'Count{count%1000:03}'.encode(),b'Exit    ',f'Disk{progress*100//2048:03}%'.encode(),b'Tab/Ente',
            b'Done    ' if done else b'Reading ']
    for tile,label in enumerate(labels):
        x=32+(tile-1)*64 if 1<=tile<=3 else 176 if tile==5 else 32
        y=24 if tile==0 else 64 if tile<=3 else 104 if tile<=5 else 144 if tile==6 else 168 if tile==7 else 184
        pen=2+count%14 if tile==4 else 0
        if (1<=tile<=3 and focus==0) or (tile==5 and focus==2):pen=6
        r.apply(25,ints=[pen]);r.apply(11,[x,y-10,x+63,y-8]);r.apply(22,ints=[2 if tile==4 and focus==1 else 1]);r.apply(8,[x,y],label)
    return r.packed()

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
    report=dict(status='running',tier='development',slice='I4',mode=mode,cases=[],production=production)
    try:
        if replay:
            p=read_build(output/'program');foreign=json.loads((output/'c-image.json').read_text())
        else:p,foreign=build_interactive(output,mode=='opt',not production)
        require(foreign['provenance']['diagnostic']==(not production),'Wrong instrumentation')
        sy=foreign['symbols'];memory=p['build']['memory']
        baseline=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for k in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[k]==baseline[k],'Bank-zero change: '+k)
        report.update(build=p['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),
            xex_sha256=sha256(p['xex']),media_sha256=sha256(output/'system.atr'),
            bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0),layout=foreign['provenance']['checked_layout'])
        for name in cases or ['keyboard']:
            folder=output/name;folder.mkdir(exist_ok=True)
            case=dict(name=name,status='running',stimuli=[]);report['cases'].append(case)
            with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
                b.config('diskemu','generic56k');disk=media(output,folder,name)
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
                def before(bridge):
                    saved.update(hardware())
                    b.memload(0x8000,aperture)
                    key('ALL','up')
                    if 'variant' in sy:b.memload(sy['variant'],CASES.index(name).to_bytes(2,'little'))
                    if name in MEDIA_ERRORS or name in ('root-stop','input-busy','display-busy','client-allocation','renderer-allocation'):
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
                    if name=='keyboard':
                        press('B');press('BACKSPACE');press('TAB');press('RETURN');idle()
                        require(read('focus')==1 and read('count')==1 and read('length')==1 and b.memdump(sy['text'],1)==b'a','Keyboard state differs')
                        case['scanout_sha256']=pixels(b,folder,scene(output,b'a',1,1))
                        press('TAB');key('RETURN','down')
                    else:
                        if name in ('late-escape','break'):idle()
                        key('BREAK' if name=='break' else 'ESC','down')
                    b.bp_clear_all()
                runtime,_=execute(b,{**p,'output':folder},before_run=before,expected_status=0xff93 if name=='no-disk' else 0,frame_limit=24000,timeout=360)
                key('ALL','up')
                case.update(runtime=runtime,checks=read('checks'),failures=read('failures'),first_failure=read('firstFailure'),
                    media_error=data(b,p['image'],'mediaError',True)[0],
                    counters={k:read(k) for k in ('received','submitted','collected','inputWhilePending','maxCommands','maxGlyphs')},
                    stack_usage=stack_usage(b,memory))
                require(read('finished')==1 and not read('failures'),'Incomplete application/assertion failure')
                require(b.peek16(sy['boot']+42)==1,'Application did not retire')
                require(b.memdump(sy['input'],32)==bytes(32),'Input lease leaked')
                require(read('submitted')==read('collected'),'Render packet leaked')
                if name=='keyboard':require(read('inputWhilePending')>0,'No input during outstanding rendering')
                require(case['media_error']==MEDIA_ERRORS.get(name,0),'Wrong media result')
                case['hardware_before']=saved
                case['hardware_after']=hardware()
                require(b.memdump(0x8000,4096)==aperture,'Mapped aperture RAM changed')
                if name!='no-disk':
                    clean_ownership(b,p,p['output'])
                    require(hardware()==saved,'OS/keyboard hardware not restored')
                else:
                    for key in ('key_vector','break_vector','display','memac'):
                        require(hardware()[key]==saved[key],'Keyboard/display retained with offline SIO: '+key)
                if name in ('input-busy','display-busy','client-allocation','renderer-allocation'):
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
