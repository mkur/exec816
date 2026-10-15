#!/usr/bin/env python3
"""Focused AES binding regression and passive identity/entry-cost observations."""
import argparse
from contextlib import contextmanager
from functools import partial
import json
import os
from pathlib import Path
import statistics
from unittest.mock import patch

from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls, listing_returns
from native_program import compiler, read_build, require, sha256
from sio_transaction_trace import read_events
import test_aes_server

NAMES = ('named_query', 'pb_query', 'scoped_update_pair', 'pb_update_pair',
         'named_menu', 'pb_menu', 'named_draw', 'pb_draw')


def analyze(out):
    definition = json.loads((out/'binding-definition.json').read_text())
    events = read_events(out/'emulator.log', kinds={'cpu'})
    timeline = definition['timeline']
    profile = analyze_events(events, timeline, include_segments=True)
    entries = {int(pc): name for pc, name in definition['entries'].items()}
    rows = []
    for dp in timeline['task_dps']:
        spans, unfinished = calls(events, entries, set(definition['returns']), dp)
        require(not any(s['kind']=='AESBindingProbe' for s in unfinished), 'Unfinished binding probe')
        clock = Timeline(profile['segments'], dp)
        for span in spans:
            if span['kind']!='AESBindingProbe' or not span['return_a']:
                continue
            nested = [s for s in spans if span['start']<=s['start']<s['end']<=span['end']]
            rows.append(dict(kind=NAMES[span['argument']],
                **clock.measure(span['start'],span['end']),
                calls={name:sum(s['kind']==name for s in nested)
                       for name in ('FindTask','ExecAESContext','ExecAESSubmit','Forbid','Permit')}))
    groups = {}
    for name in NAMES:
        selected = [r for r in rows if r['kind']==name]
        require(len(selected)>=8,'Missing binding samples: '+name)
        groups[name] = dict(count=len(selected),
            calls={k:statistics.mean(r['calls'][k] for r in selected) for k in selected[0]['calls']},
            **{metric:dict(mean=statistics.mean(r[metric] for r in selected),
                           median=statistics.median(r[metric] for r in selected))
               for metric in ('charged_cpu_ms','elapsed_ms','off_cpu_ms','interrupt_ms')})
    fixture=json.loads((out/'results.json').read_text())
    require(fixture['status']=='pass','Binding fixture failed')
    record=dict(status='pass',tier='development',qualification=False,guest_changes=False,
        groups=groups,scope='Eight calls per path with a querying peer; one extra named query under inherited Forbid. Entry through caller return, excluding outer JSL/argument setup. No UI latency claim.',
        assertions=fixture['AESChecks'],runtime=fixture['runtime'],machine=fixture['machine'],
        hashes={name:sha256(out/path) for name,path in (
            ('image','program/program.xex'),('definition','binding-definition.json'),('trace','emulator.log'))})
    (out/'binding-cost.json').write_text(json.dumps(record,indent=2)+'\n')
    for name,row in groups.items():
        print(name, 'FindTask',row['calls']['FindTask'],
              'CPU ms',round(row['charged_cpu_ms']['mean'],3),flush=True)


def run(out, replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    original_emulator=test_aes_server.emulator
    original_execute=test_aes_server.execute

    @contextmanager
    def observed(*args,**kwargs):
        p=read_build(out/'program')
        foreign=json.loads((out/'c-image.json').read_text())
        points={name:p['labels'][name] for name in ('native_irq','native_nmi','interrupt_schedule')}
        points.update(selected=p['labels']['context_restore']+4,
                      turn=foreign['symbols']['AESBindingProbe'],worker_retire=p['labels']['done'])
        timeline=dict(spans={},points=points,task_dps=[t['dp'] for t in p['build']['memory']['task_pools']])
        entries={foreign['symbols'][name]:name for name in
                 ('AESBindingProbe','FindTask','ExecAESContext','ExecAESSubmit','Forbid','Permit')}
        returns=sorted(listing_returns(foreign,out/'drawing'))
        (out/'binding-definition.json').write_text(json.dumps(dict(timeline=timeline,
            entries=entries,returns=returns),indent=2)+'\n')
        environment=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(
            f'{pc:x}' for pc in sorted(set(entries)|set(returns)|set(points.values()))))
        with patch.dict(os.environ,environment),original_emulator(*args,**kwargs) as bridge:
            yield bridge

    def execute(bridge,program,**kwargs):
        require(kwargs.get('before_run') is None,'Unexpected physical binding fixture')
        kwargs['before_run']=lambda b:b.profile_start()
        try:return original_execute(bridge,program,**kwargs)
        finally:bridge.profile_stop()

    if not replay:
        with patch.object(test_aes_server,'compiler',partial(compiler,release=True)), \
             patch.object(test_aes_server,'emulator',observed), \
             patch.object(test_aes_server,'execute',execute):
            test_aes_server.applications(out,'bindings')
    analyze(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();run(args.output,args.replay)
