#!/usr/bin/env python3
"""Exact cursor/scene pixels, rejected packets and fenced phase failures."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
from build_gem_cursor import build_cursor
from native_program import ROOT,execute,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from gem_render_oracle import Raster,font_bytes
from test_gem_interactive import pixels,PIN
from test_heap_api import clean_ownership
from stack_budget import stack_usage
ARROW=('X...............','XX..............','XOX.............','XOOX............',
       'XOOOX...........','XOOOOX..........','XOOOOOX.........','XOOOOOOX........',
       'XOOOOOOOX.......','XOOOOXXXXX......','XOOXOX..........','XOX.OX..........',
       'XX..XOX.........','X...XOX.........','.....XX.........','................')

def overlay(model,cursor):
    raw=bytearray(model.pixels)
    if cursor:
        x,y=cursor
        for row,line in enumerate(ARROW):
            for col,char in enumerate(line):
                if char!='.' and 0<=x+col<640 and 0<=y+row<240:
                    raw[(y+row)*640+x+col]=15 if char=='X' else 0
    return bytes((a<<4)|b for a,b in zip(raw[::2],raw[1::2]))

def run(output,mode,replay=False,unquiesced=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='I5',mode=mode,cases=[])
    try:
        if replay:p,foreign=read_build(output/'program'),json.loads((output/'c-image.json').read_text())
        else:p,foreign=build_cursor(output,mode=='opt')
        sy=foreign['symbols'];memory=p['build']['memory']
        report.update(build=p['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),xex_sha256=sha256(p['xex']),
            bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0),layout=foreign['provenance']['checked_layout'])
        baseline=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for k in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[k]==baseline[k],'Bank-zero change: '+k)
        model=Raster(font_bytes(output/'selected/src/vdi/font8x8.c'))
        cursor=None;n=1
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=PIN) as b:
            report['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            get=lambda name,size=2:int.from_bytes(b.memdump(sy[name],size),'little')
            put=lambda name,value:b.memload(sy[name],(value&65535).to_bytes(2,'little'))
            def reach(number):
                c=f'(dw(${sy["checkpoint"]:x})={number})&(db(${adapter.CURRENT:x})=0)'
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=c)
                run_to(b,p['labels']['native_nmi'],condition=c,frame_limit=3000,timeout=60)
            def operation(name,op,points=(),values=(),bad=0,status=0,fault=0,terminal=False):
                nonlocal n,cursor
                item=dict(name=name,status='running',opcode=op,points=points,ints=values,bad=bad,fault=fault)
                report['cases'].append(item)
                sequence=int.from_bytes(b.memdump(sy['server']+72,4),'little')
                phases=get('phases');starts=get('starts')
                cursor_before={k:get(k) for k in ('cursorX','cursorY','cursorVisible','cursorDrawn')}
                put('opcode',op);put('pairs',len(points)//2);put('words',len(values));put('bad',bad)
                put('faultPoint',fault);put('faultSeen',0);put('inject',0);put('stopped',0)
                if terminal:put('permanent',1)
                b.memload(sy['points'],b''.join((v&65535).to_bytes(2,'little') for v in points))
                b.memload(sy['ints'],b''.join((v&65535).to_bytes(2,'little') for v in values))
                put('gate',n);n+=1
                if terminal:b.bp_clear_all();return
                reach(n)
                item.update(result=get('answer'),completed=get('completed'),reply_words=get('replyWords'),
                            sequence_before=sequence,sequence_after=int.from_bytes(b.memdump(sy['server']+72,4),'little'),
                            cursor_before=cursor_before,cursor_after={k:get(k) for k in cursor_before},
                            phase_calls=get('phases')-phases,blits_started=get('starts')-starts)
                require(item['result']==status,f'{name}: status {item["result"]} != {status}')
                if bad:
                    require(item['sequence_before']==item['sequence_after'] and item['cursor_before']==item['cursor_after'] and
                            item['phase_calls']==0 and item['blits_started']==0,'Rejected packet mutated renderer')
                if fault:
                    require(get('faultSeen')==fault and get('stopped')==1 and item['blits_started']>0,'Fault did not follow hardware launch')
                    require(int.from_bytes(b.memdump(sy['server']+68,4),'little')==0,'Fault kept session live')
                    cursor=None
                elif not status:
                    if op==0xff00:
                        cursor=(points[0],points[1]) if values[0] else None
                        require(item['completed']==0 and item['reply_words']==0,'Cursor returned VDI output')
                        require(item['sequence_after']==sequence+1,'Cursor sequence did not advance')
                    elif op==2:cursor=None
                    else:
                        model.apply(op,points,values)
                        if op==1:cursor=None
                if not fault and op!=2:
                    # Let a complete display frame use the fenced scene.
                    frame=b.eval_expr('@frame');condition=f'@frame>={frame+2}'
                    b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                    run_to(b,p['labels']['native_nmi'],condition=condition,frame_limit=30,timeout=10)
                    folder=output/name;folder.mkdir(exist_ok=True)
                    item['scanout_sha256']=pixels(b,folder,overlay(model,cursor))
                item['status']='pass'
            def before(bridge):
                reach(1)
                operation('open',1)
                operation('blue',25,values=[4]);operation('background',11,[0,0,639,239])
                operation('green-text',22,values=[3]);operation('title',8,[17,46],list(b'Cursor'))
                operation('red-line',17,values=[2]);operation('line',6,[0,0,639,239])
                operation('clip',129,[10,10,629,229],[1]);operation('magenta',25,values=[7])
                operation('panel',11,[16,16,160,120])
                for i,xy in enumerate([(0,0),(1,0),(21,41),(22,41),(639,0),(0,239),(639,239),(625,225),(626,226),(320,120)]):
                    operation('move-'+str(i),0xff00,xy,[1])
                operation('hide',0xff00,[320,120],[0])
                operation('stationary',0xff00,[20,40],[1])
                operation('under-color',25,values=[3]);operation('under-bar',11,[0,0,60,80])
                operation('under-text',8,[17,46],list(b'Changed'))
                operation('under-line',6,[0,20,80,100]);operation('restored-new-background',0xff00,[20,40],[0])
                operation('before-invalid',0xff00,[21,41],[1])
                operation('edge-color',25,values=[5])
                operation('saved-edge-nibble',11,[20,41,20,56])
                operation('disjoint-text',8,[300,64],list(b'outside'))
                operation('edge-restored',0xff00,[21,41],[0])
                operation('edge-visible',0xff00,[21,41],[1])
                for bad in range(1,14):
                    operation('invalid-'+str(bad),0xff00,[500,200],[1],bad=bad,status=3 if bad in (11,12) else 1 if bad==13 else 2)
                operation('close',2);operation('reopen-hidden',1)
                operation('old-attributes-reset',6,[0,0,639,239])
                operation('new-session-cursor',0xff00,[41,41],[1])
                if unquiesced:
                    operation('unquiesced-draw',0xff00,[80,60],[1],fault=4,terminal=True)
                    return
                for fault in range(1,5):
                    operation('fault-'+str(fault),0xff00,[80,60],[1],fault=fault,status=6)
                    operation('reopen-'+str(fault),1)
                    operation('show-'+str(fault),0xff00,[41,41],[1])
                put('opcode',0xffff);put('gate',n);b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,expected_status=0xff93 if unquiesced else 0,frame_limit=24000,timeout=360)
            report.update(runtime=runtime,checks=get('checks'),failures=get('failures'),stack_usage=stack_usage(b,memory))
            require(not get('failures'),'Target assertion failure')
            if unquiesced:
                require(get('faultSeen')==4 and get('stopped')==1 and not get('finished'),'Missing permanent-busy park')
                pending=int.from_bytes(b.memdump(sy['client']+12,4),'little')
                require(pending and pending==int.from_bytes(b.memdump(sy['client']+8,4),'little'),'Pending cursor lost')
                require(b.peek16(sy['display']+17)&255==4,'Faulted display lease was released')
                require(all(int.from_bytes(b.memdump(sy['server']+o,n),'little') for o,n in [(8,4),(12,3),(24,3),(36,4),(40,4),(56,4)]),'Renderer resources freed')
                report['cases'][-1]['status']='pass'
                report['retained_request']=b.memdump(pending,164).hex()
            else:
                require(get('finished')==1,'Controller did not retire')
                clean_ownership(b,p,p['output'])
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        if report['cases']:report['cases'][-1].update(status='fail',error=str(error))
        raise
    finally:(output/('unquiesced-results.json' if unquiesced else 'results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Cursor',mode,'pass',len(report['cases']),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['raw','opt'],default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--unquiesced',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.replay,a.unquiesced)
