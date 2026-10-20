#!/usr/bin/env python3
"""Freeze measured editing development evidence after reconciling its inputs."""
import argparse
import json
import re
from pathlib import Path
from check_qed_baseline import check
from native_program import ROOT, require, sha256


def record(slice_name, directory, cohorts, destination, host_log):
    audit = check(directory, cohorts, [])
    audit_path = directory.parent / (slice_name.lower()+'-baseline.json')
    audit_path.write_text(json.dumps(audit, indent=2)+'\n')
    host = re.search(r'Ran (\d+) tests.*\n\nOK(?: \(skipped=(\d+)\))?\s*$',
                     host_log.read_text(), re.S)
    require(host is not None, 'Missing passing host suite result')
    layout = json.loads((directory / 'layout.json').read_text())
    frames = json.loads((directory / 'stack-frames.json').read_text())
    baseline = json.loads((ROOT / 'docs/development/qed-startup-qs5.json').read_text())
    measured = layout['layout']
    prior = baseline['executable']['layout']
    provider = layout['resident_provider']
    public = baseline['resident_provider']
    private_growth = dict(code_bytes=measured['code_bytes']-prior['code_bytes'],
        data_bss_bytes=measured['initialized_bytes']+measured['bss_bytes']-
            prior['initialized_bytes']-prior['bss_bytes'],
        metadata_bytes=(measured['serialized_bytes_if_executable']-measured['code_bytes']-
            measured['initialized_bytes'])-(prior['serialized_bytes_if_executable']-
            prior['code_bytes']-prior['initialized_bytes']))
    provider_growth = {k: provider[k]-public[k] for k in
                       ('code_bytes', 'table_bytes', 'data_bss_bytes')}
    remaining = {k: baseline['growth_from_step2']['provider_remaining_allowances'][k]-v
                 for k, v in provider_growth.items()}
    require(all(v >= 0 for v in remaining.values()), 'Provider exceeds frozen growth allowance')
    # Compare complete reservations, rather than only used stack watermarks.
    old_memory = json.loads((ROOT / 'build/qed-startup/qs4-failures/program/memory.json').read_text())
    memory = json.loads((cohorts[0] / 'program/memory.json').read_text())
    same_pools = memory['task_pools'] == old_memory['task_pools']
    same_regions = memory['regions'] == old_memory['regions']
    require(same_pools and same_regions,
            'Reservation changed: record a measured bank-zero budget amendment first')
    executed = []
    scenes = []
    for path in cohorts:
        result = json.loads((path / 'results.json').read_text())
        scenes.extend(result.get('qed_editing', []))
        executed.append(dict(path=str(path.relative_to(ROOT)),
            results_sha256=sha256(path / 'results.json'), completed=result['completed'],
            checks=result['checks'], snapshots=[s['name'] for scene in result.get('qed_editing', [])
                for s in scene['snapshots']],
            minimum_headroom=min(r['headroom'] for r in result['stacks']['minima']
                if r['lifetime'] and r['kind'] != 'async')))
    if slice_name == 'QE1':
        expected = {'empty', 'insert', 'split', 'join', 'allocation-rollback',
            'split-allocation-rollback', 'literal-tab', 'tab-delete', 'save-disabled',
            'close-cancel', 'native-up', 'native-right', 'overwrite',
            'forward-delete-join', 'quit-cancel', 'clean-shortcut', 'stop-dirty', 'stop-cancel'}
        seen = {s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected <= seen, 'Incomplete QE1 checkpoints: '+str(expected-seen))
        for scene in scenes:
            for snapshot in scene['snapshots']:
                require(snapshot['ending'] == 1 and bool(snapshot['dirty']) ==
                    (snapshot['name'] not in ('empty', 'clean-shortcut')),
                    'Incorrect ending/dirty state: '+snapshot['name'])
                require(snapshot['pixels']['checked'] > 0, 'Missing independent pixels')
    result = dict(schema_version=1, slice=slice_name, status='pass', tier='development',
        qualification=False,
        audit=dict(path=str(audit_path.relative_to(ROOT)), sha256=sha256(audit_path),
            auditor_sha256=audit['auditor_sha256'],provider_identity=audit['provider_identity']),
        source_pins={name: {k: pin[k] for k in ('revision', 'tree')}
                     for name, pin in audit['source_pins'].items()},
        host_checks=dict(path=str(host_log.relative_to(ROOT)),sha256=sha256(host_log),
            tests=int(host[1]),expected_skips=int(host[2] or 0)),
        executable=dict(path=str(directory.relative_to(ROOT)),
            sha256=layout['app']['sha256'], layout=measured),
        frame_ledger={k: frames[k] for k in ('source_chain_bytes', 'continuation_cap_bytes',
            'interrupt_reserve_bytes', 'required_headroom_bytes', 'admission_bytes', 'margin_bytes')},
        growth_from_QS5=dict(private=private_growth, provider=provider_growth),
        provider_remaining_allowances=remaining, executed=executed,
        private_heap=dict(peak_backing_bytes=max((s['private_heap'][3] for scene in scenes
            for s in scene['snapshots'] if 'private_heap' in s),default=0),
            basis='Private allocation headers included; underlying allocator rounding and native GUI owners charged separately'),
        bank_zero_delta=dict(fixed=0, per_public_task=0, private_idle=0,
            basis='Complete Task-pool and region maps equal QS5; guards, alignment and slack included'),
        recorder_sha256=sha256(Path(__file__)))
    destination.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slice', required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--cohort', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-log', type=Path, required=True)
    args = parser.parse_args()
    record(args.slice, args.layout.resolve(), [p.resolve() for p in args.cohort],
           args.output, args.host_log.resolve())
    print('QED editing evidence reconciled:', args.slice)
