#!/usr/bin/env python3
"""Controlled emitted UPDATE metadata cost and freshness checks."""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import native_calls
from measure_magic_aes import summary
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from sio_transaction_trace import read_events
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out,from_build=None):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(from_build/'program') if from_build else build(
        compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/aes_snapshot.act',
        out/'program',tasks=True,task_capacity=8,optimize=True,console=False,console_deferred=True)
    names='AESSNAPSHOTPROBE_SAMPLE AESWINDOWSTATE_BEGINUPDATE AESWINDOWSTATE_SNAPSHOTALL AESWINDOWSTATE_PUBLISH AESWINDOWSTATE_ENDUPDATE REGIONS_CLIP'.split()
    marks=native_markers(p,[(n,n) for n in names])
    require(set(marks)==set(names),'Missing metadata marker')
    points={n:p['labels'][n] for n in ('native_irq','native_nmi','interrupt_schedule')}
    points.update(selected=p['labels']['context_restore']+4,turn=marks[names[0]]['entry'])
    definition=dict(points=points,spans={},task_dps=[t['dp'] for t in p['build']['memory']['task_pools']])
    pcs=set(points.values())|{pc for m in marks.values() for pc in [m['entry'],*m['returns']]}
    environment=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)),EXEC816_MASK_TRACE='0')
    report=dict(status='running',tier='development',qualification=False,build=p['build'],
        harness_sha256=sha256(Path(__file__)),fixture_sha256=sha256(ROOT/'tests/programs/aes_snapshot.act'))
    try:
        with patch.dict(os.environ,environment),emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            try:report['runtime'],_=execute(b,p,before_run=lambda b:b.profile_start(),timeout=120,frame_limit=6000)
            finally:b.profile_stop()
            ownership(b,p,p['output'])
            report['checks']=data(b,p['image'],'checks',True)[0]
        events=read_events(out/'emulator.log',kinds={'cpu'})
        profile=analyze_events(events,definition,include_segments=True)
        spans=native_calls(events,marks)
        clock=Timeline(profile['segments'],profile['worker_dp'])
        samples=sorted((s for s in spans if s['kind']==names[0]),key=lambda s:s['start'])
        require(len(samples)==40,'Wrong controlled workload count')
        groups={}
        for i,name in enumerate(('one_fixed','four_fixed','four_fragmented','four_changed')):
            selected=samples[i*10+2:i*10+10]
            helpers={}
            for n in names[1:]:
                rows=[[s for s in spans if s['kind']==n and w['start']<=s['start']<s['end']<=w['end']] for w in selected]
                helpers[n]=dict(calls=summary([len(r) for r in rows]),
                    caller_cpu_ms=summary([sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in r) for r in rows]))
            groups[name]=dict(caller_cpu_ms=summary([clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in selected]),helpers=helpers)
        report.update(status='pass',groups=groups,marks=marks,definition=definition)
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Snapshot metadata checks passed:',report['checks'],flush=True)
    for name,g in groups.items():print(name,round(g['caller_cpu_ms']['median'],3),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    args=parser.parse_args()
    run(args.output.resolve(),args.from_build.resolve() if args.from_build else None)
