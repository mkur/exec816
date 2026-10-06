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
from aes_timing_breakdown import (scheduler_markers, caller_markers, input_breakdown,
                                  caller_breakdown)
from desktop_mouse import schedule
from measure_desktop import distribution


def run(out,program,frames=100,load='idle',breakdown=False,offer_period=0,button_period=0,
        continuous=False):
    require(frames > 0 and offer_period >= 0 and button_period >= 0, 'Invalid diagnostic cadence')
    require(not button_period or breakdown, 'Button diagnostic requires --breakdown')
    require(not (continuous and offer_period), 'Choose continuous or fixed offers')
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(program);foreign=json.loads((p['output'].parent/'c-image.json').read_text())
    marks=markers(p,foreign)
    _,_,costs=observers(p)
    costs['spans'].update(native_markers(p,[(name,name.lower()) for name in (
        'DESKHOST_CONTROLS','AESCORE_DISPATCH','CONSOLEDRIVER_WRITEQUANTUM')]))
    extra = {}
    if breakdown:
        scheduler = scheduler_markers(p)
        scheduler['selected'] = costs['points']['selected']
        sites = caller_markers(p,foreign)
        extra.update(scheduler['points'])
        extra.update(capture=p['labels']['pointer_notify'])
        for pc, site in sites.items():
            extra['call_'+str(pc)] = pc
            extra['return_'+str(pc)] = site['end']
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(
        f'{pc:x}' for pc in set([*marks.values(),*flat_markers(costs).values(),*extra.values()])))
    for key in ('EXEC816_MASK_TRACE','EXEC816_MOUSE_TRACE'):os.environ.pop(key,None)
    at=lambda n:next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+n.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,marks=marks,
                xex_sha256=sha256(p['xex']),frames=frames,load=load,samples=[],
                diagnostic_only=bool(offer_period or button_period),
                reserved_bank_zero_delta=dict(fixed=0,per_public_task=[0]*8,idle=0))
    report['observer_sources']={name:sha256(Path(__file__).with_name(name)) for name in (
        'measure_aes_calls.py','aes_timing_breakdown.py','aes_latency_trace.py','console_turn_profile.py')}
    report.update(cost_definition=costs,breakdown_enabled=breakdown)
    if breakdown: report.update(scheduler_markers=scheduler,caller_sites=sites)
    media=out/'media/TOOLS/SUB';media.mkdir(parents=True,exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk=out/'disk.atr';make(disk,out/'media',binary_names={'TOOLS/SUB/DATA.BIN'},filesystem='sdfs')
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.mount(0,str(disk))
            if button_period: b._cmd_ok('MOUSE ST')
            report['machine']=verify_machine(b,ROM,PIN)
            def before(bridge):
                b.profile_start()
                def reach(condition):
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    run_to(b,p['labels']['native_irq'],condition=condition,frame_limit=8000,timeout=120)
                reach(f'dw(${at("ready"):x})=1')
                sy=foreign['symbols']
                if continuous:
                    require(b.peek16(sy['AESCommand']) == 0, 'Continuous control requires initially parked clients')
                    b.poke16(sy['AESCommand'],5)
                reach(f'@frame>={b.eval_expr("@frame")+160}')
                if offer_period:
                    require(all(n in sy for n in ('AESOffered','AESStarted','AESCompleted')),
                            'Rebuild desktop for the fixed-offer diagnostic')
                    require(b.peek16(sy['AESCommand']) == 0, 'Fixed offers require initially parked clients')
                    b.poke16(sy['AESCommand'],7)
                    reach(f'dw(${sy["AESPhase"]:x})=1')
                if button_period:
                    cursor=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
                    schedule(b,p,[320,120],(480,128))
                    reach(f'(dw(${cursor("cursorX"):x})=480)&(dw(${cursor("cursorY"):x})=128)')
                    reach(f'@frame>={b.eval_expr("@frame")+80}')
                mode={'idle':0,'scroll':2,'disk':3}[load]
                b.poke16(at('mode'),mode)
                reach(f'dw(${at("runningMode"):x})={mode}')
                if load=='disk':
                    # Mount/open metadata traffic precedes the first data read.
                    # Start the bounded distribution with the steady load live.
                    reach(f'dw(${at("reads"):x})>0')
                reads=b.peek16(at('reads'));writes=b.peek16(at('writes'))
                aes_before={n:b.peek16(sy[n]) for n in ('AESMessages','AESTimers')}
                report['aes_command']=b.peek16(sy['AESCommand'])
                begin=b.eval_expr('@clk') & 0xffffffff
                start_frame=b.eval_expr('@frame')
                end_frame=start_frame+frames
                offers=[]
                due_offer=start_frame if offer_period else end_frame
                due_button=start_frame+button_period//2 if button_period else end_frame
                down=0
                while min(due_offer,due_button)<end_frame:
                    due=min(due_offer,due_button)
                    reach(f'@frame>={due}')
                    actual=b.eval_expr('@frame')
                    require(actual==due, 'Missed external workload frame; do not silently catch up')
                    clock=b.eval_expr('@clk') & 0xffffffff
                    if due==due_offer:
                        number=len(offers)+1
                        require(number<65536,'Offer counter exhausted')
                        offers.append(dict(number=number,frame=actual,clock=clock,
                            started=b.peek16(sy['AESStarted']),completed=b.peek16(sy['AESCompleted'])))
                        b.poke16(sy['AESOffered'],number)
                        due_offer+=offer_period
                    if due==due_button:
                        if report['samples']: report['samples'][-1]['observed']=clock
                        down^=1
                        report['samples'].append(dict(submitted=clock,frame=actual,button=down))
                        b._cmd_ok('MOUSE AT 2000 0 0 '+str(down))
                        due_button+=button_period
                reach(f'@frame>={end_frame}')
                report['window']=[begin,b.eval_expr('@clk') & 0xffffffff]
                if report['samples']: report['samples'][-1]['observed']=report['window'][1]
                report['aes_progress']={n:(b.peek16(sy[n])-old)&65535 for n,old in aes_before.items()}
                report['progress']=dict(reads=b.peek16(at('reads'))-reads,writes=b.peek16(at('writes'))-writes)
                if offer_period:
                    offered=len(offers);started=b.peek16(sy['AESStarted']);completed=b.peek16(sy['AESCompleted'])
                    require(0<=completed<=started<=offered,'Invalid fixed-offer counters')
                    report['offered_load']=dict(period_frames=offer_period,start_frame=start_frame,
                        end_frame=end_frame,offered=offered,started=started,completed=completed,
                        pending=offered-completed,offers=offers,
                        scope='External frame-anchored offers; no completion feedback or dropped catch-up work. One request/reply and a 100 ms sender timer per offer; receiver uses a 5 s safety timeout between offers. Root AESPump signals the sender; admission delay remains part of the result.')
                    # Stop producing, drain every offer, then use the existing
                    # shutdown/ownership proof. Preserve backlog at window end.
                    reach(f'dw(${sy["AESCompleted"]:x})={offered}')
                    report['offered_load']['drained']=b.peek16(sy['AESCompleted'])
                if down:
                    b._cmd_ok('MOUSE AT 2000 0 0 0')
                if load=='disk':require(report['progress']['reads']>0,'Disk load made no progress')
                b.poke16(at('mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=8000)
            ownership(b,p,p['output'])
            report['ownership']='restored'
            meta=(p['output']/'timermeta.act').read_text()
            base=int(re.search(r'PUBLIC CONST BASE=\$([0-9a-f]+)',meta,re.I)[1],16)
            report['final_clock']=int.from_bytes(b.memdump(base+4,4),'little')
            for name in ('AESChecks','AESFailures','AESFirstFailure'):
                report[name]=int.from_bytes(b.memdump(foreign['symbols'][name],2),'little')
            require(report['AESFailures']==0,'GEM app failure')
            b.profile_stop()
        analyze_report(report,out,p)
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AES latency:',report['latency']['calls'],'calls;',report['latency']['expiry_count'],'expiries')


def analyze_report(report, out, p):
    costs=report['cost_definition']
    marks=report['marks']
    breakdown=report['breakdown_enabled']
    if breakdown:
        scheduler=report['scheduler_markers']
        sites=report['caller_sites']
    events=read_events(out/'emulator.log',kinds={'cpu'})
    window=[t+round((events[0][0]-t)/(1<<32))*(1<<32) for t in report['window']]
    report['latency']=analyze(events,marks,report['final_clock'],window)
    report['costs']=analyze_events(events,costs,window,allow_empty_window=True,
        intervals=[dict(dp=r['dp'],operation=r['operation'],transport=r['transport'],
                        start=r['start'],end=r['client']) for r in report['latency']['records']],
        include_segments=breakdown)
    if breakdown:
        profile=report['costs']
        report['caller_breakdown']=caller_breakdown(events,sites,profile['segments'],report['latency']['records'])
        if report['samples']:
            captures=[t for t,e in events if e[0]=='cpu' and int(e[4],16)==p['labels']['pointer_notify']]
            align=lambda t:t+round((events[0][0]-t)/(1<<32))*(1<<32)
            for sample in report['samples']:
                sample['observed']=align(sample['observed'])
                selected=[t for t in captures if align(sample['submitted'])<=t<=sample['observed']]
                require(len(selected)==1,'Missing or ambiguous diagnostic button capture')
                sample['capture']=selected[0]
            report['input_breakdown']=input_breakdown(events,scheduler,profile,report['samples'],costs['spans']['consume']['entry'])
            report['input_breakdown']['summary']={key:distribution([r[key] for r in report['input_breakdown']['records']])
                for key in ('capture_to_ready_ms','ready_to_selected_ms','selected_to_consume_ms',
                            'runnable_off_cpu_ms','blocked_off_cpu_ms','charged_cpu_ms','elapsed_ms')}
        profile.pop('segments')
        records=report['caller_breakdown']['records']
        report['caller_breakdown']['summary']={str(op):{
            key:distribution([r['exclusive_cpu_ms'].get(key,0) for r in records if r['operation']==op])
            for key in {k for r in records if r['operation']==op for k in r['exclusive_cpu_ms']}}
            for op in {r['operation'] for r in records}}
    if report['load']=='scroll':require(report['costs']['routines'].get('consoledriver_writequantum',{}).get('calls',0)>0,'Console load made no progress')
    report['trace_sha256']=sha256(out/'emulator.log')
    report['analysis_sources']={name:sha256(Path(__file__).with_name(name)) for name in (
        'aes_timing_breakdown.py','aes_latency_trace.py','console_turn_profile.py')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--program',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',type=int,default=100)
    p.add_argument('--load',choices=('idle','scroll','disk'),default='idle')
    p.add_argument('--breakdown',action='store_true',help='Passively split caller CPU and presenter scheduling delay')
    p.add_argument('--offer-period',type=int,default=0,metavar='FRAMES',help='Diagnostic fixed-rate offers to command 7; requires a parked-client build')
    p.add_argument('--continuous',action='store_true',help='Start the original continuous exchange on the same parked-client image')
    p.add_argument('--button-period',type=int,default=0,metavar='FRAMES',help='Diagnostic fixed-rate physical button edges; requires --breakdown')
    p.add_argument('--analyze-only',action='store_true',help='Recompute passive metrics after a completed guest run')
    a=p.parse_args()
    if a.analyze_only:
        out=a.output.resolve();report=json.loads((out/'results.json').read_text())
        require(report.get('ownership')=='restored' and report['AESFailures']==0,'Guest did not finish cleanly')
        program=read_build(a.program.resolve())
        require(sha256(program['xex'])==report['xex_sha256'],'Different diagnostic image')
        analyze_report(report,out,program)
        report['status']='pass';report.pop('error',None)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    else:
        run(a.output.resolve(),a.program.resolve(),a.frames,a.load,a.breakdown,a.offer_period,a.button_period,a.continuous)
