#!/usr/bin/env python3
"""Qualify simultaneously resident signal Tasks with checked bank-zero pools."""
import adapter_state as adapter
import argparse
import json
import os
import struct
from pathlib import Path
from native_program import ROOT,build,compiler,execute,platform_files,require,sha256,verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import data
from banked_test_memory import read


def marker_addresses(program):
    markers={n:program['labels'][n] for n in ('signal_post','signal_post_return')}
    returns={}
    for name in ('DRAINONE','DRAINWAKES'):
        routine=next(r for r in program['image']['routines'] if r['name'].startswith('M_TASKPOLICY_'+name+'_'))
        markers[name]=routine['address']
        segment=next(s for s in program['image']['segments'] if s['address']<=routine['address']<s['address']+len(s['bytes']))
        offset=routine['address']-segment['address']
        returns[name]={routine['address']+i for i,b in enumerate(segment['bytes'][offset:offset+routine['size']]) if b==0x6b}
    return markers,returns


def measure(log,markers,returns):
    from test_signals_irq import events
    from test_signal_stream import stats
    active={};durations={name:[] for name in ('posting','DRAINONE','DRAINWAKES','nonempty')}
    for tick,event in events(log):
        if event[0]!='cpu':continue
        require(int(event[3])==8,'Wrong observed CPU multiplier')
        pc=int(event[4],16)
        if pc==markers['signal_post']:active['posting']=tick
        if pc==markers['signal_post_return'] and 'posting' in active:
            durations['posting'].append(tick-active.pop('posting'))
        for name in returns:
            if pc==markers[name]:
                require(name not in active,'Recursive kernel drain')
                active[name]=tick
            if pc in returns[name] and name in active:
                cost=tick-active.pop(name)+6/8
                durations[name].append(cost)
                if name=='DRAINONE' and int(event[5],16)==1:durations['nonempty'].append(cost)
    require(durations['posting'] and durations['nonempty'],'Missing measured post/drain')
    return {k:stats(v) if v else None for k,v in durations.items()}


def check_case(bridge,program,result,args):
    checks=data(bridge,program['image'],'checks',True);n=args.capacity
    if args.burst:
        require(checks==[n-1,1,n-1,1,n-1,0,0,0],'Full-capacity burst: '+str(checks))
        raw=bytes(data(bridge,program['image'],'values'))
        masks=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
        require(masks[:n]==[1]*n and masks[n:]==[0]*(16-n),'Burst Wait results: '+str(masks))
        c=program['build']['task_storage']
        queued=list(read(bridge,c['SERIAL_STATE']+5,n,program['output']))
        require(queued==[1]*n,'Queue never reached capacity: '+str(queued))
        require(result['created']==n-1 and result['idle_runs']>=2,'Missing burst admission/idle path')
        if args.burst==3:
            require(bridge.peek16(adapter.PROBE0)==2 and result['native_irq_count']>=2,'Protected IRQ window failed')
            require(int.from_bytes(bytes(result['root_task'][24:28]),'little')==2,'Window signal lost/consumed')
        observed=dict(checks=checks,masks=masks,queued=queued)
    else:
        require(checks==[n-1,n-1,1,1,1,1,1,n-1,1,1,1,n-1]+[0]*4,'Capacity checks: '+str(checks))
        raw=bytes(data(bridge,program['image'],'results'))
        masks=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
        require(masks[1:n]==[1]*(n-1),'Delivered/reused masks: '+str(masks))
        progress=data(bridge,program['image'],'progress',True)
        require(progress[1:n]==[1]*(n-1),'Worker buffer corruption: '+str(progress))
        require(result['created']==n and result['native_irq_count']>0,'Missing simultaneous/reuse/IRQ coverage')
        observed=dict(checks=checks,masks=masks,progress=progress)
    c=program['build']['memory']['constants'];bank=c['KERNEL_BANK']
    if c['TABLE']>=65536:
        table=read(bridge,c['TABLE'],c['TABLE_BYTES'],program['output'])
        require(c['TABLE']==bank<<16 and table[bank*4]==2,'Upper kernel table not adopted')
        memory=program['build']['memory'];arena=memory['image_data']
        require(memory['profile']['code_origin']==arena['address']+arena['size'] and
                arena['address']>>16==bank,'Kernel-bank placement mismatch')
        observed['bank_table']=list(table)
    contexts=[]
    if args.flags!=0x100:
        for slot,pool in enumerate(program['build']['memory']['task_pools'][:n]):
            raw=bridge.memdump(adapter.probe_address(slot),24);f=args.flags
            expected=struct.pack('<BHHHHBHHHHH',0x12,pool['dp'],0x78 if f&0x10 else 0x5678,0x34 if f&0x10 else 0x1234,0xab01,f,pool['stack_base']+pool.get('stack_bytes',1536)-8,0xbeef,0xff10,0xff11,0xff10)
            require(raw[:20]==expected,'Capacity register restoration: '+str(slot)+' '+raw.hex())
            contexts.append(raw.hex())
    observed['contexts']=contexts
    return observed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,required=True)
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/capacity')
    p.add_argument('--mode',choices=('raw','opt'))
    p.add_argument('--kernel-bank',type=int,action='append')
    p.add_argument('--capacity',type=int,default=8)
    p.add_argument('--worker-stack',type=int)
    p.add_argument('--idle-stack',type=int)
    p.add_argument('--flags',type=lambda x:int(x,0),default=0x100)
    p.add_argument('--burst',type=int,choices=(2,3))
    p.add_argument('--observe',action='store_true',help='Measure post/drain costs with the passive 24-bit observer on the 8x profile')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    require(args.flags==0x100 or args.capacity<=8 and not args.burst,'Register capture supports at most eight tasks, without burst probe')
    toolchain=compiler(args.compiler_dir)
    pin=PIN;observer=None
    if args.observe:
        from test_signals_irq import PIN as fast_pin
        pin=fast_pin
        observer=json.loads((ROOT/'toolchain/altirra-signals-observer.json').read_text())
        require(sha256(args.bridge_dir/'AltirraBridgeServer')==observer['binary_sha256'],'Incorrect observer binary')
        require(sha256(args.rom)==pin['rom']['sha256'],'Incorrect ROM')
    else:platform_files(args.bridge_dir,args.rom)
    report=dict(schema_version=1,status='running',scope='Simultaneous Task capacity and full wake queue',platform=pin,observer=observer,cases=[])
    env={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    try:
        for bank in args.kernel_bank or (1,3):
            for mode in (args.mode,) if args.mode else ('raw','opt'):
                name=f'{args.capacity}-bank{bank}-{mode}-{args.flags:x}'+(f'-burst{args.burst}' if args.burst else '')
                print('Running '+name+'...',flush=True)
                program=build(toolchain,ROOT/('tests/programs/signals_capacity_burst.act' if args.burst else 'tests/programs/signals_capacity.act'),out/name,
                    tasks=True,optimize=mode=='opt',kernel_bank=bank,task_capacity=args.capacity,
                    worker_stack=args.worker_stack,idle_stack=args.idle_stack,probe_flags=args.flags,irq_probe=args.burst or 0,
                    image_data=[(0x5ffe0,bytes([0xa5])*4096),(0x68000,bytes(4096)),(0x6a000,bytes(96))])
                markers,returns=marker_addresses(program)
                if args.observe:
                    os.environ['EXEC816_LATENCY_TRACE']='1'
                    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{v:x}' for v in sorted(set(markers.values())|set.union(*returns.values())))
                with emulator(args.bridge_dir.resolve(),args.rom.resolve(),out/name,pin=pin) as bridge:
                    machine=verify_machine(bridge,args.rom,pin)
                    borrowed = {}
                    extra = max(0,args.capacity*32-128) if args.flags!=0x100 else 0
                    def before_run(b):
                        if extra:
                            require(extra <= adapter.TEST_REGISTER_EXTENSION_BYTES,'Register scratch too small')
                            borrowed['bytes'] = b.memdump(adapter.TEST_REGISTER_EXTENSION,extra)
                        if args.observe:
                            b.profile_start()
                    result,_=execute(bridge,program,frame_limit=6000,timeout=480,load_timeout=180,
                        before_run=before_run)
                    try:
                        observed=check_case(bridge,program,result,args)
                    finally:
                        if extra:
                            bridge.memload(adapter.TEST_REGISTER_EXTENSION,borrowed['bytes'])
                    if extra:
                        require(bridge.memdump(adapter.TEST_REGISTER_EXTENSION,extra) == borrowed['bytes'],
                                'Register scratch not restored')
                        observed['scratch']=dict(address=adapter.TEST_REGISTER_EXTENSION,size=extra,restored=True)
                case=dict(name=name,status='pass',build=program['build'],runtime=result,machine=machine,observed=observed,
                    diagnostic_bank_zero_delta=extra)
                if args.observe:
                    case['timing']=measure(out/name/'emulator.log',markers,returns)
                    case['trace_sha256']=sha256(out/name/'emulator.log')
                report['cases'].append(case)
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        for k,v in env.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed '+str(len(report['cases']))+' simultaneous-capacity cases')


if __name__=='__main__':main()
