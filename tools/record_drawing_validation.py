#!/usr/bin/env python3
"""Record development evidence for the drawing validation and async slices."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, require, sha256


def record(slice_name, paths):
    reports = {}
    for path in paths:
        path = path.resolve()
        value = json.loads(path.read_text())
        require(value['status'] == 'pass' or (slice_name=='D6' and value['status']=='timing-fail'),
            'Failed report: ' + str(path))
        build = value['build']
        reports[str(path.relative_to(ROOT))] = dict(
            sha256=sha256(path), status=value['status'], xex_sha256=build['xex_sha256'],
            compiler={k:build[k] for k in ('revision','override','binary_sha256','optimize')},
            pin=value.get('pin'),
            mode=value.get('mode'), machine=value.get('machine'),
            bank_zero_budget=build['memory']['bank_zero_budget'],
            task_pools=build['memory']['task_pools'],
            checks=value.get('checks'), cases=value.get('cases'),
            performance=value.get('performance'), timing=value.get('timing'),
            input_latency=value.get('input_latency'), scanout=value.get('scanout'),
            async_timing=value.get('async_timing'), candidate=value.get('candidate'),
            mouse_timing=value.get('mouse_timing'))
    paths = [ROOT/p for p in (
        'platform/altirraos/vbxe.c', 'c/include/hardware/vbxe.h',
        'ports/gem4xe/adapter/gem-vbxe.c', 'tools/bitmap_console_performance.py',
        'lib/console/console-bitmap-display.inc', 'lib/console/consoledriver.act',
        'lib/console/consoledisplay.act', 'lib/console/consolebitmap.act',
        'abi/console-bitmap.json', 'tools/measure_async_scroll.py',
        'toolchain/actionc.json', 'toolchain/altirra-gem-vdi.json')]
    result = dict(slice=slice_name, status='development-pass', reports=reports,
        source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in paths},
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        measurement_limits=[
            'Routine elapsed includes preemption; it is not isolated Task CPU time.',
            'Launch to idle is an upper bound, not an exact hardware BUSY edge.',
            'Settled pixels and fixture completion do not prove first-visible latency.'])
    baseline=ROOT/'docs/development/drawing-validation-d0.json'
    if slice_name != 'D0':
        old=json.loads(baseline.read_text())
        control=next(iter(old['reports'].values()))
        for report in reports.values():
            require(report['bank_zero_budget']==control['bank_zero_budget'], 'Changed bank-zero budget')
            require(report['task_pools']==control['task_pools'], 'Changed Task reservations')
        result['baseline_sha256']=sha256(baseline)
        if slice_name == 'D3':
            before=next(r['performance'] for r in old['reports'].values() if r.get('performance'))
            after=next(r['performance'] for r in reports.values() if r.get('performance'))
            result['comparison']=[]
            for stage in (2,3):
                a=next(s for s in before['stages'] if s['stage']==stage)
                b=next(s for s in after['stages'] if s['stage']==stage)
                ar=a['scroll_input'][0]['routines'];br=b['scroll_input'][0]['routines']
                require(ar['DisplayCheck']['calls']==49 and br['DisplayCheck']['calls']==16,
                    'Ownership count gate failed')
                require(ar['launch_to_idle']['calls']==br['launch_to_idle']['calls']==30,
                    'Hardware batching changed during validation comparison')
                validation=1-br['display_check']['total_ms']/ar['display_check']['total_ms']
                elapsed=1-b['edit_through_final_chunk_ms'][0]/a['edit_through_final_chunk_ms'][0]
                require(validation>=0.60 and elapsed>=0.10, 'Validation performance gate failed')
                result['comparison'].append(dict(stage=stage,
                    native_validation_elapsed_reduction=validation,scroll_elapsed_reduction=elapsed))
    if slice_name=='D6':
        current=next(r['performance'] for r in reports.values() if r.get('performance'))
        previous=json.loads((ROOT/'docs/development/drawing-validation-d3.json').read_text())
        previous=next(r['performance'] for r in previous['reports'].values() if r.get('performance'))
        result['comparison']=[]
        for stage in (2,3):
            a=next(s for s in previous['stages'] if s['stage']==stage)
            b=next(s for s in current['stages'] if s['stage']==stage)
            calls=b['scroll_input'][0]['routines']
            require(calls['GemDrawingScrollStart']['calls']==1 and calls['launch_to_idle']['calls']==1,
                'Production scroll did not have one start and launch')
            result['comparison'].append(dict(stage=stage,scroll_ms=b['edit_through_final_chunk_ms'][0],
                elapsed_reduction_from_d3=1-b['edit_through_final_chunk_ms'][0]/a['edit_through_final_chunk_ms'][0],
                starts=1,launches=1,polls=calls['GemDrawingScrollPoll']['calls'],
                admissions=calls['DisplayCheck']['calls']))
        visible=[s.get('target_40ms') for r in reports.values() for s in r.get('scanout') or []
                 if s.get('target_40ms')]
        result['status']='development-pass-performance-open'
        result['acceptance']=dict(functional='pass',
            coexistence='pass' if all(r['status']=='pass' for r in reports.values()) else 'fail',
            scroll_20ms='pass' if all(c['scroll_ms']<=20 for c in result['comparison']) else 'fail',
            visible_input_40ms='fail' if 'fail' in visible else 'unqualified',
            turn_cpu_4ms='unqualified',exact_busy_edges='unqualified',selected_geometry='whole rectangle')
    target=ROOT/f'docs/development/drawing-validation-{slice_name.lower()}.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(target.relative_to(ROOT))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('slice',choices=[f'D{i}' for i in range(7)])
    parser.add_argument('reports',type=Path,nargs='+')
    args=parser.parse_args()
    record(args.slice,args.reports)
