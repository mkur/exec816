#!/usr/bin/env python3
"""Copied pointer stimuli published by a real diagnostic Task; exact scene pixels."""
import argparse
import json
import struct
from pathlib import Path
from types import SimpleNamespace
import adapter_state as adapter
from build_gem_interactive import build_interactive
from native_program import ROOT, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_gem_interactive import PIN, scene, pixels
from test_gem_cursor import overlay
from test_heap_api import clean_ownership
from stack_budget import stack_usage


def run(output, mode, replay=False):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='I5',mode=mode,cases=[])
    try:
        if replay: p,foreign=read_build(output/'program'),json.loads((output/'c-image.json').read_text())
        else: p,foreign=build_interactive(output,mode=='opt',True)
        sy=foreign['symbols']; memory=p['build']['memory']
        report.update(build=p['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),xex_sha256=sha256(p['xex']),
                      bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
        baseline=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for k in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[k]==baseline[k],'Bank-zero change: '+k)
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=PIN) as b:
            b.config('diskemu','generic56k'); b.mount(0,str(output/'system.atr'))
            report['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            get=lambda k,n=2:int.from_bytes(b.memdump(sy[k],n),'little')
            put=lambda k,v:b.memload(sy[k],(v&65535).to_bytes(2,'little'))
            ex=lambda k:f'dw(${sy[k]:x})'
            seq=0
            def reach(condition,label='native_nmi'):
                b.bp_clear_all(); b.bp_set(p['labels'][label],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                try: run_to(b,p['labels'][label],condition=condition,frame_limit=4000,timeout=60)
                except Exception:
                    report['debug']={k:get(k) for k in ('initialReady','finished','failures','firstFailure','injectRequest','injectDone','injectQueued','injectLost','uiQueued','uiLoss','inputLosses','pointerEvents','pointerReady','count','armed','dirty','pointerDirty','holdCursor','cursorHeld')}
                    report['debug']['state']=b.peek16(adapter.STATE)
                    raise
            def frames(n): reach(f'@frame>={b.eval_expr("@frame")+n}')
            def idle():
                reach(f'({ex("dirty")}=0)&({ex("pointerDirty")}=0)&({ex("uiQueued")}=0)&({ex("uiLoss")}=0)&(dw(${sy["client"]+12:x})=0)&(dw(${sy["client"]+14:x})=0)&(dw(${sy["boot"]+46:x})=1)')
                frames(2)
            def event(x=50,y=100,buttons=0,kind=2,**changes):
                values=dict(acquisition=get('input',16)>>96,route=int.from_bytes(b.memdump(sy['input']+16,4),'little'),
                            tick=0,kind=kind,flags=0,code=1 if kind==3 else 0,qualifiers=0,x=x,y=y,buttons=buttons,reserved=0)
                values.update(changes)
                return struct.pack('<IIHBBHHhhHH',*values.values())
            def publish(name,events,expected=None,wait=True):
                nonlocal seq
                seq+=1
                b.memload(sy['injectEvents'],b''.join(events)); put('injectCount',len(events)); put('injectRequest',seq)
                if not wait: return
                reach(f'{ex("injectDone")}={seq}')
                statuses=list(struct.unpack('<'+'H'*len(events),b.memdump(sy['injectResults'],len(events)*2)))
                item=dict(name=name,status='pass',events=[e.hex() for e in events],results=statuses,
                          queued=get('injectQueued'),loss=get('injectLost'),pending=get('injectWhilePending'),ack_phase=get('injectAckPhase'))
                report['cases'].append(item)
                require(statuses==(expected if expected is not None else [0]*len(events)),'Pointer publication status: '+name)
                return item
            def picture(name,focus,count,position):
                idle(); folder=output/name; folder.mkdir(exist_ok=True)
                packed=scene(output,focus=focus,count=count,cursor=None)
                model=SimpleNamespace(pixels=bytes(v for pair in packed for v in (pair>>4,pair&15)))
                digest=pixels(b,folder,overlay(model,position))
                report['cases'].append(dict(name=name,status='pass',scanout_sha256=digest))
            def click(name,x=50,y=100): publish(name,[event(x,y,1,3),event(x,y,0,3)])
            def before(bridge):
                put('variant',100)
                reach(f'{ex("initialReady")}=1'); idle()
                before_coalesce=get('uiCoalesced')
                item=publish('adjacent-motion',[event(20,40),event(21,40),event(22,40)])
                require(item['queued']==1 and get('uiCoalesced')==before_coalesce+2,'Motion not coalesced')
                picture('coalesced-pixels',0,0,(22,40))
                click('inside-click'); picture('first-click',1,1,(50,100))
                publish('outside-release',[event(50,100,1,3),event(120,100,0,3)])
                picture('outside-pixels',1,1,(120,100))
                publish('duplicate-edges',[event(50,100,1,3),event(50,100,1,3),event(50,100,0,3),event(50,100,0,3)])
                picture('duplicate-pixels',1,2,(50,100))
                put('holdCursor',1); publish('held-motion',[event(300,120)])
                reach(f'{ex("cursorHeld")}=1')
                address=int.from_bytes(b.memdump(sy['client']+12,4),'little'); packet=b.memdump(address,164)
                item=publish('click-during-cursor',[event(50,100,1,3),event(50,100,0,3)])
                require(item['pending']==1,'No outstanding cursor request')
                reach(f'{ex("count")}=3')
                require(b.memdump(address,164)==packet,'Pending cursor packet was mutated')
                put('holdCursor',0); picture('concurrent-pixels',1,3,(50,100))
                before_events=get('pointerEvents'); before_packets=get('cursorPackets')
                bad=[dict(acquisition=0),dict(route=0),dict(x=-1),dict(x=640),dict(y=-1),dict(y=240),
                     dict(buttons=2),dict(flags=4),dict(qualifiers=4),dict(code=1),dict(reserved=1),dict(tick=1),dict(kind=1)]
                publish('invalid-records',[event(**v) for v in bad],[4,4]+[3]*11); idle()
                require(get('pointerEvents')==before_events and get('cursorPackets')==before_packets,'Rejected pointer mutated state')
                publish('arm-before-loss',[event(50,100,1,3)]); reach(f'{ex("armed")}=1')
                overflow=[event(50,100,i%2,3) for i in range(33)]
                item=publish('full-queue',overflow,[0]*32+[5]); require(item['loss']==1 and item['queued']==0,'Overflow not latched')
                reach(f'{ex("inputLosses")}=1'); require(get('armed')==65535 and get('pointerReady')==0,'Loss did not disarm')
                publish('release-after-loss',[event(50,100,0,3)]); idle(); require(get('count')==3,'Lost click activated')
                click('fresh-click'); picture('fresh-pixels',1,4,(50,100))
                put('holdLossAck',1)
                publish('acknowledgment-loss',overflow,[0]*32+[5],wait=False)
                reach(f'{ex("lossAck")}=1')
                put('holdLossAck',0)
                item=publish('arrival-during-loss-ack',overflow,[0]*32+[5])
                require(item['ack_phase']==0,'Producer entered atomic acknowledgment')
                reach(f'{ex("inputLosses")}=3')
                publish('resynchronize',[event(50,100)])
                click('click-after-ack'); picture('ack-pixels',1,5,(50,100))
                click('field-focus',50,60); picture('field-pixels',0,5,(50,60))
                click('exit',190,100); b.bp_clear_all()
            runtime,_=execute(b,{**p,'output':output},before_run=before,frame_limit=24000,timeout=360)
            require(get('finished')==1 and get('failures')==0,'Application failure')
            require(get('submitted')==get('collected'),'Packet leaked')
            require(b.memdump(sy['input'],32)==bytes(32),'Input lease leaked')
            require(get('injectorRetired')==1 and get('closed')==1 and not get('uiQueued'),'Producer/queue still live')
            clean_ownership(b,p,p['output'])
            report.update(runtime=runtime,stack_usage=stack_usage(b,memory),
                          counters={k:get(k) for k in ('pointerEvents','pointerActivations','inputLosses','cursorPackets','uiOverflow','uiCoalesced','checks','failures')},status='pass')
    except Exception as e:
        report.update(status='fail',error=str(e)); raise
    finally: (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Pointer',mode,'pass',len(report['cases']),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['raw','opt'],default='opt'); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replay',action='store_true'); a=p.parse_args(); run(a.output,a.mode,a.replay)
