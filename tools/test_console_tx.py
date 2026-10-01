#!/usr/bin/env python3
"""TX refill/write turnaround with native display work and a physical key."""
import adapter_state as adapter
import argparse,json,os
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,require,sha256
from os_boundary import emulator,run_to
from test_console_coexistence import PIN,check_alarms
from test_dos_stack import execute,ownership
from sector_images import disk_image
from sio_adapter_trace import analyze
from sio_transaction_trace import read_events,checksum,stats,BASE_HZ
from sio_concurrent_trace import LIMITS

def run(out,optimize,toolchain=None):
    out.mkdir(parents=True,exist_ok=True)
    p=build(toolchain if toolchain is not None else compiler(ROOT/'build/actionc'),ROOT/'tests/programs/native_console_tx.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True)
    marks={k:v for k,v in p['labels'].items() if k in ('native_nmi','native_irq','sio_start','sio_retire','sio_shutdown','sio_terminal','signal_post','sio_alarm','sio_watchdog','console_capture')}
    cases=[];schedule=None
    for observed in (True,False):
        dest=out/('observed' if observed else 'replay');dest.mkdir(exist_ok=True);disk_image(dest/'disk.atr',128);original=(dest/'disk.atr').read_bytes()
        for key in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE','EXEC816_LATENCY_PCS'):os.environ.pop(key,None)
        if observed:os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_MASK_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in marks.values()))
        require(sha256(ROOT/'build/console-bridge/AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned console emulator')
        with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',dest,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.config('diskemu','fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.mount(0,str(dest/'disk.atr'));actions=[];saved={}
            def rendezvous(point,condition):
                b.bp_clear_all();b.bp_set(p['labels'][point],condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                run_to(b,p['labels'][point],6000,120,condition)
            def before(b):
                saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
                b._cmd_ok('KEY ALL up')
                if observed:b.profile_start()
                state=p['build']['task_storage']['BASE']+0x800
                rendezvous('native_irq',f'(db(${state+1:x})=7)&(dw(${state+10:x})>100)')
                require(b._cmd_ok('KEY A down')['raw_scan'],'Not physical input');actions.append(dict(key='A',state='down',frame=b.eval_expr('@frame')))
                frame=actions[0]['frame']+4 if observed else schedule[1]['frame']
                rendezvous('native_nmi',f'@frame>={frame}');b._cmd_ok('KEY A up');actions.append(dict(key='A',state='up',frame=b.eval_expr('@frame')));b.bp_clear_all()
            rt,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            if observed:b.profile_stop()
            require(b.peek(next(d['address'] for d in p['image']['data'] if '_CHECKPOINT_' in d['name']))==b'\1','Missing TX cleanup')
            require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Console not restored')
            require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel reserve touched');ownership(b,p,out)
        expected=bytearray(original);expected[16+3*128:16+4*128]=bytes(i^0xa7 for i in range(128));require((dest/'disk.atr').read_bytes()==expected,'Unexpected media mutation')
        result=dict(status='pass',runtime=rt,machine=machine,schedule=actions,media_before_sha256=__import__('hashlib').sha256(original).hexdigest(),media_after_sha256=sha256(dest/'disk.atr'))
        if observed:
            schedule=actions
            with (dest/'emulator.log').open() as src,(dest/'trace.log').open('w') as dst:
                for line in src:
                    if '[SIOPOC] ' in line or '[SIOTXN] ' in line:dst.write(line)
            timing=analyze(dest/'trace.log',p['labels']);require(timing['verdict']=='pass','TX timing failed: '+str(timing['violations']))
            events=read_events(dest/'trace.log');timing['alarms']=check_alarms(events,p['labels'])
            payload=[i^0xa7 for i in range(128)];frames=[[49,0x50,4,0],[49,0x52,4,0]]
            require(timing['tx_frames']==[frames[0]+[checksum(frames[0])],payload+[checksum(payload)],frames[1]+[checksum(frames[1])]],'TX bytes changed')
            require(timing['rx_bytes']==[0x41,0x41,0x43,0x41,0x43]+payload+[checksum(payload)],'RX acknowledgement/data changed')
            ack=next((t,e) for t,e in events if e[0]=='rxstart');start=next(t for t,e in events if e[0]=='ready' and t>ack[0]);gap=(start-ack[0]-int(ack[1][3])*10)/BASE_HZ*1e6
            require(LIMITS['write_delay_us'][0]<=gap<=LIMITS['write_delay_us'][1],'Write turnaround deadline');timing['write_delay_us']=gap
            timing.pop('tx_frames');timing.pop('rx_bytes');result['timing']=timing
        else:require(actions==schedule,'TX replay schedule changed')
        cases.append(result);(dest/'case.json').write_text(json.dumps(result,indent=2)+'\n')
    return dict(status='pass',build=p['build'],cases=cases,limits=dict(checkpoint_host_seconds=120,completion_host_seconds=240,byte_deadline_us=140/BASE_HZ*1e6,write_delay_us=LIMITS['write_delay_us']))
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(out,args.case=='opt')
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Console TX passed',args.case,flush=True)
