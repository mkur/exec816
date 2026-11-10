#!/usr/bin/env python3
"""Passive drawing breakdown on the unchanged optimized AES corpus."""
import argparse
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

import measure_magic_aes as corpus
from aes_drawing_profile import CATEGORIES, COUNTERS, partition_cpu, physical_units
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls, listing_returns, native_calls
from native_program import require, sha256
from sio_transaction_trace import read_events


NATIVE = ('DISPLAY_ENTER', 'DISPLAY_LEAVE', 'DISPLAY_CHECK', 'DISPLAY_VALID',
    'DISPLAY_DELEGATED')
EXTRA = {'App_gr_box', 'App_gr_rect', 'ob_sst', 'App_ob_offset', 'GemVdiPaint',
    'GemVdiDispatch', 'GemVdiValidate', 'vbxe_flush', 'GemDrawingPrepare'}
ORIGINAL_DEFINITION = corpus.trace_definition


def definition(program, foreign, out):
    result = ORIGINAL_DEFINITION(program, foreign, out)
    wanted = set().union(*CATEGORIES.values()) | set(COUNTERS) | EXTRA
    symbols = foreign['symbols']
    present = sorted(wanted & symbols.keys())
    missing = sorted(wanted - symbols.keys())
    entries = {symbols[n]: n for n in present}
    require(len(entries) == len(present), 'Aliased drawing entry needs explicit resolution')
    result['entries'].update(entries)
    # Observe actual RTL instructions too: indirect callbacks and optimized
    # tail calls can return through runtime code without a C JSL successor.
    exits = listing_returns(foreign, program['output'].parent/'drawing', exits=True)
    result['c_exits'] = exits
    for i, pc in enumerate(exits):
        result['timeline']['points']['drawing_exit_' + str(i)] = pc
    marks = native_markers(program, [(n, n) for n in NATIVE])
    require(set(marks) == set(NATIVE), 'Missing native drawing boundary')
    result['native'].update(marks)
    for name, mark in marks.items():
        result['timeline']['points'][name] = mark['entry']
        for i, pc in enumerate(mark['returns']):
            result['timeline']['points'][name + str(i)] = pc
    result['drawing_observer'] = dict(present=present, absent_or_inlined=missing,
        categories={n:sorted(v) for n,v in CATEGORIES.items()},
        inputs={str(p.relative_to(corpus.ROOT)):sha256(p) for p in (
            Path(__file__), corpus.ROOT/'tools/aes_drawing_profile.py')})
    return result


def analyze(out):
    d = json.loads((out/'trace-definition.json').read_text())
    report = json.loads((out/'results.json').read_text())
    require(report['status'] == 'pass', 'Drawing capture did not pass')
    events = read_events(out/'emulator.log', kinds={'cpu'})
    interrupts = {d['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in interrupts:
        events.pop()
    profile = analyze_events(events, d['timeline'], include_segments=True)
    native = native_calls(events, d['native'])
    entries = {int(k):v for k,v in d['entries'].items()}
    rows = []
    for dp in d['timeline']['task_dps']:
        clock = Timeline(profile['segments'], dp)
        spans, unfinished = calls(events, entries, set(d['returns']), dp, set(d['c_exits']))
        workloads = sorted((s for s in spans if s['kind'] == 'MagicBaselineProbe'
            and s['argument'] < 3), key=lambda s:s['start'])
        if not workloads:
            continue
        require(not any(s['start'] <= workloads[-1]['end'] for s in unfinished),
            'Unfinished observed drawing call')
        presenter = Timeline(profile['segments'], profile['worker_dp'])
        for work in workloads:
            nested = [s for s in spans if work['start'] <= s['start'] < s['end'] <= work['end']]
            draws = [s for s in nested if s['kind'] == 'objc_draw']
            require(len(draws) == 1 and draws[0]['return_a'] == 1,
                'Expected one successful object draw')
            draw = draws[0]
            inside = [s for s in nested if draw['start'] <= s['start'] < s['end'] <= draw['end']]
            units = physical_units(clock, inside, draw)
            native_inside = [s for s in native if s['dp'] == dp
                and draw['start'] <= s['start'] < s['end'] <= draw['end']]
            rows.append(dict(case=corpus.NAMES[work['argument']], start=work['start'],
                operation=clock.measure(work['start'], work['end']),
                presenter_cpu_ms=presenter.measure(work['start'], work['end'])['charged_cpu_ms'],
                drawing=clock.measure(draw['start'], draw['end']),
                exclusive_cpu_ms=partition_cpu(clock, inside, draw['start'], draw['end']),
                counts=dict(Counter(s['kind'] for s in inside)),
                routines={n:dict(calls=sum(s['kind'] == n for s in inside),
                    inclusive_cpu_ms=sum(clock.measure(s['start'], s['end'])['charged_cpu_ms']
                        for s in inside if s['kind'] == n)) for n in d['drawing_observer']['present']},
                native={n:dict(calls=sum(s['kind'] == n for s in native_inside),
                    inclusive_cpu_ms=sum(clock.measure(s['start'], s['end'])['charged_cpu_ms']
                        for s in native_inside if s['kind'] == n)) for n in NATIVE},
                units=units))
    groups = {}
    for name in corpus.NAMES[:3]:
        selected = sorted((r for r in rows if r['case'] == name), key=lambda s:s['start'])
        require(len(selected) == 10, 'Incomplete drawing cohort ' + name)
        selected = selected[corpus.WARMUPS:]
        units = [u for r in selected for u in r['units']]
        buckets = sorted(set().union(*(r['exclusive_cpu_ms'] for r in selected)))
        count_names = sorted(set().union(*(r['counts'] for r in selected)))
        group = dict(count=len(selected), discarded_warmups=corpus.WARMUPS,
            operation={k:corpus.summary([r['operation'][k] for r in selected])
                for k in selected[0]['operation']},
            drawing={k:corpus.summary([r['drawing'][k] for r in selected])
                for k in selected[0]['drawing']},
            presenter_cpu_ms=corpus.summary([r['presenter_cpu_ms'] for r in selected]),
            exclusive_cpu_ms={n:corpus.summary([r['exclusive_cpu_ms'].get(n, 0) for r in selected])
                for n in buckets},
            calls={n:corpus.summary([r['counts'].get(n, 0) for r in selected]) for n in count_names},
            routines={n:{k:corpus.summary([r['routines'][n][k] for r in selected])
                for k in ('calls', 'inclusive_cpu_ms')} for n in selected[0]['routines']},
            native={n:{k:corpus.summary([r['native'][n][k] for r in selected])
                for k in ('calls', 'inclusive_cpu_ms')} for n in NATIVE},
            physical_units=dict(count=len(units),
                **{scope:{k:corpus.summary([u[scope][k] for u in units])
                    for k in selected[0]['drawing']} for scope in ('transaction', 'owned_core', 'callback')}))
        require(abs(sum(v['mean'] for v in group['exclusive_cpu_ms'].values())
            - group['drawing']['charged_cpu_ms']['mean']) < 1e-6, 'Cohort CPU does not reconcile')
        groups[name] = group
    result = dict(format='exec816.aes-drawing-profile.v1', status='pass',
        tier='development', qualification=False, groups=groups, samples=rows,
        coverage=d['drawing_observer'], observer_sha256=sha256(Path(__file__)),
        capture_sha256=sha256(out/'results.json'), trace_sha256=sha256(out/'emulator.log'),
        limits=['Exclusive CPU buckets reconcile per sample; add means, not medians.',
            'Routine costs are inclusive and overlap the exclusive buckets.',
            'Buckets describe observed call scopes; unobserved/inlined helpers stay in their parent scope.',
            'Polling CPU is not exact hardware BUSY duration.',
            'Owned core is Enter-return to Leave-entry, a lower bound on ownership.',
            'No new batching, scheduling, runtime storage or guest instructions. Small samples do not establish tails.'])
    (out/'drawing-profile.json').write_text(json.dumps(result, indent=2)+'\n')
    for name, g in groups.items():
        print(name, 'drawing CPU mean', round(g['drawing']['charged_cpu_ms']['mean'], 3),
            {n:round(v['mean'], 3) for n,v in g['exclusive_cpu_ms'].items()}, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    if not args.analyze_only:
        with patch.object(corpus, 'trace_definition', definition):
            corpus.run(out, args.from_build.resolve() if args.from_build else None)
    analyze(out)
