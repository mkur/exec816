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
        require(value['status'] == 'pass', 'Failed report: ' + str(path))
        build = value['build']
        reports[str(path.relative_to(ROOT))] = dict(
            sha256=sha256(path), xex_sha256=build['xex_sha256'],
            compiler={k:build[k] for k in ('revision','override','binary_sha256','optimize')},
            pin=value.get('pin'),
            mode=value.get('mode'), machine=value.get('machine'),
            bank_zero_budget=build['memory']['bank_zero_budget'],
            task_pools=build['memory']['task_pools'],
            checks=value.get('checks'), cases=value.get('cases'),
            performance=value.get('performance'), timing=value.get('timing'))
    paths = [ROOT/p for p in (
        'platform/altirraos/vbxe.c', 'c/include/hardware/vbxe.h',
        'ports/gem4xe/adapter/gem-vbxe.c', 'tools/bitmap_console_performance.py',
        'lib/console/console-bitmap-display.inc', 'lib/console/consoledriver.act',
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
    target=ROOT/f'docs/development/drawing-validation-{slice_name.lower()}.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(target.relative_to(ROOT))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('slice',choices=[f'D{i}' for i in range(7)])
    parser.add_argument('reports',type=Path,nargs='+')
    args=parser.parse_args()
    record(args.slice,args.reports)
