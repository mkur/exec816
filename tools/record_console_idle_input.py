#!/usr/bin/env python3
"""Collect the reproducible Q0 console input baseline and control replays."""
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


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--host-log',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(baseline(a.input.resolve(),a.host_log),indent=2)+'\n')
