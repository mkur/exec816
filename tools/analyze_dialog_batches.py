#!/usr/bin/env python3
"""Size dialog drawing batches from an existing passive G4BENCH capture.

Models remove only intermediate DisplayLeave/DisplayEnter CPU. They retain
the existing draw calls, cursor/fence work and traversal between units. They
are CPU estimates, not predictions of elapsed time under a changed schedule.
"""
import argparse
from bisect import bisect_left
import json
import math
from pathlib import Path
import statistics

from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls, loaded_markers, read_trace
from native_program import require, sha256


UNIT_NAMES = ('background top', 'background middle 1', 'background middle 2',
              'background bottom', 'label', 'small box', 'OK button', 'Cancel button')
METRICS = ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')
MODELS = {
    'eight existing units': (1, 1, 1, 1, 1, 1, 1, 1),
    'five objects': (4, 1, 1, 1, 1),
    'four adjacent pairs': (2, 2, 2, 2),
    'three groups': (4, 2, 2),
    'whole dialog': (8,),
}


def stats(values):
    values = sorted(values)
    require(values, 'Empty distribution')
    return dict(count=len(values), mean=statistics.mean(values),
                median=statistics.median(values), p95=values[math.ceil(.95*len(values))-1],
                minimum=values[0], maximum=values[-1])


def merge_model(timeline, units):
    first, last = units[0], units[-1]
    removed = [u['leave'] for u in units[:-1]] + [u['enter'] for u in units[1:]]
    saved = sum(timeline.measure(s['start'], s['end'])['charged_cpu_ms'] for s in removed)
    envelope = timeline.measure(first['enter']['start'], last['leave']['end'])
    core = timeline.measure(first['enter']['end'], last['leave']['start'])
    return dict(removed_ownership_cpu_ms=saved,
                transaction_cpu_ms=envelope['charged_cpu_ms']-saved,
                owned_core_cpu_ms=core['charged_cpu_ms']-saved)


def analyze(directory):
    directory = Path(directory)
    report = json.loads((directory/'trace-results.json').read_text())
    require(report['status']=='pass', 'Capture did not pass')
    definition = json.loads((directory/'trace-definition.json').read_text())
    live = json.loads((directory/'loaded-app.json').read_text())
    trace = directory/'cpu-trace.log.gz'
    events = read_trace(trace, definition, live)
    profile = report['profile']
    row = next(r for r in profile['rows'] if r['name']=='five-object dialog')
    segments = analyze_events(events, definition['timeline'], include_segments=True)['segments']
    timeline = Timeline(segments, profile['task_dp'])
    entries, returns = loaded_markers(definition, live)
    spans, unfinished = calls(events, entries, returns, profile['task_dp'])
    require(all(s['start']>=row['samples'][-1]['end'] for s in unfinished), 'Incomplete calls')
    spans.sort(key=lambda s:s['start'])
    starts = [s['start'] for s in spans]

    def inside(span, kind=None):
        return [s for s in spans[bisect_left(starts,span['start']):bisect_left(starts,span['end'])]
                if s['end']<=span['end'] and (kind is None or s['kind']==kind)]

    def one(span, kind):
        found = inside(span, kind)
        require(len(found)==1, 'Expected one '+kind)
        return found[0]

    operations = []
    units_by_position = [[] for _ in UNIT_NAMES]
    models = {name:[] for name in MODELS}
    for sample in row['samples']:
        for operation_index, operation in enumerate(sample['operation_spans']):
            borrows = inside(operation, 'drawing_borrow')
            require(len(borrows)==8, 'Dialog no longer consists of eight drawing units')
            units = []
            for i, borrow in enumerate(borrows):
                enter, leave = one(borrow,'DisplayEnter'), one(borrow,'DisplayLeave')
                require(enter['return_a']==0 and leave['return_a']==0, 'Failed ownership call')
                require(enter['end']<leave['start'], 'Invalid ownership interval')
                erase = one(borrow,'pointer_erase')
                fences = inside(borrow,'fence_owner')
                require(len(fences)==2 and erase['end']<fences[0]['start'], 'Callback boundaries changed')
                data = dict(
                    position=i, name=UNIT_NAMES[i], sample=sample['sample'],
                    operation_index=operation_index, enter=enter, leave=leave,
                    transaction=timeline.measure(enter['start'],leave['end']),
                    owned_core=timeline.measure(enter['end'],leave['start']),
                    before_enter=timeline.measure(borrow['start'],enter['start']),
                    after_leave=timeline.measure(leave['end'],borrow['end']),
                    callback=timeline.measure(erase['end'],fences[0]['start']),
                    ownership_cpu_ms=sum(timeline.measure(s['start'],s['end'])['charged_cpu_ms']
                                         for s in (enter,leave)),
                    counts={kind:len(inside(borrow,kind)) for kind in
                            ('GemSolidFill','solid_record','blit_mask','_VbxeUpload',
                             '_VbxeTextUpload','VbxeOwnerSubmit','idle')})
                units.append(data)
                units_by_position[i].append(data)
            operations.append(dict(sample=sample['sample'],
                **timeline.measure(operation['start'],operation['end']),
                ownership_cpu_ms=sum(u['ownership_cpu_ms'] for u in units),
                owned_core_cpu_ms=sum(u['owned_core']['charged_cpu_ms'] for u in units),
                owned_core_off_cpu_ms=sum(u['owned_core']['off_cpu_ms'] for u in units),
                owned_core_interrupt_ms=sum(u['owned_core']['interrupt_ms'] for u in units),
                owned_core_elapsed_ms=sum(u['owned_core']['elapsed_ms'] for u in units),
                callback_cpu_ms=sum(u['callback']['charged_cpu_ms'] for u in units)))
            for name, sizes in MODELS.items():
                offset=0; batches=[]
                for size in sizes:
                    batches.append(merge_model(timeline,units[offset:offset+size]))
                    offset+=size
                models[name].append(batches)

    unit_summary=[]
    for name, group in zip(UNIT_NAMES,units_by_position):
        unit_summary.append(dict(name=name,
            ownership_cpu_ms=stats([u['ownership_cpu_ms'] for u in group]),
            slowest_owned_core=max(group,key=lambda u:u['owned_core']['elapsed_ms']),
            **{scope:{metric:stats([u[scope][metric] for u in group]) for metric in METRICS}
               for scope in ('transaction','owned_core','callback','before_enter','after_leave')},
            counts_per_unit={k:stats([u['counts'][k] for u in group]) for k in group[0]['counts']}))
    model_summary={}
    for name, groups in models.items():
        model_summary[name]=dict(groups=MODELS[name], acquisitions_per_dialog=len(MODELS[name]),
            removed_ownership_cpu_ms_per_dialog=stats([
                sum(b['removed_ownership_cpu_ms'] for b in batches) for batches in groups]),
            transaction_cpu_ms_per_dialog=stats([
                sum(b['transaction_cpu_ms'] for b in batches) for batches in groups]),
            longest_owned_core_cpu_ms_per_dialog=stats([
                max(b['owned_core_cpu_ms'] for b in batches) for batches in groups]),
            batches=[dict(first_unit=sum(MODELS[name][:i]), units=size,
                owned_core_cpu_ms=stats([batches[i]['owned_core_cpu_ms'] for batches in groups]))
                for i,size in enumerate(MODELS[name])])
    run=report['run']
    return dict(scope=__doc__, load=report['load'], operations=len(operations),
        archive_sha256=report['archive_sha256'], trace_sha256=sha256(trace),
        trace_report_sha256=sha256(directory/'trace-results.json'),
        analysis_sha256=sha256(Path(__file__)),
        inputs={k:run[k] for k in ('actionc_revision','emulator_sha256','rom','machine','runner_sha256')},
        guest_changes=False, status=run['status'], guards=run['runtime']['guards'],
        benchmark=run['benchmark']['rows'][-1],
        per_operation=row['per_operation'],
        presenter_cpu_ms_per_operation=row['presenter_cpu_ms_per_operation'],
        exclusive_cpu_ms_per_operation=row['exclusive_cpu_ms_per_operation'],
        routines_per_operation=row['routines_per_operation'],
        operation_distributions={metric:stats([o[metric] for o in operations])
            for metric in (*METRICS,'ownership_cpu_ms','owned_core_cpu_ms','owned_core_off_cpu_ms',
                           'owned_core_interrupt_ms','owned_core_elapsed_ms','callback_cpu_ms')},
        units=unit_summary, models=model_summary,
        limits=[
            'Pointer is stationary outside the drawing. Cursor overlap/movement is not measured.',
            'Owned core runs from DisplayEnter return to DisplayLeave entry, a lower bound on actual ownership duration.',
            'Transaction envelope includes Enter/Leave, and may include waiting before acquisition or after release.',
            'Models retain inter-unit traversal and all existing drawing/cursor/fence CPU; only intermediate ownership calls are removed.',
            'Modeled owned-core CPU excludes interrupts and scheduling. Larger batches can change both; no elapsed-time prediction.',
            'Per-unit p95 describes these repeated benchmark units, not UI input latency or a hard bound.',
            'Blitter polling is software CPU time, not a measurement of exact hardware BUSY time.',
        ])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=analyze(args.trace)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['load'],result['operations'],'dialogs:',result['per_operation'])
    for unit in result['units']:
        print(unit['name'],'owned CPU',round(unit['owned_core']['charged_cpu_ms']['mean'],3),
              'owned elapsed max',round(unit['owned_core']['elapsed_ms']['maximum'],3))
