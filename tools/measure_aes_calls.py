#!/usr/bin/env python3
"""Bounded passive AES round-trip/deadline probe in the loaded GUI image."""
import argparse
import json
import os
import re
from pathlib import Path
import adapter_state as adapter
from aes_latency_trace import markers,analyze
from native_program import read_build,verify_machine,require,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from sio_transaction_trace import read_events
from bitmap_console_performance import native_markers
from console_turn_profile import flat_markers, analyze_events
from test_widget_panel import observers
from make_data_disk import make


def run(out,program,frames=100,load='idle'):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);foreign=json.loads((p['output'].parent/'c-image.json').read_text())
    marks=markers(p,foreign)
    _,_,costs=observers(p)
    costs['spans'].update(native_markers(p,[(name,name.lower()) for name in (
        'DESKHOST_CONTROLS','AESCORE_DISPATCH','AESEVENTS_WAIT','AESEVENTS_POLL',
        'AESTIMER_READ','AESTIMER_TARGET','TIMER_DEADLINE','CONSOLEDRIVER_WRITEQUANTUM')]))
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(
        f'{pc:x}' for pc in set([*marks.values(),*flat_markers(costs).values()])))
    for key in ('EXEC816_MASK_TRACE','EXEC816_MOUSE_TRACE'):os.environ.pop(key,None)
    at=lambda n:next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+n.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,marks=marks,
                xex_sha256=sha256(p['xex']),frames=frames,load=load)
    media=out/'media/TOOLS/SUB';media.mkdir(parents=True,exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk=out/'disk.atr';make(disk,out/'media',binary_names={'TOOLS/SUB/DATA.BIN'},filesystem='sdfs')
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.mount(0,str(disk))
            report['machine']=verify_machine(b,ROM,PIN)
            def before(bridge):
                b.profile_start()
                def reach(condition):
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    run_to(b,p['labels']['native_irq'],condition=condition,frame_limit=8000,timeout=120)
                reach(f'dw(${at("ready"):x})=1')
                reach(f'@frame>={b.eval_expr("@frame")+160}')
                mode={'idle':0,'scroll':2,'disk':3}[load]
                b.poke16(at('mode'),mode)
                reach(f'dw(${at("runningMode"):x})={mode}')
                if load=='disk':
                    # Mount/open metadata traffic precedes the first data read.
                    # Start the bounded distribution with the steady load live.
                    reach(f'dw(${at("reads"):x})>0')
                reads=b.peek16(at('reads'));writes=b.peek16(at('writes'))
                begin=b.eval_expr('@clk') & 0xffffffff
                reach(f'@frame>={b.eval_expr("@frame")+frames}')
                report['window']=[begin,b.eval_expr('@clk') & 0xffffffff]
                report['progress']=dict(reads=b.peek16(at('reads'))-reads,writes=b.peek16(at('writes'))-writes)
                if load=='disk':require(report['progress']['reads']>0,'Disk load made no progress')
                b.poke16(at('mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=8000)
            ownership(b,p,p['output'])
            meta=(p['output']/'timermeta.act').read_text()
            base=int(re.search(r'PUBLIC CONST BASE=\$([0-9a-f]+)',meta,re.I)[1],16)
            report['final_clock']=int.from_bytes(b.memdump(base+4,4),'little')
            for name in ('AESChecks','AESFailures','AESFirstFailure'):
                report[name]=int.from_bytes(b.memdump(foreign['symbols'][name],2),'little')
            require(report['AESFailures']==0,'GEM app failure')
            b.profile_stop()
        events=read_events(out/'emulator.log',kinds={'cpu'})
        window=[t+round((events[0][0]-t)/(1<<32))*(1<<32) for t in report['window']]
        report['latency']=analyze(events,marks,report['final_clock'],window)
        report['costs']=analyze_events(events,costs,window)
        if load=='scroll':require(report['costs']['routines'].get('consoledriver_writequantum',{}).get('calls',0)>0,'Console load made no progress')
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AES latency:',report['latency']['calls'],'calls;',report['latency']['expiry_count'],'expiries')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',type=int,default=100)
    p.add_argument('--load',choices=('idle','scroll','disk'),default='idle')
    a=p.parse_args();run(a.output.resolve(),a.program.resolve(),a.frames,a.load)
