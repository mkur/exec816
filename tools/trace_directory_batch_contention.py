#!/usr/bin/env python3
"""Controlled queued-peer comparison; no production scheduling changes."""
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,read_build
from library_paths import read_source,library_file
from make_data_disk import make
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from bitmap_console_performance import native_markers
from dos_concurrent_trace import packet_marks,packet_observations
from g4bench_trace import native_calls
from sio_transaction_trace import read_events,BASE_HZ

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    for name in ('dirbatchpeer.act','dirbatchcontention.act','directory_batch_contention.act'):
        (out/name).write_bytes((ROOT/'tests/programs'/name).read_bytes())
    source=read_source(library_file('fsdirectory.act')).replace('\nUSE ','\nUSE DIRBATCHCONTENTION\nUSE ',1)
    old='  service.batchOutput=BYTE POINTER(@batch.entries(0))\n  RestoreParent(service)'
    require(source.count(old)==1,'Stale batch admission checkpoint')
    # One admission hook, outside the measured queue interval. Do not add a
    # hook to every bounded worker step and charge that overhead to the batch.
    (out/'fsdirectory.act').write_text(source.replace(old,old+'\n  DIRBATCHCONTENTION.Checkpoint(service)'))
    media=out/'media/DATA';media.mkdir(parents=True,exist_ok=True)
    for i in range(20):(media/f'F{i:02}').write_bytes(bytes([i])*3)
    make(out/'data.atr',out/'media',filesystem='sdfs',sector_bytes=256,sectors=2880)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=4352
    memory=out/'memory.json';memory.write_text(json.dumps(profile)+'\n')
    p=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),out/'directory_batch_contention.act',out,
        tasks=True,task_capacity=8,optimize=True,console_deferred=True,kernel_bank=18,memory_profile=memory,
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,format=2,profile=4)])
    marks=native_markers(p,[(n,n) for n in ('BATCHCONTENTIONTEST_PEEROPERATION','DOSCALLS_EXNEXTBATCH','DOSCALLS_LOCK')])
    packets=packet_marks(p)
    pcs=set(packets.values())
    for m in marks.values():pcs.update([m['entry'],*m['returns']])
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)))
    (out/'definition.json').write_text(json.dumps(dict(marks=marks,packets=packets),indent=2)+'\n')
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=PIN) as b:
        machine=verify_machine(b,rom,PIN)
        b.config('diskemu','generic56k');b.mount(0,str(out/'data.atr'))
        runtime,_=execute(b,p,before_run=lambda b:b.profile_start(),timeout=240,frame_limit=12000)
        b.profile_stop();ownership(b,p,p['output'])
        checks=data(b,p['image'],'checks',True)
    (out/'runtime.json').write_text(json.dumps(dict(runtime=runtime,machine=machine,checks=checks),indent=2)+'\n')
    return analyze(out)

def analyze(out):
    saved=json.loads((out/'definition.json').read_text());marks=saved['marks'];packets=saved['packets']
    events=read_events(out/'emulator.log',kinds={'cpu'})
    spans=native_calls(events,marks)
    failures=[]
    _,operations=packet_observations(events,packets,lambda okay,message:None if okay else failures.append(message))
    require(not failures,str(failures))
    peers=sorted((s for s in spans if s['kind']=='BATCHCONTENTIONTEST_PEEROPERATION'),key=lambda s:s['start'])[1:]
    require(len(peers)==6,'Missing peer operations')
    rows=[]
    for i,peer in enumerate(peers):
        lock=next(s for s in spans if s['kind']=='DOSCALLS_LOCK' and s['dp']==peer['dp'] and peer['start']<=s['start']<s['end']<=peer['end'])
        request=next(s for s in operations if s['dp']==peer['dp'] and lock['start']<=s['submitted']<s['collected']<=lock['end'])
        batch=next(s for s in spans if s['kind']=='DOSCALLS_EXNEXTBATCH' and s['start']<request['submitted']<s['end'])
        require(batch['end']<=lock['end'],'Peer unexpectedly completed before active batch')
        ms=lambda ticks:ticks*1000/BASE_HZ
        rows.append(dict(capacity=8 if i<3 else 16,lock_ms=ms(lock['end']-lock['start']),
            queue_ms=ms(request['dispatched']-request['submitted']),batch_ms=ms(batch['end']-batch['start'])))
    result=dict(status='pass',tier='development',qualification=False,samples=rows,
        **json.loads((out/'runtime.json').read_text()),
        stimulus='Test-only one-time Signal/Yield at active batch admission, before enumeration; peer already owns its DOS context. Queue timing starts at its ordinary PutMsg. No per-entry hooks; production worker unchanged.',
        bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(rows,indent=2),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--reuse-build',action='store_true');a.add_argument('--analyze',action='store_true')
    args=a.parse_args()
    if args.analyze:analyze(args.output.resolve())
    else:run(args.output.resolve(),args.reuse_build)
