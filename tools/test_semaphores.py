#!/usr/bin/env python3
"""Small emitted-code semaphore cases and passive complete-pair accounting."""
import argparse
import json
import os
import statistics
from pathlib import Path

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from g4bench_trace import calls
from sio_transaction_trace import read_events

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def inputs():
    paths = [ROOT/'tests/programs/semaphores.act',
             ROOT/'tools/native_program.py', ROOT/'tools/generate_tasks.py',
             ROOT/'toolchain/actionc.json']
    paths += list((ROOT/'lib').rglob('*.act')) + list((ROOT/'lib').rglob('*.inc'))
    paths += list((ROOT/'abi').glob('*.json')) + list((ROOT/'platform/altirraos').glob('*.s'))
    paths += list((ROOT/'platform/altirraos').glob('*.inc'))
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(paths))}


def definition(program):
    names = ('LibraryPair', 'LibraryObtain', 'LibraryRelease', 'FreePairs',
             'RecursivePairs', 'CounterTurn')
    native = native_markers(program, [('SEMAPHORES_'+name.upper(), name) for name in names])
    require(set(native) == set(names), 'Missing semaphore observation boundary')
    restore = program['labels']['context_restore']
    points = {name: program['labels'][name] for name in
              ('native_irq', 'native_nmi', 'interrupt_schedule')}
    points.update(selected=restore+4, turn=native['CounterTurn']['entry'])
    timeline = dict(points=points, spans={},
                    task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])
    pcs = set(points.values()) | {span['entry'] for span in native.values()}
    pcs.update(pc for span in native.values() for pc in span['returns'])
    return dict(native=native, timeline=timeline, pcs=sorted(pcs))


def analyze(path, definition):
    events = read_events(path, kinds={'cpu'})
    irqs = {definition['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in irqs:
        events.pop()
    profile = analyze_events(events, definition['timeline'], include_segments=True)
    native = definition['native']
    root_dps = {int(e[9], 16) for _, e in events if int(e[4], 16) == native['LibraryPair']['entry']}
    require(len(root_dps) == 1, 'No unique semaphore benchmark Task')
    root = root_dps.pop()
    timeline = Timeline(profile['segments'], root)
    spans, unfinished = calls(events, {v['entry']: n for n, v in native.items()}, set(), root,
                              {pc for v in native.values() for pc in v['returns']})
    require(not unfinished, 'Unfinished semaphore spans: '+str(unfinished))
    result = {}
    for name in ('FreePairs', 'RecursivePairs'):
        windows = [s for s in spans if s['kind'] == name]
        require(len(windows) == 1, 'Missing measured batch '+name)
        a, b = windows[0]['start'], windows[0]['end']
        pairs = [dict(s, **timeline.measure(s['start'], s['end'])) for s in spans
                 if s['kind'] == 'LibraryPair' and a <= s['start'] < s['end'] <= b]
        require(len(pairs) == 32, 'Wrong pair count: '+str((name, len(pairs))))
        result[name] = dict(samples=pairs, **{
            key: dict(min=min(p[key] for p in pairs), median=statistics.median(p[key] for p in pairs),
                      max=max(p[key] for p in pairs))
            for key in ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')})
    return dict(root_dp=root, counter_dp=profile['worker_dp'], batches=result,
                scope='Complete composition pair; Task CPU includes gateway/bus stalls; IRQ and off-Task time separate.')


def run(out, mode, from_build=None):
    out.mkdir(parents=True, exist_ok=True)
    frozen_inputs = inputs()
    if from_build:
        require(json.loads((from_build/'inputs.json').read_text()) == frozen_inputs, 'Changed semaphore build inputs')
        program = read_build(from_build/'program')
    else:
        program = build(compiler(ROOT/'build/actionc', release=True), ROOT/'tests/programs/semaphores.act',
                        out/'program', tasks=True, optimize=mode == 'opt')
        (out/'inputs.json').write_text(json.dumps(frozen_inputs, indent=2)+'\n')
    require(program['build']['optimize'] == (mode == 'opt'), 'Wrong semaphore build mode')
    d = definition(program)
    (out/'definition.json').write_text(json.dumps(d, indent=2)+'\n')
    report = dict(status='running', tier='development', mode=mode, pin=PIN, build=program['build'],
                  runner_sha256=sha256(Path(__file__)))
    previous = {k: os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in d['pcs'])
    try:
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            runtime, _ = execute(bridge, program, timeout=120, frame_limit=1200,
                                 before_run=lambda b: b.profile_start())
            report['runtime'] = runtime
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            require(report['checks'] == 14, 'Semaphore fixture assertions: '+str(report['checks']))
            report['counter'] = data(bridge, program['image'], 'counter', True)[0]
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            clean_ownership(bridge, program, program['output'])
        report['timing'] = analyze(out/'emulator.log', d)
        report['status'] = 'pass'
        print('Passed', mode, 'semaphore composition;', report['checks'], 'checks', flush=True)
        print(json.dumps({n: v['charged_cpu_ms'] for n, v in report['timing']['batches'].items()}, indent=2))
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--suite', choices=('baseline',), default='baseline')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.from_build.resolve() if args.from_build else None)
