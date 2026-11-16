#!/usr/bin/env python3
"""Small Counter input/UPDATE ownership case; no application catalog or demo."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_aes_desktop import counter_image, counter_bindings
from build_bitmap_console import prepare
from desktop_mouse import schedule
from generate_aes_server import expected_layout
from generate_display import ABI as DISPLAY_ABI
from generate_memory import PROFILE
from generate_mouse_acceleration import metadata
from native_program import ROOT, build, compiler, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def build_fixture(out):
    foreign=counter_image(out,True)
    source=out/'counters.act'
    source.write_text(counter_bindings((ROOT/'tests/programs/input_device_gui.act').read_text(),foreign))
    launcher=prepare(source,out,foreign,desktop=True,aes=True)
    text=launcher.read_text()
    needle='  IF CONSOLEDRIVER.Start()=0 THEN'
    require(text.count(needle)==1,'GUI startup boundary changed')
    launcher.write_text(text.replace(needle,'  StartupProbe()\n'+needle))
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',
        tasks=True,task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,optimize=True)
    program['build']['desktop_mouse']=metadata(None)
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


def run(out,p,trace=False):
    p['build'].setdefault('desktop_mouse',metadata(None))
    foreign=json.loads((p['output'].parent/'c-image.json').read_text())
    sy=foreign['symbols'];layout=dict(expected_layout())
    at=lambda module,name:next(d['address'] for d in p['image']['data']
        if '_'+module+'_'+name.upper()+'_' in d['name'])
    from input_device_timing import setup,restore,result
    timing=setup(p) if trace else None
    idle=[]
    report=dict(status='running',tier='development',qualification=False,
        emulator_sha256=sha256(BRIDGE/'AltirraBridgeServer'),cases=[])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            def get(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                try:run_to(b,p['labels']['native_nmi'],condition=condition,timeout=30,frame_limit=1800)
                except Exception:
                    report['checkpoint']=condition
                    report['diagnostic']={'status':b.peek16(adapter.STATE),
                        'checks':get(at('INPUTDEVICEGUI','checks')),
                        'failure':get(sy['GEMCountersFailure']),
                        'cursor':[get(at('DESKINPUT',name)) for name in ('cursorX','cursorY')],
                        'inboxes':[dict(address=get(sy['CounterInputInbox']+i*4,4),
                            tail=get(get(sy['CounterInputInbox']+i*4,4)+layout['InputInbox keyTail'],1))
                            for i in range(2)]}
                    raise
            def frames(count=4):reach('@frame>='+str(b.eval_expr('@frame')+count))
            position=[320,120]
            def move(x,y):
                nonlocal position
                for attempt in range(12):
                    current=[get(at('DESKINPUT',name)) for name in ('cursorX','cursorY')]
                    if current==[x,y]:
                        position=current
                        return
                    schedule(b,p,current,(x,y));frames(20)
                raise RuntimeError('Pointer did not reach requested point')
            def before(b):
                if timing:b.profile_start()
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                reach('dw($%x)=1'%at('INPUTDEVICEGUI','ready'));frames(40)
                require(get(sy['GEMCountersFailure'])==0,'Counter startup failed')
                idle.append(b.eval_expr('@clk'));frames(20);idle.append(b.eval_expr('@clk'))
                move(280,100)
                b._cmd_ok('MOUSE AT 2000 0 0 1');frames()
                b._cmd_ok('MOUSE AT 2000 0 0 0');frames(40)
                # B stays in its normal native Task, paused before event consumption.
                b.poke16(sy['CounterPause']+2,1)
                reach('dw($%x)=1'%(sy['CounterHeld']+2))
                inbox=get(sy['CounterInputInbox']+4,4)
                require(inbox!=0,'Missing B input inbox')
                key=inbox+layout['InputInbox keyTail']
                button=inbox+layout['InputInbox buttonTail']
                key_before=get(key,1);button_before=get(button,1)
                b.poke16(sy['CounterInputHold'],1)
                reach('dw($%x)=1'%sy['CounterInputHeld'])
                # A owns UPDATE. Ordinary B input and console acceptance continue.
                b._cmd_ok('KEY A down')
                reach('db($%x)!=%d'%(key,key_before));b._cmd_ok('KEY A up')
                move(280,124)
                b._cmd_ok('MOUSE AT 2000 0 0 1');frames()
                b._cmd_ok('MOUSE AT 2000 0 0 0')
                reach('db($%x)=%d'%(button,(button_before+2)%256))
                b.poke16(at('INPUTDEVICEGUI','writeCommand'),1)
                reach('dw($%x)=2'%at('INPUTDEVICEGUI','writeCommand'))
                require(get(sy['CounterInputHeld'])==1,'UPDATE owner escaped the contention case')
                report['cases'].append('key/button inbox and console write while A owns UPDATE')
                # Title interaction waits for manager ownership; capture stays live.
                move(280,100);b._cmd_ok('MOUSE AT 2000 0 0 1');frames()
                b._cmd_ok('MOUSE AT 2000 0 0 0');frames()
                require(get(sy['CounterInputHeld'])==1,'Native interaction stole UPDATE')
                b.poke16(sy['CounterInputHold'],0)
                reach('dw($%x)=0'%sy['CounterInputHeld'])
                b.poke16(sy['CounterPause']+2,0);frames(30)
                report['cases'].append('retained manager interaction resumes after UPDATE')
                b.poke16(sy['CounterPause']+2,1)
                reach('dw($%x)=1'%(sy['CounterHeld']+2))
                b.poke16(at('INPUTDEVICEGUI','grantCommand'),1)
                reach('dw($%x)=1'%at('INPUTDEVICEGUI','grantHeld'))
                # The Action controller uses its own already-delegated public grant.
                # Find A's admitted grant through the C context's Request prefix.
                grant=0
                for index in range(8):
                    context=get(sy['contexts']+index*4,4)
                    if context and get(context+layout['Request global']+4)==get(sy['GEMCounters']+4):
                        grant=get(context+layout['Request displayGrant'],4)
                        break
                require(grant!=0,'Missing A display grant')
                reach('dw($%x)=2'%(grant+DISPLAY_ABI['grant_fields']['state']))
                key_before=get(key,1)
                b._cmd_ok('KEY B down')
                reach('db($%x)!=%d'%(key,key_before));b._cmd_ok('KEY B up')
                require(get(at('INPUTDEVICEGUI','grantHeld'))==1,'Display holder escaped the wait case')
                report['cases'].append('key inbox delivery while A sleeps for a display grant')
                b.poke16(at('INPUTDEVICEGUI','grantCommand'),2)
                reach('dw($%x)=0'%at('INPUTDEVICEGUI','grantHeld'))
                b.poke16(sy['CounterPause']+2,0);frames(20)
                b.poke16(at('INPUTDEVICEGUI','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            if timing:b.profile_stop()
            ownership(b,p,p['output'])
            report['native_checks']=get(at('INPUTDEVICEGUI','checks'))
            require(report['native_checks']==19,'Incomplete GUI fixture')
            report['cases'][:0]=['pointer-busy GUI startup rollback and retry','two ordinary GEM Counters']
            if timing:report['timing']=result(out,p,timing,idle)
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        if timing:restore(timing)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS input.device GUI:',report['native_checks'],'checks')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    parser.add_argument('--trace',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    run(out,read_build(args.from_build) if args.from_build else build_fixture(out),args.trace)
