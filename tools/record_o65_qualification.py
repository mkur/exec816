#!/usr/bin/env python3
"""Assemble L4 evidence only after the complete native matrix passes."""
import argparse
import json
from pathlib import Path

from generate_program import ABI, provider_manifest
from native_program import ROOT, read_build, require, sha256


def collect(path):
    result = json.loads(path.read_text())
    require(result['status'] == 'pass', 'Unsuccessful case: '+str(path))
    require(all(c['status'] == 'pass' for c in result['cases']), 'Incomplete native case')
    p = read_build(path.parent)
    require(p['build'] == result['build'], 'Build changed since execution')
    require(sha256(path.parent/p['build']['source']) == p['build']['source_sha256'],
            'Native fixture source changed since emission')
    for name, digest in result.get('observers', {}).items():
        require(sha256(path.parent/name) == digest, 'Changed observation source: '+name)
    if 'observer_sha256' in result:
        require(sha256(path.parent/'programfile.act') == result['observer_sha256'],
                'Changed disk-fault observation source')
        source = (path.parent/'programfile.act').read_text()
        result['fault_phase'] = ('seek' if source.index('O65FAULTPROBE.Opened(0)') <
                                 source.index('position=DOS.Seek') else 'read')
    for field in ('platform_inputs', 'task_inputs', 'console_inputs', 'banked_inputs'):
        for name, digest in p['build'].get(field, {}).items():
            require(sha256(ROOT/name) == digest, 'Stale native input: '+name)
    encoded, providers = provider_manifest(p['image'], p['labels'], True)
    manifest = json.loads((path.parent/'providers.json').read_text())
    require(manifest['providers'] == providers, 'Provider evidence differs from emitted code')
    address = p['build']['task_storage']['BASE']+ABI['provider_offset']
    segments = [s for s in p['image']['segments'] if s['address'] == address]
    require(len(segments) == 1 and bytes(segments[0]['bytes']) == encoded,
            'Provider contracts differ from the loaded manifest')
    return dict(result, providers=manifest, evidence_sha256=sha256(path))


def check_matrix(record):
    transports = record['transport']
    require({(r['mode'], r['sector_bytes'], r['profile']) for r in transports} ==
            {(mode, size, profile) for mode in ('raw', 'opt')
             for size, profile in ((128, 1), (256, 1), (256, 4), (128, 2))},
            'Incomplete transport matrix')
    require(len(transports) == 8, 'Duplicate transport cases')
    for result in transports:
        require(result['kernel_bank'] == 1, 'Unexpected transport kernel bank')
        observed, replay, functional = result['cases']
        require(observed['trace'] and observed['timing']['verdict'] == 'pass', 'Missing timing gate')
        require(not replay['trace'] and not functional['trace'], 'Missing untraced runs')
        require(observed['timing_only'] and replay['timing_only'] and not functional['timing_only'],
                'Incomplete workload coverage')
        require(observed['media_sha256'] == replay['media_sha256'] == functional['media_sha256'],
                'Replay media mismatch')
        require(observed['placements'] == replay['placements'], 'Replay placement mismatch')
        require(functional['processes'] == 9 and functional['checks'] >= 89, 'Missing failure/reuse coverage')
        require(all(max(p['live'] for p in c['placements']) == 8 for c in result['cases']),
                'Missing full-capacity admission')
        if result['sector_bytes'] == 256:
            require(result['files']['DATA.BIN'] == 70003, 'Missing long-file workload')
    for group in ('bank3', 'large', 'fault_seek', 'fault_read'):
        require(sorted(r['mode'] for r in record[group]) == ['opt', 'raw'], 'Missing modes: '+group)
    for result in record['bank3']:
        require(result['kernel_bank'] == 3 and result['cases'][0]['processes'] == 9,
                'Missing bank-3 lifetime coverage')
    for result in record['large']:
        require({c['case'] for c in result['cases']} == {'multibank', 'stack-overflow'},
                'Missing multi-bank/fault execution')
    for group in ('fault_seek', 'fault_read'):
        for result in record[group]:
            require(result['fault_phase'] == group.removeprefix('fault_'), 'Wrong fault checkpoint')
            require({c['case'] for c in result['cases']} == {'checksum', 'device', 'short'},
                    'Missing peripheral failure coverage')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for group in ('transport', 'bank3', 'large', 'fault_seek', 'fault_read'):
        parser.add_argument('--'+group.replace('_', '-'), type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = dict(schema_version=1, status='pass', tier='qualification', slice='L4', date='2026-09-25',
                  bank_zero_delta=dict(fixed=0, per_task=0))
    for group in ('transport', 'bank3', 'large', 'fault_seek', 'fault_read'):
        record[group] = [collect(path.resolve()) for path in getattr(args, group)]
    check_matrix(record)
    paths = [*ROOT.glob('abi/*.json'), *ROOT.glob('lib/*/*.act'), *ROOT.glob('lib/*/*.inc'),
             *ROOT.glob('examples/shell/*.inc'), *ROOT.glob('examples/commands/*.act'),
             *ROOT.glob('tests/programs/o65*.act'), *ROOT.glob('tests/programs/disk_*.act'),
             *ROOT.glob('tools/*o65*.py')]
    record['source_inputs'] = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(paths)}
    record['scope'] = [
        'source_inputs is the final repository snapshot; each case retains its actual native build and observation hashes.',
        'Two loaded Processes alive during foreground shell execution, eight live Tasks, long file input, all loader allocation failures, load/execution BREAK and reuse.',
        'Each timing case has the same-image/input replay without tracing and a separate complete functional failure run.',
        'Bank-3 cases retain their original observation hashes; their holding loop predates the bounded-compute timing fixture.',
        'Seek faults occur with an open file; read faults occur after staging allocation. Recoverable faults permit another launch. Offline retains the original cause and requires reset.',
        'Loaded stack overflow stops the hosted session and retains the live Image; per-command fault isolation is unsupported.',
        'This qualifies the loader matrix, not the general compiler update or independent console-window release.'
    ]
    args.output.write_text(json.dumps(record, indent=2)+'\n')
    print('Complete o65 qualification evidence:', args.output)
