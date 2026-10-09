#!/usr/bin/env python3
"""Standalone input lease/routes and physical native keyboard capture."""
import json
from stack_budget import current_task_memory
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_cooperative import data
from test_heap_api import clean_ownership
from test_mouse_observe import PIN, BRIDGE, ROM


def run(output, mode, replay=False, input_diagnostics=False):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='I3',mode=mode,cases=[])
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],
                'Wrong capture emulator')
        (output/'program').mkdir(exist_ok=True)
        source=output/'program/input_capture.act'
        source.write_bytes((ROOT/'tests/programs/input_capture.act').read_bytes())
        p=read_build(output/'program') if replay else build(compiler(ROOT/'build/actionc'),
            source,output/'program',optimize=mode=='opt',
            tasks=True,task_capacity=8,console=False,input_diagnostics=input_diagnostics)
        require(p['build']['input_diagnostics']==input_diagnostics,'Wrong input diagnostics')
        require(not p['build'].get('console_enabled') and not p['build'].get('console_test'),
                'Standalone capture accidentally enabled console')
        require(p['build']['optimize']==(mode=='opt'),'Wrong compiler mode')
        baseline=current_task_memory()
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(p['build']['memory'][key]==baseline[key],'Input changed '+key)
        report.update(build=p['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),
            xex_sha256=sha256(p['xex']),bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
        at=lambda name:next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_INPUTTEST_'+name.upper()+'_'))
        with emulator(BRIDGE,ROM,output,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            case=dict(name='capture',status='running',stimuli=[])
            report['cases'].append(case)
            hardware=lambda:{k:b.memdump(a,n).hex() for k,a,n in (
                ('mask',16,1),('skctl',0x232,1),('key_vector',0x208,2),('break_vector',0x236,2))}
            saved={}
            def checkpoint(condition):
                b.bp_clear_all()
                b.bp_set(p['labels']['native_nmi'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                try:run_to(b,p['labels']['native_nmi'],frame_limit=1500,timeout=90,condition=condition)
                except Exception:
                    raise RuntimeError('Input stopped: status='+hex(b.peek16(adapter.STATE))+', checks='+str(b.peek16(at('checks'))))
            def key(name,state):
                r=b._cmd_ok(f'KEY {name} {state}')
                require(r['raw_scan'],'Not physical keyboard scanning')
                case['stimuli'].append(dict(key=name,state=state,frame=b.eval_expr('@frame')))
            def frames(n):checkpoint(f'@frame>={b.eval_expr("@frame")+n}')
            def before(bridge):
                saved.update(hardware())
                key('ALL','up')
                checkpoint(f'db(${at("stage"):x})=1')
                stimuli = [('A',None),('A','SHIFT'),('ESC',None),('C','CTRL'),('BREAK',None),
                           ('ESC',None),('C','CTRL'),('BREAK',None)]
                for index,(name,modifier) in enumerate(stimuli):
                    if index == 5:
                        checkpoint(f'db(${at("stage"):x})=2')
                    if modifier:key(modifier,'down')
                    key(name,'down')
                    if index==7:
                        b.bp_clear_all()
                        break
                    checkpoint(f'db(${at("received"):x})>={index+1}')
                    key(name,'up')
                    if modifier:key(modifier,'up')
                    frames(4)
            runtime,_=execute(b,p,before_run=before,frame_limit=5000,timeout=120)
            key('ALL','up')
            raw=b.memdump(at('events'),8*24)
            events=[]
            for i in range(8):
                r=raw[i*24:i*24+24]
                events.append(dict(acquisition=int.from_bytes(r[:4],'little'),route=int.from_bytes(r[4:8],'little'),
                    tick=int.from_bytes(r[8:10],'little'),kind=r[10],flags=r[11],code=int.from_bytes(r[12:14],'little'),
                    qualifiers=int.from_bytes(r[14:16],'little')))
                require(r[16:]==bytes(8),'Unused event fields not zero')
            require([(e['kind'],e['code'],e['qualifiers']) for e in events]==[
                    (1,63,0),(1,127,1),(5,2,0),(5,2,0),(5,1,0),
                    (1,28,0),(1,146,2),(5,1,0)],
                    'Wrong physical events: '+str(events))
            require([e['flags'] for e in events]==[1,1,0,0,0,1,1,0],'Invented/lost timestamps')
            require(all(e['acquisition']==2 and e['route'] for e in events),'Stale acquisition/route')
            require(len({e['route'] for e in events[:5]}) == 1 and
                    len({e['route'] for e in events[5:]}) == 1 and
                    events[0]['route'] != events[5]['route'], 'Route policy did not switch')
            require(hardware()==saved,'Keyboard hardware was not restored')
            clean_ownership(b,p,p['output'])
            case.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),events=events,
                        hardware_before=saved,hardware_after=hardware(),stack_usage=stack_usage(b,p['build']['memory']))
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        if report['cases']:report['cases'][-1].update(status='fail',error=str(error))
        raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Input',mode,'capture pass',flush=True)
    return report
