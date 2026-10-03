#!/usr/bin/env python3
"""Real VBXE IRQ delivery and retained producer lifetime through emitted code."""
import argparse
import json
import os
from pathlib import Path
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256, read_build
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage


def run(out, mode, replay=False, timer=False, lost=False, wrap=False, observe=False, before_wait=False):
    require(not observe or not (timer or lost or wrap),'Timing requires uninterrupted completion')
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/blitter_irq.act',
            out/'program',tasks=True,task_capacity=8,console=False,optimize=mode=='opt')
    report=dict(status='running',tier='development',mode=mode,timer_irq=timer,lost_irq=lost,tick_wrap=wrap,before_wait=before_wait,build=p['build'])
    marks={name:p['labels'][name] for name in ('blitter_launched','blitter_irq_complete',
        'native_irq','interrupt_schedule','blitter_watchdog','blitter_watchdog_done')}
    if observe:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in marks.values())
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            report['machine']=verify_machine(b,ROM,PIN)
            saved={}
            def before(b):
                if observe:b.profile_start()
                saved['irq']=b.memdump(0x216,2)
                saved['timer']=b.memdump(0x210,2)
                shadow_address=next(d['address'] for d in p['image']['data'] if '_SHADOWADDRESS_' in d['name'])
                b.memload(shadow_address,(p['build']['task_storage']['BLITTER_STATE']+28).to_bytes(4,'little'))
                mode_address=next(d['address'] for d in p['image']['data'] if '_FAULTMODE_' in d['name'])
                b.memload(mode_address,bytes([int(lost)|int(wrap)*2|int(timer)*4|int(before_wait)*8]))
            runtime,_=execute(b,p,before_run=before,timeout=90,frame_limit=4000,timer_irq=timer)
            require(b.memdump(0x216,2)==saved['irq'],'IRQ vector not restored')
            require(b.memdump(0x210,2)==saved['timer'],'Timer vector not restored')
            require(b.peek(0xd654)==b'\0','VBXE IRQ left asserted')
            at=p['build']['task_storage']['BLITTER_STATE']
            emulations=b.peek16(at+30)
            require(emulations==(0 if timer else 1),'Unexpected emulation IRQ completions')
            clean_ownership(b,p,p['output'])
            require(data(b,p['image'],'checks',True)==[5 if timer else 19 if before_wait else 17],'Incomplete IRQ fixture')
            if observe:b.profile_stop()
            elapsed=data(b,p['image'],'elapsed',True)[0]
            if lost: require(elapsed>=15 and elapsed<20,'Watchdog wake outside sixteen-tick bound')
            require(b.peek(at+15)==b'\0','Mailbox not reset')
            require(b.peek(p['build']['task_storage']['BASE']+0xf30)==b'\0','Timer owner leaked')
            report.update(elapsed_ticks=elapsed,status='pass',emulation_completions=emulations,checks=data(b,p['image'],'checks',True),
                          runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']))
        if observe:
            from sio_transaction_trace import read_events, BASE_HZ
            events=[(t,int(e[4],16)) for t,e in read_events(out/'emulator.log') if e[0]=='cpu']
            launch=next(t for t,pc in events if pc==marks['blitter_launched'])
            finish=next(t for t,pc in events if t>launch and pc==marks['blitter_irq_complete'])
            active={}; totals={key:0 for key in ('irq','watchdog')}; counts=dict(totals)
            for t,pc in events:
                if not launch<=t<=finish:continue
                for name,entry,end in [('irq','native_irq','interrupt_schedule'),
                        ('watchdog','blitter_watchdog','blitter_watchdog_done')]:
                    if pc==marks[entry]:active[name]=t
                    if pc==marks[end] and name in active:
                        totals[name]+=t-active.pop(name);counts[name]+=1
            report['timing']=dict(scope='First native hardware list; IRQ body through interrupt_schedule, watchdog nested in IRQ. Exact BUSY edge unmeasured.',
                launch_to_irq_upper_ms=(finish-launch)/BASE_HZ*1000,
                body_ms={key:value/BASE_HZ*1000 for key,value in totals.items()},counts=counts)
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/('results-before-wait.json' if before_wait else 'results-observed.json' if observe else 'results-lost-wrap.json' if wrap else 'results-lost.json' if lost else 'results-timer.json' if timer else 'results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('Blitter IRQ passed',mode,report['checks'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    parser.add_argument('--replay',action='store_true')
    parser.add_argument('--timer',action='store_true')
    parser.add_argument('--lost',action='store_true')
    parser.add_argument('--wrap',action='store_true')
    parser.add_argument('--observe',action='store_true')
    parser.add_argument('--before-wait',action='store_true')
    args=parser.parse_args();run(args.output,args.mode,args.replay,args.timer,args.lost,args.wrap,args.observe,args.before_wait)
