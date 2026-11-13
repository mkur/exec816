#!/usr/bin/env python3
"""Run the real Terminal scenario with timer-free native directory observers."""
import argparse,json,os
from unittest.mock import patch
from pathlib import Path
from native_program import require,read_build,sha256
from shell_inspect import address
from test_gem_terminal import _run


def run(directory,out,observe=False):
    snapshots={};quiet={};definition={}
    if observe:
        from bitmap_console_performance import native_markers
        p=read_build(directory/'program')
        names=['SHELLAPP_SHELLSESSIONQUERYREPLY','CONSOLEVIEW_DIRECTORY']
        definition=native_markers(p,[(n,n) for n in names])
        require(set(definition)==set(names),'Missing idle observer sites')
        provider=json.loads((directory/'c-image.json').read_text())
        timer=provider['symbols']['ExecAESTimerSend']
        from text_performance_trace import sites
        folder=directory/'apps/terminal';app=json.loads((folder/'app.json').read_text())
        calls={pc:s for pc,s in sites(folder,app['image'],{'ExecAESWait':'wait'}).items() if s['category']=='wait'}
        require(calls,'Missing actual Terminal wait sites')
        pcs=[v['entry'] for v in definition.values()]+[timer,p['labels']['native_nmi'],p['labels']['native_irq'],p['labels']['idle_start']]
        pcs += [bank*65536+(pc&65535) for pc,s in calls.items() for pc in (pc,s['end'])
            for bank in p['build']['memory']['usable_banks']]
    def checkpoint(label,b,p,report):
        base=address(p['image'],'directoryCounts')
        counts=[int.from_bytes(b.memdump(base+i*4,4),'little') for i in range(2)]
        require(counts[0]==counts[1],'Observers disagree at '+label)
        snapshots[label]=counts
        if label.startswith('quiet-'):quiet[label]=b.eval_expr('@clk')
        if label in ('quiet-end','output'):
            require(counts==snapshots['quiet-start'],'Read/output manufactured a directory hint')
        if label=='created':require(counts[0]>snapshots['output'][0],'Missing creation/READY hint')
        if label=='selected-first':require(counts[0]>snapshots['created'][0],'Missing silent selection hint')
        if label=='selected-second':require(counts[0]>snapshots['selected-first'][0],'Missing second selection hint')
        if label=='fallback':require(counts[0]>snapshots['selected-second'][0],'Missing retirement/fallback hint')
        report['directory_observers']=snapshots
    if observe:
        def begin(b,p,terminal,report):
            t=p['build']['task_storage']
            number=lambda at,size:int.from_bytes(b.memdump(at,size),'little')
            slot=next(i for i in range(len(p['build']['memory']['task_pools']))
                if number(t['BASE']+i*t['SIZE']+t['TCB_ITEM'],3)==terminal['task'])
            report['idle_observer']=dict(dp=p['build']['memory']['task_pools'][slot]['dp'],
                delta=terminal['base']-(app['abi']['link_bank']<<16))
            b.profile_start()
        with patch.dict(os.environ,EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in pcs)):
            report=_run(directory,out,observer=begin,checkpoint=checkpoint)
        from measure_gui_baseline import save_cpu_trace
        from sio_transaction_trace import read_events,BASE_HZ
        from text_performance_trace import extend_clock
        save_cpu_trace(out)
        events=read_events(out/'cpu-trace.log',kinds={'cpu'})
        start=extend_clock(quiet['quiet-start'],events[0][0]);end=extend_clock(quiet['quiet-end'],start)
        # Root handles only this one quiet Terminal's QUERY in this interval.
        counts={name:sum(start<=t<end and int(e[4],16)==mark['entry'] for t,e in events)
            for name,mark in definition.items()}
        dp=report['idle_observer']['dp'];delta=report['idle_observer']['delta']
        counts['Terminal_timer_arms']=sum(start<=t<end and int(e[4],16)==timer and int(e[9],16)==dp for t,e in events)
        require(not any(counts.values()),'Healthy idle polling: '+str(counts))
        from g4bench_trace import native_calls
        waits=[s for s in native_calls(events,{str(pc):dict(entry=pc+delta,returns=[site['end']+delta]) for pc,site in calls.items()}) if s['dp']==dp]
        report['idle_observer'].update(waits=len(waits),view_wakes=sum(bool(s['return_a']&0x8000) for s in waits),
            timer_wakes=sum(bool(s['return_a']&0x20) for s in waits))
        require(report['idle_observer']['view_wakes']>0,'Missing genuine output wakes')
        report['quiet_interval']=dict(milliseconds=(end-start)*1000/BASE_HZ,counts=counts,
            trace_sha256=sha256(out/'cpu-trace.log'))
    else:report=_run(directory,out,checkpoint=checkpoint)
    # Native completion checks require both watches to withdraw after quiescence.
    report['directory_observer_scope']='Two Task-owned watches, no timer; source creation/retirement/epoch reuse and activation while UPDATE held; stable reads/output; real shell creation/READY/select/fallback and shutdown.'
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def probe_only(directory,out):
    """The focused UPDATE owner/peer case ends through normal controller stop."""
    from os_boundary import emulator
    from test_mouse_observe import BRIDGE,ROM,PIN
    from native_program import verify_machine
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    p=read_build(directory/'program');out.mkdir(parents=True,exist_ok=True)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROM,PIN);b.mount(0,str(directory/'system.atr'))
        runtime,_=execute(b,{**p,'output':out},timeout=180,frame_limit=12000)
        ownership(b,p,p['output'])
        checks=data(b,p['image'],'directoryChecks',True)[0]
        done=data(b,p['image'],'directoryDone')[0]
        require(checks>=40 and done==2,'Incomplete UPDATE consumer cases')
    record=dict(status='pass',tier='development',qualification=False,checks=checks,peer_observers_retired=done,
        runtime=runtime,machine=machine,build=p['build'],scope=probe_only.__doc__,observer_sha256=sha256(Path(__file__)))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('UPDATE consumer checks passed',checks,done,flush=True)
    return record


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--observe',action='store_true');a.add_argument('--probe-only',action='store_true')
    args=a.parse_args()
    if args.probe_only:
        require(not args.observe,'The focused UPDATE case uses native completion checks')
        probe_only(args.build.resolve(),args.output.resolve())
    else:run(args.build.resolve(),args.output.resolve(),args.observe)
