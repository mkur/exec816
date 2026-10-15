#!/usr/bin/env python3
"""Trace the unchanged packaged G4BENCH, including loaded application routines."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil

from gem_applications import instances
from g4bench_trace import analyze, definition, marker_pcs, read_trace
from measure_g4bench import measure
from native_program import read_build, require, sha256
from os_boundary import run_to
import adapter_state as adapter


class Observer:
    def __init__(self, output, rectangles=False):
        self.output = output
        self.rectangles = rectangles

    def ready(self, session, symbols):
        apps = instances(session.b, session.p, session.p['output']/'bitmap-console')
        self.live = next(a for a in apps if a['name'] == 'g4bench')
        require(self.live['symbols']['g4b_ready'] == symbols['g4b_ready'], 'Wrong loaded app')
        (self.output/'loaded-app.json').write_text(json.dumps(self.live, indent=2)+'\n')
        session.b.profile_start()

    def drawn(self, session, symbols):
        b = session.b; marker = session.p['labels']['native_irq']
        condition = ('(@xpc=$%x)&(dw($%x)>=1)'%(marker, symbols['g4b_row']) if self.rectangles else
                     '(@xpc=$%x)&(dw($%x)=4)'%(marker, symbols['g4b_phase']))
        b.bp_clear_all(); b.bp_set(marker, condition=condition)
        b.bp_set(session.p['labels']['done'], condition=adapter.STOPPED)
        run_to(b, marker, frame_limit=12000, timeout=900, condition=condition)
        b.profile_stop()
        print('Drawing trace captured; reporting and shutdown are untraced', flush=True)

    def finished(self, session, symbols, result):
        (self.output/'loaded-app.json').write_text(json.dumps(self.live, indent=2)+'\n')


def save_profile(out, report, profile):
    viewer = profile.pop('viewer_events')
    (out/'drawing-trace.json').write_text(json.dumps(dict(traceEvents=viewer,
        displayTimeUnit='ms', otherData=dict(scope='First UPDATE group of sample 1: four primitives or one dialog, including visibility and event polling. '
        'Each workload starts at zero on its own lane; this is not a simultaneous execution.')), indent=2)+'\n')
    report['profile'] = profile
    report['analysis_sha256'] = sha256(Path(__file__).with_name('g4bench_trace.py'))
    lines = ['# G4BENCH passive drawing trace', '', profile['scope'], '',
             'All values below are means per operation over the three measured batches.', '',
             '| Workload | Elapsed ms | Task CPU ms | Other Tasks ms | Interrupt ms |',
             '| --- | ---: | ---: | ---: | ---: |']
    for row in profile['rows']:
        m = row['per_operation']
        lines.append('| '+row['name']+' | '+' | '.join(f'{m[k]:.3f}' for k in
            ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms'))+' |')
    categories = sorted({k for r in profile['rows'] for k in r['exclusive_cpu_ms_per_operation']})
    lines += ['', '## Exclusive CPU costs', '', '| Work | '+' | '.join(r['name'] for r in profile['rows'])+' |',
              '| --- | '+' | '.join('---:' for _ in profile['rows'])+' |']
    for name in categories:
        lines.append('| '+name+' | '+' | '.join(f'{r["exclusive_cpu_ms_per_operation"].get(name,0):.3f}'
                                               for r in profile['rows'])+' |')
    lines += ['', 'The drawing-trace.json file uses the Chrome Trace Event format. It shows a short',
              'group on a separate lane for each workload; routine durations include preemption.',
              'Raw CPU observations are in cpu-trace.log.gz. No guest code or reservations changed.', '']
    (out/'trace-summary.md').write_text('\n'.join(lines))


def run(bundle, output, load='idle', rectangles=False):
    out = Path(output).resolve()
    require(not out.exists(), 'Use a fresh trace output directory')
    shutil.copytree(Path(bundle).resolve(), out, ignore=shutil.ignore_patterns(
        'g4bench-extracted-*', 'extracted', 'emulator.log', '*.png'))
    p = read_build(out)
    directory = out/'bitmap-console'
    foreign = json.loads((directory/'c-image.json').read_text())
    app = json.loads((directory/'apps/g4bench/app.json').read_text())
    d = definition(p, foreign, app, directory)
    (out/'trace-definition.json').write_text(json.dumps(d, indent=2)+'\n')
    points = marker_pcs(d)
    previous = {key: os.environ.get(key) for key in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
    observer = Observer(out, rectangles)
    report = dict(status='running', tier='development', qualification=False, load=load,
                  archive_sha256=sha256(out/'exec816-demo.zip'), observer_pcs=len(points),
                  bank_zero_delta=dict(fixed=0, per_public_task=[0]*8, idle=0),
                  guest_changes=False)
    print('Passive G4BENCH trace:', len(points), 'PCs', flush=True)
    try:
        result = measure(out, load, observer, rectangles)
        report['run'] = result
        events = read_trace(out/'emulator.log', d, observer.live)
        # A shareable raw trace contains only CPU observations. Do not copy
        # bridge session credentials or unrelated emulator diagnostics.
        with gzip.open(out/'cpu-trace.log.gz', 'wt') as trace:
            trace.write('[SIOTXN] anchor '+str(int(events[0][0]))+'\n')
            for _, fields in events:
                trace.write('[SIOTXN] '+' '.join(fields)+'\n')
        report['trace_sha256'] = sha256(out/'cpu-trace.log.gz')
        save_profile(out, report, analyze(events, d, observer.live, result['benchmark']))
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=type(error).__name__+': '+str(error))
        raise
    finally:
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        (out/'trace-results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['profile']['rows']:
        print(row['name'], {k:round(v, 3) for k, v in row['per_operation'].items()}, flush=True)
    return report


def reanalyze(output):
    out = Path(output).resolve()
    report = json.loads((out/'trace-results.json').read_text())
    d = json.loads((out/'trace-definition.json').read_text())
    live = json.loads((out/'loaded-app.json').read_text())
    trace = out/'cpu-trace.log.gz'
    if not trace.exists(): trace = out/'emulator.log'
    profile = analyze(read_trace(trace, d, live), d, live,
                      report['run']['benchmark'])
    save_profile(out, report, profile)
    report.update(status='pass', analysis_sha256=sha256(Path(__file__).with_name('g4bench_trace.py')))
    report.pop('error', None)
    (out/'trace-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print((out/'trace-summary.md').read_text())
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--load', choices=('idle', 'counter'), default='idle')
    parser.add_argument('--analyze', action='store_true', help='Re-analyze an existing capture without booting')
    parser.add_argument('--rectangles', action='store_true')
    args = parser.parse_args()
    if args.analyze: reanalyze(args.output)
    else:
        require(args.bundle is not None, '--bundle is required for capture')
        run(args.bundle, args.output, args.load, args.rectangles)
