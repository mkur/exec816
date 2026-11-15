#!/usr/bin/env python3
"""Small direct and loaded-provider semaphore consumers; no demo refresh."""
import argparse
import json
import os
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT, build, compiler, execute, read_build, require, verify_machine
from os_boundary import emulator
from stack_budget import stack_usage
from test_heap_api import clean_ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out, mode='opt', reuse=False, measured=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        foreign=json.loads((out/'c-image.json').read_text())
        program=read_build(out/'program')
    else:
        foreign=emit(out,[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/semaphores.c'],
                     [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],
                     ['Counter'],optimize=mode=='opt',roots=['ComposedPair','NativePair'])
        (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
        source=out/'launcher.act'
        source.write_text(f'''MODULE CSEMAPHORES
USE EXEC
USE HEAPCORE
CARD FUNC POINTER entry()
PROC Main()

  LET cell=ADDRESS POINTER(@entry)
  cell^=ADDRESS(${foreign['symbols']['main']:x})
  IF entry()<>0 THEN
    HEAPCORE.Abort($ff90)
  FI

RETURN
ENDMODULE
''')
        program=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',
                      tasks=True,optimize=mode=='opt',foreign_image=foreign,
                      image_data=[(0x04fff0,bytes([0xa5])*32)])
    report=dict(status='running',tier='development',qualification=False,mode=mode,
                build=program['build'],foreign=foreign['provenance'],pin=PIN)
    from generate_semaphores import ABI as semaphore_abi
    from g4bench_trace import listing_returns, calls
    from sio_transaction_trace import read_events
    names=('InitSemaphore','ObtainSemaphore','AttemptSemaphore','ReleaseSemaphore')
    entries={foreign['symbols'][n]:n for n in names}
    returns=listing_returns(foreign,out)
    points=set(entries)|set(returns)|{program['labels']['fast_entry']}
    saved_env={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{p:x}' for p in points))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            def before(b):
                b.poke(foreign['symbols']['variant'],int(measured))
                b.profile_start()
            report['runtime'],_=execute(b,program,before_run=before,timeout=120,frame_limit=2400)
            for name,expected in [('failures',0),('counter',1),('completed',1),('checks',12)]:
                actual=b.eval_expr(f'dw(${foreign["symbols"][name]:x})')
                require(actual==expected,'C '+name+': '+str(actual))
                report[name]=actual
            from banked_test_memory import read
            guard=read(b,0x04fff0,32,out)
            require(guard[:10]==bytes([0xa5])*10 and guard[22:]==bytes([0xa5])*10,'C far object guard')
            report['stack_usage']=stack_usage(b,program['build']['memory'])
            clean_ownership(b,program,program['output'])
        events=read_events(out/'emulator.log',kinds={'cpu'})
        observed=[]
        for pool in program['build']['memory']['task_pools']:
            spans,unfinished=calls(events,entries,set(returns),pool['dp'])
            require(not unfinished,'Unfinished C semaphore wrapper')
            lo,hi=pool['stack_base'],pool['stack_base']+pool['stack_bytes']
            for span in spans:
                requests=sum(int(e[4],16)==program['labels']['fast_entry'] and
                    lo<=int(e[6],16)<hi and int(e[7],16) in semaphore_abi['services'].values()
                    for t,e in events if span['start']<=t<=span['end'])
                require(requests==int(span['kind']!='InitSemaphore'),'C request count '+str(span))
                observed.append(dict(span,requests=requests))
        require(set(s['kind'] for s in observed)==set(names),'Missing C binding observation')
        require(foreign['symbols']['device']%2==0,'C semaphore storage alignment')
        report['public_calls']=observed
        report['status']='pass'
    finally:
        for key,value in saved_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed C semaphore',mode)
    return report


def loaded(out,reuse=False):
    from test_c_runtime import fixture
    from test_c_process import run as process
    pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
    return process(out,True,reuse=reuse,app_sources=[ROOT/'tests/programs/semaphores.c'],
        app_options=dict(definitions={'semaphores.c':['-DSEMAPHORE_APP']},minimum_stack=1536),
        fixture_source=fixture(out,'abi'),expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=False,
        execution=dict(binary=ROOT/'build/shell-paced-bridge',pin=pin))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--loaded',action='store_true')
    p.add_argument('--measured',action='store_true')
    a=p.parse_args()
    if a.loaded:loaded(a.output.resolve(),a.from_build)
    else:run(a.output.resolve(),a.mode,a.from_build,a.measured)
