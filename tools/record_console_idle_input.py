#!/usr/bin/env python3
"""Collect console idle-input development evidence and timing comparisons."""
import argparse,json,re
from pathlib import Path
from native_program import ROOT,require,sha256


def baseline(out,host_log):
    host=host_log.read_text()
    count=re.search(r"Ran (\d+) tests",host)
    require(count and "OK (skipped=4)" in host and "FAILED" not in host,"Incomplete host checks")
    paths=[out/p for p in ('scroll-opt/results.json','scroll-opt/results-replay.json',
        'signals-opt/results.json','signals-opt/replay-results.json','signals-raw/results.json')]
    runs=[json.loads(p.read_text()) for p in paths]
    require(all(r['status']=='pass' for r in runs),'Incomplete Q0 checks')
    scroll,control,signals,signals_control,raw=runs
    for measured,replay in ((scroll,control),(signals,signals_control)):
        require(measured['observed'] and not replay['observed'],'Missing passive/control separation')
        require(measured['build']['xex_sha256']==replay['build']['xex_sha256'],'Replay image changed')
        require(measured['checks']==replay['checks'],'Replay checks changed')
    require(scroll['observations']==control['observations'],'Replay pixels changed')
    require(len(scroll['observations'])==13,'Missing console scenes')
    require(all(not v['routines'] for v in scroll['performance']['idle_input']),'Settled console polls input')
    require(signals['checks']==raw['checks']==[28],'Missing signal acknowledgement checks')
    stages=[s for s in scroll['performance']['stages'] if s['stage'] in (2,3)]
    require(len(stages)==2,'Missing scroll measurements')
    for stage in stages:
        timing=stage['scroll_input'][0]
        require(timing['routines']['input_pending']['calls']==16,'Wrong input-query count')
        require(51<timing['input_check_ms']<53,'Baseline input time changed')
    names=['tools/bitmap_console_performance.py','tools/test_console_bitmap_scroll.py',
        'tools/test_console_input_signals.py','tools/record_console_idle_input.py',
        'tests/programs/console_input_signals.act','lib/console/consoledriver.act',
        'lib/console/consoleinput.act','lib/console/console-requests.inc','lib/input/input.act']
    return dict(slice='Q0',status='development-pass',scope='Unchanged optimized scroll image; 13 exact-pixel scenes and idle intervals, atomic input/stop collection in raw/optimized emitted code. No production behavior change.',
        reports={str(p.relative_to(ROOT)):sha256(p) for p in paths},
        source_inputs={p:sha256(ROOT/p) for p in names},pin=scroll['pin'],machine=scroll['machine'],
        compiler={k:scroll['build'][k] for k in ('revision','binary_sha256','abi_sha256','override')},
        xex_sha256={str(p.parent.relative_to(out)):r['build']['xex_sha256'] for p,r in zip(paths,runs)},
        scrolls=stages,idle_intervals=scroll['performance']['idle_input'],
        signal_collection={r['mode']:dict(timing=r['timing'],checks=r['checks'],runtime=r['runtime']) for r in (signals,raw)},
        baseline_runtime=scroll['runtime'],host_checks=dict(tests=int(count[1]),skipped_historical=4,status='pass',log_sha256=sha256(host_log)),
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        limits=['Elapsed spans include preemption, not isolated CPU time. Nested routine totals must not be added.',
                'Signal-only empty-call timing predicts neither full console latency nor loaded fairness.',
                'No release or physical-hardware qualification.'])


def pump(out,host_log):
    cases=[];paths=[]
    for mode in ('raw','opt'):
        path=out/f'pump-{mode}/results.json';paths.append(path)
        r=json.loads(path.read_text())
        require(r['status']=='pass' and len(r['cases'])==2,'Incomplete pump checks')
        normal,fault=r['cases']
        require(normal['counts']==[0,7,63,64,0,64,2,0,8,8],'Missing pump boundaries')
        require(normal['runtime']['status']==0 and fault['runtime']['status']==4,'Wrong terminal status')
        base=json.loads((ROOT/'build/console-idle-input/q0/signals-opt/program/build.json').read_text())['memory']
        for name in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(r['build']['memory'][name]==base[name],'Changed reserved memory '+name)
        cases.append(dict(mode=mode,xex_sha256=r['build']['xex_sha256'],
            compiler={k:r['build'][k] for k in ('revision','binary_sha256','abi_sha256','override')},
            cases=[dict(variant=c['variant'],checks=c['checks'],counts=c['counts'],
                runtime={k:v for k,v in c['runtime'].items() if k not in ('task_records','ready_queue')}) for c in r['cases']]))
    names=['lib/console/consoleinput.act','tests/programs/console_input_pump.act','tools/test_console_input_pump.py']
    host=host_log.read_text();count=re.search(r'Ran (\d+) tests',host)
    require(count and 'OK (skipped=4)' in host and 'FAILED' not in host,'Incomplete host checks')
    return dict(slice='Q1',status='development-pass',scope='Raw/optimized emitted bounded drains, route filtering, loss recovery, cancellation mailbox and invalid retained-lease terminal failure; synthetic records with route zero, not a physical input-latency measurement.',
        reports={str(p.relative_to(ROOT)):sha256(p) for p in paths},pin=r['pin'],machine=normal['machine'],
        source_inputs={p:sha256(ROOT/p) for p in names},cases=cases,
        host_checks=dict(tests=int(count[1]),skipped_historical=4,status='pass',log_sha256=sha256(host_log)),
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        limits=['Ownership cleanup checked on normal completion; fault case checks terminal status and context/stack guards.',
                'No notification-loop or release qualification claim.'])


def runtime_summary(runtime):
    return {k:v for k,v in runtime.items() if k not in ('task_records','ready_queue')}


def worker(out,host_log):
    paths=[out/f'wake-{backend}-{mode}/results.json' for backend in ('text','bitmap') for mode in ('raw','opt')]
    paths += [out/'focus-opt/results.json',out/'scroll-opt/results.json']
    runs=[json.loads(p.read_text()) for p in paths]
    require(all(r['status']=='pass' for r in runs),'Incomplete worker checks')
    focus,scroll=runs[-2:]
    require(focus['quota_drains']>0 and len(focus['observations'])==8,'Missing physical route/quota checks')
    require(len(scroll['observations'])==13,'Missing scroll scenes')
    require(all(not v['routines'] for v in scroll['performance']['idle_input']),'Settled worker polls input')
    for stage in scroll['performance']['stages']:
        if stage['stage'] not in (2,3):continue
        timing=stage['scroll_input'][0]['routines']
        require(not any(n in timing for n in ('input_pending','public_pending','pump','input_take','input_extent')),'Quiet scroll still validates input')
        require(timing['input_collect']['calls']==timing['signal_collect']['calls']==timing['input_service']['calls']==16,'Wrong per-turn collection count')
    base=json.loads((ROOT/'build/console-idle-input/q0/scroll-opt/program/build.json').read_text())['memory']
    for run in runs:
        for name in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(run['build']['memory'][name]==base[name],'Changed reserved memory '+name)
    host=host_log.read_text();count=re.search(r'Ran (\d+) tests',host)
    require(count and 'OK (skipped=4)' in host and 'FAILED' not in host,'Incomplete host checks')
    names=['lib/console/consoledriver.act','lib/console/console-requests.inc','lib/console/consoleinput.act','lib/console/consolecapture.act',
        'tests/programs/console_input_wake.act','tests/programs/inputwakeprobe.act','tools/test_console_input_wake.py',
        'tools/test_console_focus.py','tools/bitmap_console_performance.py']
    return dict(slice='Q2',status='development-pass',scope='Raw/optimized text and bitmap workers; controlled publication through public Signal at six boundaries, coalesced/full/exact batches, durable notices, restart, and physical focus/BREAK/route retirement. No direct Task signal writes.',
        reports={str(p.relative_to(ROOT)):sha256(p) for p in paths},source_inputs={p:sha256(ROOT/p) for p in names},
        cases=[dict(name=str(p.parent.relative_to(out)),xex_sha256=r['build']['xex_sha256'],
            compiler={k:r['build'][k] for k in ('revision','binary_sha256','abi_sha256','override')},
            checks=r['checks'],runtime=runtime_summary(r['runtime'])) for p,r in zip(paths,runs)],
        pin=scroll['pin'],machine=scroll['machine'],physical_focus=dict(pin=focus['pin'],machine=focus['machine'],quota_drains=focus['quota_drains'],events=focus['events']),
        scrolls=[s for s in scroll['performance']['stages'] if s['stage'] in (2,3)],idle_intervals=scroll['performance']['idle_input'],
        host_checks=dict(tests=int(count[1]),skipped_historical=4,status='pass',log_sha256=sha256(host_log)),
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        limits=['Synthetic publication interleavings establish correctness, not input-to-visible latency.',
                'Loaded SIO/pointer timing and the unobserved scroll replay follow in Q3. No release qualification.'])


def integration(out,host_log):
    from native_program import read_build
    baseline=json.loads((ROOT/'docs/development/console-idle-input-q0.json').read_text())
    q2=json.loads((ROOT/'docs/development/console-idle-input-q2.json').read_text())
    for name,digest in q2['source_inputs'].items():
        if name.startswith('lib/'):
            require(sha256(ROOT/name)==digest,'Production source changed after Q2: '+name)
    paths=[out/p for p in ('scroll-opt/results.json','scroll-opt/results-replay.json',
        'fairness-opt/results.json','fairness-replay/replay-results.json','cancel-opt/results.json',
        'shell-break-opt/results.json','input-opt/results-mode0.json','input-opt/results-mode2.json','input-opt/results-mode4.json')]
    runs=[json.loads(p.read_text()) for p in paths]
    require(all(r['status']=='pass' for r in runs),'Incomplete integration checks')
    scroll,control,fairness,fairness_control,cancel,shell,*inputs=runs
    for measured,replay in ((scroll,control),(fairness,fairness_control)):
        require(measured['observed'] and not replay['observed'],'Missing observed/control runs')
        require(measured['build']['xex_sha256']==replay['build']['xex_sha256'],'Replay image changed')
        require(measured['observations']==replay['observations'],'Replay pixels/checkpoints changed')
    require(len(scroll['observations'])==13 and scroll['checks']==control['checks']==[93],'Missing scroll scenes')
    require(scroll['pin']==baseline['pin'],'Scroll pin changed')
    require(all(not v['routines'] for v in scroll['performance']['idle_input']),'Idle worker spins')
    comparisons=[]
    for before in baseline['scrolls']:
        stage=next(s for s in scroll['performance']['stages'] if s['stage']==before['stage'])
        old=before['scroll_input'][0];new=stage['scroll_input'][0]
        routines=new['routines']
        require(not any(n in routines for n in ('input_pending','public_pending','pump','input_take','input_extent')),'Quiet output checks input')
        require(all(routines[n]['calls']==16 for n in ('signal_collect','input_collect_turn','input_service_turn')),'Wrong per-turn collection count')
        require(new['components']==['input_service_turn','input_collect_turn','runnable'],'Missing caller flag/decision cost')
        reduction=1-new['input_check_ms']/old['input_check_ms']
        require(new['input_check_ms']<=13 and reduction>=.75,'Idle input performance gate failed')
        comparisons.append(dict(stage=stage['stage'],before_scroll_ms=before['edit_through_final_chunk_ms'][0],
            after_scroll_ms=stage['edit_through_final_chunk_ms'][0],before_input_ms=old['input_check_ms'],
            after_input_ms=new['input_check_ms'],input_reduction_percent=100*reduction,routines=routines,
            components=new['components']))
    require(fairness['timing']['verdict']=='pass' and fairness['runtime']['created']==7,'Missing loaded eight-Task timing')
    require(fairness['pointer']['losses']==0 and fairness['pointer']['samples']>=2,'Missing active ST capture')
    require(fairness['screen_sha256']==fairness_control['screen_sha256'],'Loaded replay pixels changed')
    require(fairness['media_sha256']==fairness_control['media_sha256'],'Loaded replay media changed')
    require(shell['case']['serial_timing']['verdict']=='pass','Shell SIO timing failed')
    for r,mode in zip(inputs,(0,2,4)):
        require(r['mode']==mode and r['native_events']>0 and r['input_observations']['post_nmi_checkpoints']>0,'Missing input/NMI capture')
        require(r['captured']==([27] if mode==4 else [97,98,65,1,3,10,27]),'Input bytes changed')
    require(inputs[1]['emulation_events']>0 and inputs[2]['losses']==[1],'Missing emulation/overflow checks')
    before_program=read_build(ROOT/'build/console-idle-input/q0/scroll-opt/program')
    after_program=read_build(out/'scroll-opt/program')
    def image_usage(p):
        worker=next(r for r in p['image']['routines'] if r['name'].startswith('M_CONSOLEDRIVER_WORKER_'))
        return dict(initialized_image_bytes=sum(len(s['bytes']) for s in p['image']['segments']),
            zero_fill_bytes=sum(s['size'] for s in p['image']['zero_fill']),
            worker={k:worker[k] for k in ('size','fixed_frame','spill_bytes','local_stack_peak')})
    for r in runs:
        for name in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(r['build']['memory'][name]==before_program['build']['memory'][name],'Changed reserved memory '+name)
    host=host_log.read_text();count=re.search(r'Ran (\d+) tests',host)
    require(count and 'OK (skipped=4)' in host and 'FAILED' not in host,'Incomplete host checks')
    names=['tools/record_console_idle_input.py','tools/bitmap_console_performance.py','tools/test_console_input.py',
        'tools/test_console_coexistence.py','tools/test_shell_break.py']
    diagnostic=out/'input-before-q1/results.json'
    require(json.loads(diagnostic.read_text())['status']=='fail','Diagnostic result changed; reassess 125k stress limit')
    return dict(slice='Q3',status='development-pass',scope='Matched optimized PAL x8 VBXE/4MB scroll comparison; raw/optimized worker races from Q2; physical input in native/emulation contexts and overflow, cancellation, physical shell BREAK, eight-Task SDFS/ST timing and observed/control replays.',
        reports={str(p.relative_to(ROOT)):sha256(p) for p in paths},
        source_inputs={**{p:sha256(ROOT/p) for p in names},**{p:h for p,h in q2['source_inputs'].items() if p.startswith('lib/')}},
        baseline_evidence_sha256=sha256(ROOT/'docs/development/console-idle-input-q0.json'),
        worker_evidence_sha256=sha256(ROOT/'docs/development/console-idle-input-q2.json'),
        pin=scroll['pin'],machine=scroll['machine'],comparison=comparisons,
        input_check_limit_ms=13,input_reduction_required_percent=75,
        timing_scope='Elapsed guest cycles including preemption. Collection includes caller mask stores/stop test; service includes caller flag arguments/stores and clearing local bits. Whole Runnable charged conservatively if called. Nested spans are not added.',
        cases=[dict(name=str(p.parent.relative_to(out))+'/'+p.name,xex_sha256=r['build']['xex_sha256'],
            compiler={k:r['build'][k] for k in ('revision','binary_sha256','abi_sha256','override')},
            runtime=runtime_summary(r.get('runtime',r.get('case',{}).get('runtime',{})))) for p,r in zip(paths,runs)],
        loaded=dict(counters=fairness['counters'],pointer=fairness['pointer'],
            timing=fairness['timing'],pointer_timing={k:v for k,v in fairness['mouse_timing'].items() if k!='serial'},
            replay_counters=fairness_control['counters'],pin=fairness['pin'],machine=fairness['machine']),
        shell=dict(pin=shell['pin'],machine=shell['case']['machine'],break_timing=shell['case']['break_timing'],serial_timing=shell['case']['serial_timing']),
        input=[{k:r[k] for k in ('mode','captured','checks','native_events','emulation_events','losses','input_observations')} for r in inputs],
        input_pin=inputs[0]['pin'],cancel_checks=cancel['checks'],
        image_memory=dict(before=image_usage(before_program),after=image_usage(after_program)),
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        host_checks=dict(tests=int(count[1]),skipped_historical=4,status='pass',log_sha256=sha256(host_log)),
        supplemental_probe=dict(scope='Standalone 125 kbaud continuous SIO with forced NMI inside keyboard posting',
            result='First transfer overruns; io_Error=5, io_Actual=68, fixture assertion followed by reset-required FF93. Reproduces with the pre-Q1 pump. This extra profile is not qualified here.',
            baseline_report=str(diagnostic.relative_to(ROOT)),baseline_report_sha256=sha256(diagnostic),
            changed_log_sha256=sha256(out.parent/'q3-input-replay.log'),baseline_log_sha256=sha256(out.parent/'q3-input-before-q1.log')),
        limits=['Development checks, not release or physical-cartridge qualification.',
            'The separate 20 ms full scroll target remains unmet; no new 40 ms visible-input or 500 ms repaint claim.',
            'SDFS/ST concurrency uses the existing paced profile 4 workload and unchanged SIO/pointer/Forbid limits.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--slice',choices=('q0','q1','q2','q3'),default='q0');p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--host-log',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(dict(q0=baseline,q1=pump,q2=worker,q3=integration)[a.slice](a.input.resolve(),a.host_log),indent=2)+'\n')
