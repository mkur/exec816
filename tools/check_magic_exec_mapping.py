#!/usr/bin/env python3
"""Check the MagiC/Exec architecture mapping's pinned inputs and selected facts."""
import argparse
import json
from pathlib import Path

from check_magic_architecture import ROOT, check as check_magic, digest, local_links, require

RECORD = ROOT/'docs/development/magic-exec-mapping.json'


def check(fetch=False):
    magic = check_magic(fetch=fetch)
    record = json.loads(RECORD.read_text())
    magic_record = json.loads((ROOT/'docs/development/magic-architecture.json').read_text())
    require(record['magic_revision'] == magic_record['magic_revision'], 'MagiC model revision changed')
    require(record['qualification'] is False, 'Architecture mapping cannot claim qualification')
    require(len(record['exec_revision']) == 40, 'Mapping needs an exact Exec basis')
    inputs = {}
    for row in record['inputs']:
        path = ROOT/row['path']
        data = path.read_bytes()
        require(digest(data) == row['sha256'], 'Changed mapping input: '+row['path'])
        inputs[row['path']] = data.decode()

    for row in record['source_checks']:
        text = inputs[row['path']]
        for marker in row.get('contains', []):
            require(marker in text, 'Missing mapping marker: '+row['id']+' '+marker)
        for marker in row.get('absent', []):
            require(marker not in text, 'Unexpected mapping marker: '+row['id']+' '+marker)
        if 'json_path' in row:
            value = json.loads(text)
            for part in row['json_path']:
                value = value[part]
            require(value == row['value'], 'Changed ABI fact: '+row['id'])

    magic_claims = {c['id'] for c in magic_record['claims']}
    for row in record['findings']:
        require(row['kind'] in ('existing-foundation', 'must-adapt', 'policy-difference',
                                'unsupported-feature', 'architectural-judgment'), 'Unknown finding kind')
        require(row['exec_inputs'] and set(row['exec_inputs']) <= inputs.keys(),
                'Untraced Exec finding: '+row['id'])
        require(row['magic_claims'] and set(row['magic_claims']) <= magic_claims,
                'Untraced MagiC finding: '+row['id'])

    links = 0
    for name in record['documentation_pages']:
        count, _ = local_links(ROOT/name)
        links += count
    require(all(v == 0 for k, v in record['resource_impact'].items() if k != 'includes'),
            'Documentation mapping must not reserve target memory')
    result = dict(status='pass', tier='documentation', qualification=False,
        magic_sources=magic['sources'], magic_structural_checks=magic['source_checks'],
        mapping_inputs=len(inputs), mapping_checks=len(record['source_checks']),
        findings=len(record['findings']), pages=len(record['documentation_pages']), local_links=links,
        evidence_sha256=digest(RECORD.read_bytes()), checker_sha256=digest(Path(__file__).read_bytes()),
        mapping_sha256=digest((ROOT/'docs/architecture/magic-exec-mapping.md').read_bytes()))
    output = ROOT/'build/magic-exec-mapping/checks.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Fetch missing hash-pinned MagiC inputs')
    check(parser.parse_args().fetch)
