#!/usr/bin/env python3
"""Passive UPDATE breakdown on the unchanged matched AES workload."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from unittest.mock import patch

import measure_magic_aes as corpus
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls, native_calls
from native_program import require, sha256
from sio_transaction_trace import read_events

ROUTINES = '''AESWINDOWSTATE_BEGINUPDATE AESWINDOWSTATE_SNAPSHOTALL
AESWINDOWSTATE_PUBLISH AESWINDOWSTATE_ENDUPDATE AESWINDOWSTATE_UPDATES
DESKGEOMETRY_WORK REGIONS_CLIP LAYERS_PIXELSREADY LAYERS_TOUCH
DESKCACHE_BEGINCHANGE DESKCACHE_ENDCHANGE DESKCACHE_CLIENTBOUNDS
LAYERCACHE_ENDCHANGE AESLOCAL_CALL AESGATE_CLAIM
AESLOCKS_ATTEMPT AESLOCKS_ACQUIRE AESLOCKS_RELEASE'''.split()


def definition(program, foreign, out):
    result = original_definition(program, foreign, out)
    marks = native_markers(program, [(n,n) for n in ROUTINES])
    require(set(marks)==set(ROUTINES), 'Missing UPDATE observation boundary')
    result['native'].update(marks)
    for name, mark in marks.items():
        result['timeline']['points'][name] = mark['entry']
        for i, pc in enumerate(mark['returns']):
            result['timeline']['points'][name+str(i)] = pc
    return result


original_definition = corpus.trace_definition


def analyze(out):
    d = json.loads((out/'trace-definition.json').read_text())
    events = read_events(out/'emulator.log', kinds={'cpu'})
    interrupts = {d['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts: events.pop()
    profile = analyze_events(events,d['timeline'],include_segments=True)
    native = native_calls(events,d['native'])
    clocks = {dp:Timeline(profile['segments'],dp) for dp in d['timeline']['task_dps']}
    rows = []
    for dp,clock in clocks.items():
        c, unfinished = calls(events,{int(k):v for k,v in d['entries'].items()},set(d['returns']),dp)
        require(not any(s['kind']=='MagicBaselineProbe' for s in unfinished),'Unfinished workload')
        workloads = sorted((s for s in c if s['kind']=='MagicBaselineProbe'),key=lambda s:s['start'])
        for work in workloads:
            updates = [s for s in c if s['kind']=='wind_update' and
                       work['start']<=s['start']<s['end']<=work['end']]
            phases = {}
            for name,code in (('begin',1),('end',0)):
                selected = [u for u in updates if u['argument']==code]
                helpers = {}
                for n in ROUTINES:
                    nested = [s for s in native if s['kind']==n and
                        any(u['start']<=s['start']<s['end']<=u['end'] for u in selected)]
                    helpers[n] = dict(calls=len(nested),
                        caller_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms']
                            for s in nested if s['dp']==dp),
                        other_task_cpu_ms=sum(clocks[s['dp']].measure(s['start'],s['end'])['charged_cpu_ms']
                            for s in nested if s['dp']!=dp))
                phases[name] = dict(calls=len(selected),
                    caller_cpu_ms=sum(clock.measure(u['start'],u['end'])['charged_cpu_ms'] for u in selected),
                    elapsed_ms=sum(clock.measure(u['start'],u['end'])['elapsed_ms'] for u in selected),
                    rpc_calls=sum(1 for s in c if s['kind']=='ExecAESSubmit' and
                        any(u['start']<=s['start']<s['end']<=u['end'] for u in selected)),
                    helpers=helpers)
            rows.append(dict(case=corpus.NAMES[work['argument']],start=work['start'],phases=phases))
    groups = {}
    for i,name in enumerate(corpus.NAMES):
        selected = sorted((r for r in rows if r['case']==name),key=lambda r:r['start'])
        warm = 0 if i==6 else corpus.WARMUPS
        require(len(selected)==corpus.COUNTS[i]+warm,'Wrong workload count')
        selected = selected[warm:]
        phases = {}
        for phase in ('begin','end'):
            phases[phase] = {key:corpus.summary([r['phases'][phase][key] for r in selected])
                for key in ('calls','caller_cpu_ms','elapsed_ms','rpc_calls')}
            phases[phase]['helpers'] = {n:{key:corpus.summary([
                r['phases'][phase]['helpers'][n][key] for r in selected])
                for key in ('calls','caller_cpu_ms','other_task_cpu_ms')} for n in ROUTINES}
        groups[name] = dict(count=len(selected),phases=phases)
    result = dict(status='pass',tier='development',qualification=False,
        scope='Inclusive native costs within public UPDATE; helpers overlap. Guest workload unchanged.',
        groups=groups,samples=rows,observer_sha256=sha256(Path(__file__)))
    (out/'update-profile.json').write_text(json.dumps(result,indent=2)+'\n')
    for name,g in groups.items():
        print(name, {p:round(g['phases'][p]['caller_cpu_ms']['median'],3) for p in ('begin','end')},flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    parser.add_argument('--analyze-only',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if not args.analyze_only:
        with patch.object(corpus,'trace_definition',definition):
            corpus.run(out,args.from_build.resolve() if args.from_build else None)
    analyze(out)
