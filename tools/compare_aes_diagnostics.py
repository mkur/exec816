#!/usr/bin/env python3
"""Compare fixed-offer diagnostics without replacing HY4 acceptance limits."""
import argparse
import json
from pathlib import Path
from native_program import require, sha256


def schedule_key(report):
    require(report['status'] == 'pass' and report['diagnostic_only'], 'Incomplete diagnostic')
    load = report['offered_load']
    origin = load['start_frame']
    expected = list(range(0, report['frames'], load['period_frames']))
    actual = [r['frame']-origin for r in load['offers']]
    require(actual == expected and load['offered'] == len(expected), 'Unequal or missing offers')
    require(load['drained'] == load['offered'], 'Diagnostic lost outstanding offers')
    require(0 <= load['completed'] <= load['started'] <= load['offered'], 'Invalid offer accounting')
    require(load['pending'] == load['offered']-load['completed'], 'Invalid pending count')
    return dict(frames=report['frames'], period_frames=load['period_frames'],
                offers=actual, edges=[(s['frame']-origin,s['button']) for s in report['samples']],
                machine=report['machine'])


def compare(reports):
    require(len(reports) >= 2, 'Supply at least two fixed-offer results')
    keys = [schedule_key(r) for r in reports]
    require(all(key == keys[0] for key in keys), 'Workload schedule or machine differs')
    rows = []
    for report in reports:
        load = report['offered_load']
        calls = report['caller_breakdown']['records']
        rows.append(dict(load=report['load'], xex_sha256=report['xex_sha256'],
            offered=load['offered'], started=load['started'], completed=load['completed'],
            pending=load['pending'], calls=len(calls), native_progress=report['progress'],
            input=report.get('input_breakdown',{}).get('summary',{}),
            caller_cpu_ms=sum(r['charged_cpu_ms'] for r in calls),
            caller_costs=report['caller_breakdown']['summary']))
    return dict(status='pass', diagnostic_only=True, acceptance_evaluated=False,
                scope='Identical external offer and button-edge schedules on the same recorded machine. Backlog and boundary-crossing calls remain visible. These distributions do not replace continuous-workload or scanout acceptance.',
                schedule=keys[0], cohorts=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare([json.loads(path.read_text()) for path in args.results])
    result['sources'] = [dict(path=str(p), sha256=sha256(p)) for p in args.results]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
