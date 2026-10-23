#!/usr/bin/env python3
"""Reconcile immutable saving evidence, current source, packages and fresh reads."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from c_program import ABI
from native_program import ROOT, require, sha256


def read(path):
    return json.loads(path.read_text())


def stamp(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=sha256(path))


def verify_stamps(value):
    """Check recorded artifacts without changing their historical records."""
    if isinstance(value, dict):
        if set(value) == {'path', 'sha256'}:
            path = ROOT / value['path']
            require(sha256(path) == value['sha256'], 'Changed evidence: ' + str(path))
        else:
            for child in value.values():
                verify_stamps(child)
    elif isinstance(value, list):
        for child in value:
            verify_stamps(child)


def package(directory):
    manifest = read(directory / 'demo-manifest.json')
    for name, digest in manifest['source_inputs'].items():
        require(sha256(ROOT / name) == digest, 'Package input changed: ' + name)
    smoke = directory / ('gem-desktop-results.json' if manifest.get('gem_desktop') else 'demo-results.json')
    result = read(smoke)
    require(result['status'] == 'pass' and result['autoboot_frames'] == 249 and
            result['distribution_root'] and result['bundle_manifest_sha256'] == sha256(directory / 'demo-manifest.json'),
            'Package lacks its matching exact-ZIP smoke')
    with zipfile.ZipFile(directory / 'exec816-demo.zip') as archive:
        names = archive.namelist()
        prefix = 'exec816-demo/'
        sums = archive.read(prefix + 'SHA256SUMS').decode().splitlines()
        checked = []
        for line in sums:
            digest, name = line.split(None, 1)
            name = name.lstrip('*')
            require(hashlib.sha256(archive.read(prefix + name)).hexdigest() == digest,
                    'ZIP checksum differs: ' + name)
            checked.append(prefix + name)
        require(set(names) == set(checked) | {prefix + 'SHA256SUMS'}, 'Unlisted package entry')
        require({prefix + n for n in ('Exec-of816.xex', 'system.atr', 'OF816-LICENSE.txt',
                'altirraos-816.rom', 'ALTIRRAOS-LICENSE.txt', 'README.txt')} <= set(names), 'Incomplete OF816 package')
        require(not any('qed' in n.lower() for n in names), 'Private QED in development package')
    return dict(zip=stamp(directory / 'exec816-demo.zip'), smoke=stamp(smoke),
                matching_source_inputs=len(manifest['source_inputs']), checked_entries=len(names),
                scope='Unchanged exact QW1 development package; no publication or cartridge qualification')


def audit(output, combined, readers, layout, packages):
    output = output.resolve()
    require(not output.exists(), 'Evidence is immutable: choose a new output')
    combined = combined.resolve()
    layout = layout.resolve()
    require(len(packages) == 2 and {bool(read(p / 'demo-manifest.json').get('gem_desktop'))
            for p in packages} == {False, True}, 'Reconcile both standard and GEM packages')
    previous = []
    for index in range(1, 8):
        path = ROOT / ('docs/development/qed-saving-qw%d.json' % index)
        data = read(path)
        require(data['abi'] == ABI['version'] and data['tier'] == 'development' and
                not data['qualification'], 'Wrong evidence scope/ABI')
        verify_stamps(data)
        previous.append(stamp(path))
    production = read(layout / 'layout.json')
    require(not production['image']['provenance']['analysis_only'], 'Analysis-only production layout')
    for name, digest in production['build_inputs'].items():
        require(sha256(Path(name)) == digest, 'Production input changed: ' + name)
    selected = read(combined / 'app/layout.json')
    # Prepared donor paths have different build roots. Match their source-tree
    # suffix, while headers/native/runtime inputs keep their absolute identity.
    def identity(name):
        return name.split('/inputs/source/', 1)[-1] if '/inputs/source/' in name else name
    current = {identity(n): v for n, v in selected['build_inputs'].items()}
    for name, digest in production['build_inputs'].items():
        require(current.get(identity(name)) == digest, 'Combined APP differs from production source: ' + name)
    result = read(combined / 'results.json')
    require(result['status'] == 'pass' and result['completed'] == [4] and
            result['build']['foreign_image']['c_program_provider']['abi'] == ABI['version'],
            'Combined editor gate failed')
    for name, digest in result['observer_inputs'].items():
        require(sha256(ROOT / name) == digest, 'Combined observer changed: ' + name)
    from test_qed_saving_gate import audit as audit_media
    audit_media(combined)
    fresh = []
    fresh_combined = False
    for directory in readers:
        directory = directory.resolve()
        proof = read(directory / 'fresh-reopen-audit.json')
        require(proof['status'] == 'pass' and proof['fresh_native_services'] and proof['readonly'] and
                proof['image_sha256'] == sha256(directory / 'system.atr') and
                proof['reader_result_sha256'] == sha256(directory / 'results.json') and
                read(directory / 'results.json')['status'] == 'pass', 'Fresh service read failed')
        fresh.append(stamp(directory / 'fresh-reopen-audit.json'))
        if proof['writer_result_sha256'] == sha256(combined / 'results.json'):
            require(proof['image_sha256'] == sha256(combined / 'system.atr'), 'Fresh reader used another writer image')
            fresh_combined = True
    require({read(p.resolve() / 'results.json')['filesystem'] for p in readers} == {'mydos', 'sdfs'},
            'Fresh reads must cover both disk formats')
    require(fresh_combined, 'Combined writer needs an exact-image fresh-service reopen')
    # Reuse the foundation's full provider/source/resource and emitted-PC stack
    # audit for current cohorts. Historical cohorts retain their frozen scope.
    from check_qed_baseline import check
    baseline_path = output.with_name(output.stem + '-baseline.json')
    require(not baseline_path.exists(), 'Baseline evidence already exists')
    checked = check(layout, [combined, *[p.resolve() for p in readers]], [p.resolve() for p in packages],
                    persisted_media=True)
    oracle_inputs = []
    for directory in [combined, *[p.resolve() for p in readers]]:
        font = directory / 'selected/src/vdi/font8x8.c'
        sources = read(directory / 'c-image.json')['provenance']['source_inputs']
        digests = {v for n, v in sources.items() if n.endswith('/src/vdi/font8x8.c')}
        require(digests == {sha256(font)}, 'Pixel oracle font differs from the native provider')
        oracle_inputs.append(stamp(font))
    baseline_path.write_text(json.dumps(checked, indent=2) + '\n')
    editing = read(ROOT / 'docs/development/qed-editing-qe7.json')
    baseline = editing['executable']['layout']
    final = production['layout']
    growth = dict(code_bytes=final['code_bytes'] - baseline['code_bytes'],
                  data_bss_bytes=final['initialized_bytes'] + final['bss_bytes'] -
                                 baseline['initialized_bytes'] - baseline['bss_bytes'],
                  container_bytes=final['serialized_bytes_if_executable'] - baseline['serialized_bytes_if_executable'],
                  aligned_image_backing_bytes=final['heap_alignment_backing_bytes'] - baseline['heap_alignment_backing_bytes'])
    growth['metadata_bytes'] = growth['container_bytes'] - growth['code_bytes'] - (
        final['initialized_bytes'] - baseline['initialized_bytes'])
    prior_provider = read(ROOT / editing['executable']['path'] / 'layout.json')['resident_provider']
    provider_growth = {k: production['resident_provider'][k] - prior_provider[k]
                       for k in ('code_bytes', 'table_bytes', 'data_bss_bytes')}
    remaining = {k: editing['provider_remaining_allowances'][k] - provider_growth[k] for k in provider_growth}
    require(all(v >= 0 for v in remaining.values()), 'Provider allowance exceeded')
    private_remaining = dict(code_bytes=final['private_allowances']['code_bytes'] - max(0, growth['code_bytes']),
        data_bss_bytes=final['private_allowances']['data_bss_bytes'] - max(0, growth['data_bss_bytes']),
        metadata_bytes=final['container_metadata_allowance_bytes'] - max(0, growth['metadata_bytes']))
    require(all(v >= 0 for v in private_remaining.values()), 'Private growth allowance exceeded')
    data = dict(status='pass', tier='development', qualification=False, abi=ABI['version'],
                previous=previous, combined=stamp(combined / 'results.json'),
                persisted_media=stamp(combined / 'saving-gate-audit.json'), fresh_reads=fresh,
                production=stamp(layout / 'program.app'), layout=stamp(layout / 'layout.json'),
                baseline_audit=stamp(baseline_path),
                oracle_inputs=oracle_inputs,
                growth_from_QE7=growth,
                provider_growth_from_QE7=provider_growth, provider_remaining_allowances=remaining,
                private_growth_remaining_from_QE7=private_remaining,
                packages=[package(p.resolve()) for p in packages],
                scope='Current combined GUI plus QW1-QW7 scoped evidence, not a replay or expansion of historical claims',
                invalidated_images='QW7 transport images are isolated; reset-required cases do not claim normal hosted return or healthy media',
                unsupported=['power-loss atomicity', 'same-target concurrent mutation', 'autosave',
                             'broader metadata restoration', 'automatic repair/recovery scanning'])
    output.write_text(json.dumps(data, indent=2) + '\n')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--combined', type=Path, required=True)
    parser.add_argument('--reader', type=Path, action='append', required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--package', type=Path, action='append', default=[])
    args = parser.parse_args()
    audit(args.output, args.combined, args.reader, args.layout, args.package)
    print('Saving development evidence reconciled')
