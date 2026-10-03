#!/usr/bin/env python3
"""M3: standalone simultaneous keyboard and real ST/port-1 pointer leases."""
import argparse
import json
import os
import re
import time
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_heap_api import clean_ownership
from test_mouse_observe import PIN, BRIDGE, ROM


def run(out, mode, unobserved=False):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', slice='M3', mode=mode)
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned bridge')
        p = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/pointer_capture.act',
                  out/'program', tasks=True, task_capacity=8, optimize=mode == 'opt', console=False)
        at = lambda name: next(d['address'] for d in p['image']['data']
                              if d['name'].startswith('M_POINTERTEST_'+name.upper()+'_'))
        if unobserved:
            os.environ.pop('EXEC816_MOUSE_TRACE', None)
        else:
            os.environ['EXEC816_MOUSE_TRACE'] = '1'
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROM, PIN)
            def reach(condition):
                b.bp_clear_all()
                b.bp_set(p['labels']['native_nmi'], condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                try:
                    initial=b.eval_expr('@frame')
                    deadline=time.monotonic()+40
                    b.resume()
                    while time.monotonic()<deadline:
                        regs=b.regs()
                        if int(regs['PC'].lstrip('$'),16)==p['labels']['native_nmi'] and b.eval_expr(condition):
                            b.pause()
                            return
                        if b.peek16(adapter.STATE)!=0xffff or b.eval_expr('@frame')-initial>800:
                            break
                        time.sleep(.02)
                    b.pause()
                    raise RuntimeError('No pointer checkpoint')
                except Exception:
                    raise RuntimeError(f'Pointer check {b.peek16(at("checks"))}, status {b.peek16(adapter.STATE):x}, event={b.memdump(at("event"),24).hex()}, capture={b.memdump(0x3f4810,152).hex()}')
            saved, commands = {}, []
            def hardware():
                values = {name:b.memdump(address,n).hex() for name,address,n in
                        [('mask',16,1), ('skctl',0x232,1), ('timer_vector',0x210,2),
                         ('key_vector',0x208,2), ('break_vector',0x236,2)]}
                values.update(pia=b.pia(),gractl=b.gtia()['GRACTL'])
                return values
            def before(bridge):
                saved.update(hardware())
                b._cmd_ok('MOUSE ST')
                reach(f'db(${at("stage"):x})=1')
                movements = [(16,0)]*8+[(-16,0)]*8+[(0,16)]*8+[(0,-16)]*8
                for i,(dx,dy) in enumerate(movements):
                    command = f'MOUSE AT {2000+i*36000} {dx} {dy} -1'
                    commands.append(dict(command=command, **b._cmd_ok(command)))
                for delay,state in ((1180000,1),(1200000,0)):
                    command = f'MOUSE AT {delay} 0 0 {state}'
                    commands.append(dict(command=command, **b._cmd_ok(command)))
                reach(f'@frame>={b.eval_expr("@frame")+40}')
                b.memload(at('stop'), b'\1')
                b._cmd_ok('KEY A down')
                b.bp_clear_all()
            runtime, _ = execute(b,p,before_run=before, frame_limit=2000,timeout=100)
            b._cmd_ok('KEY ALL up')
            raw = b.memdump(at('events'),b.peek16(at('received'))*24)
            events = [dict(acquisition=int.from_bytes(r[:4],'little'),route=int.from_bytes(r[4:8],'little'),
                           tick=int.from_bytes(r[8:10],'little'),kind=r[10],flags=r[11],
                           code=int.from_bytes(r[12:14],'little'),x=int.from_bytes(r[16:18],'little',signed=True),
                           y=int.from_bytes(r[18:20],'little',signed=True),buttons=int.from_bytes(r[20:22],'little'))
                      for r in (raw[i:i+24] for i in range(0,len(raw),24))]
            expected = [(2,100,100,0)]
            x=y=100
            for dx,dy in [(1,0)]*8+[(-1,0)]*8+[(0,1)]*8+[(0,-1)]*8:
                x+=dx; y+=dy; expected.append((2,x,y,0))
            expected += [(3,100,100,1),(3,100,100,0)]
            require([(e['kind'],e['x'],e['y'],e['buttons']) for e in events] == expected,
                    'Wrong physical pointer records: '+str(events))
            require(all(e['acquisition']==3 and e['route'] and e['flags']==1 and e['code']==(1 if e['kind']==3 else 0) for e in events),
                    'Pointer identity/timestamp flags changed')
            require(hardware()==saved, 'Hardware ownership not restored')
            storage=p['build']['memory']['input_storage']
            guard=storage['POINTER_GUARD_BYTES']
            require(b.memdump(storage['POINTER_RESERVE'],guard)==bytes([0xa5])*guard and
                    b.memdump(storage['POINTER_CAPTURE']+storage['POINTER_CAPTURE_BYTES'],guard)==bytes([0xa5])*guard,
                    'Pointer capture guards changed')
            clean_ownership(b,p,p['output'])
            report.update(runtime=runtime,checks=b.peek16(at('checks')),events=events,commands=commands,
                          hardware_before=saved,hardware_after=hardware(),
                          stack_usage=stack_usage(b,p['build']['memory']))
        trace=[list(map(int,m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)',(out/'emulator.log').read_text())]
        if not unobserved:
            require(len(trace)==34, 'Controller observer missed a transition')
        report.update(status='pass',build=p['build'],pin=PIN,xex_sha256=sha256(p['xex']),
                      observer=not unobserved,controller_trace=trace,
                      bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Standalone ST capture passed:',mode,flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--unobserved',action='store_true')
    args=parser.parse_args()
    run(args.output,args.mode,args.unobserved)
