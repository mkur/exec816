#!/usr/bin/env python3
"""Freeze fresh, passing development evidence for a hosted input slice."""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

from native_program import ROOT, require, sha256


def read_run(folder):
    folder = Path(folder).resolve()
    report = json.loads((folder/'results.json').read_text())
    require(report['status'] == 'pass', 'Failed/incomplete run: '+str(folder))
    require(report.get('cases') and all(c['status'] == 'pass' for c in report['cases']),
            'Missing or failed cases: '+str(folder))
    image = json.loads((folder/'c-image.json').read_text())
    inputs = {**image['provenance']['source_inputs'],
              **report['build']['platform_inputs'], **report['build']['task_inputs']}
    for path, digest in inputs.items():
        # The C extraction manifest also lists host observers. They do not
        # affect emitted code. Audit the observer used by this execution below;
        # G2 does not import or execute the concurrent graphics observer.
        if path == 'tools/test_gem_concurrent.py':
            continue
        require(sha256(ROOT/path) == digest, 'Stale source: '+path)
    if 'harness_sha256' in report:
        runner = ROOT/('tools/test_gem_concurrent.py' if report['slice'] == 'G5'
                       else 'tools/test_'+report['slice']+'.py')
        require(sha256(runner) == report['harness_sha256'], 'Stale observer')
    xex = folder/'program/program.xex'
    digest = sha256(xex)
    if 'xex_sha256' in report:
        require(digest == report['xex_sha256'], 'Changed tested XEX')
    report.update(provenance=image['provenance'], xex_sha256=digest,
                  evidence_path=str(folder.relative_to(ROOT)),
                  evidence_sha256=sha256(folder/'results.json'))
    return report


def distribution(folder, run):
    from package_demo import GEM_FILES
    folder = Path(folder).resolve()
    archive = folder/'exec816-demo.zip'
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'ZIP CRC failure')
        files = {n.removeprefix('exec816-demo/'): z.read(n) for n in z.namelist()}
    expected = {'Exec-of816.xex', 'system.atr', 'altirraos-816.rom',
                'ALTIRRAOS-LICENSE.txt', 'OF816-LICENSE.txt', 'EXEC816-GPL-3.0.txt',
                'EXEC816-MIT.txt', 'EXEC816-LICENSING.md', 'README.txt', 'SHA256SUMS'}
    expected.update('gem-vdi/'+name for name in GEM_FILES)
    require(set(files) == expected, 'Wrong ZIP members')
    hashes = dict(line.split('  ', 1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
    require(set(hashes) == expected-{'SHA256SUMS'}, 'Missing ZIP hashes')
    for name, digest in hashes.items():
        require(hashlib.sha256(files[name]).hexdigest() == digest, 'Wrong ZIP hash: '+name)
    require(run['production'] and len(run['cases']) == 1 and run['cases'][0]['scanout_sha256'],
            'Missing production pixel replay')
    require(hashes['gem-vdi/Exec-gem-vdi.xex'] == run['xex_sha256'], 'Untested packaged XEX')
    require(hashes['gem-vdi/graphics.atr'] == run['media_sha256'], 'Untested packaged disk')
    boot = json.loads((folder/'of816/of816.json').read_text())
    require(hashes['Exec-of816.xex'] == boot['xex_sha256'] and
            hashes['system.atr'] == boot['media']['sha256'] and
            hashes['altirraos-816.rom'] == boot['rom']['sha256'], 'Mismatched OF816 bundle')
    return dict(path=str(archive.relative_to(ROOT)), sha256=sha256(archive),
                bytes=archive.stat().st_size, members=hashes)


def record_i0(base, host):
    from test_gem_concurrent import CASES
    runs = {name: read_run(base/name) for name in
            ('i0-concurrent-raw', 'i0-concurrent-opt', 'i0-service-raw', 'i0-service-opt')}
    required = {'protocol', 'stop-queued', 'stop-active', 'worker-port', 'worker-scratch',
                'stop-port', 'stop-packet', 'admission', 'startup-signal', 'stop-exhausted'}
    for mode in ('raw', 'opt'):
        require([c['name'] for c in runs['i0-concurrent-'+mode]['cases']] == CASES,
                'Missing concurrent cases')
        require({c['name'] for c in runs['i0-service-'+mode]['cases']} >= required,
                'Missing lifecycle cases')
    production = read_run(base/'i0-demo/gem-vdi')
    package = distribution(base/'i0-demo', production)
    runs['production'] = production
    peaks = {}
    for run in runs.values():
        require(run['bank_zero_delta'] == dict(fixed=0, per_task=[0]*8, private_idle=0),
                'Unexpected memory reservation')
        for case in run['cases']:
            for slot, usage in case.get('stack_usage', {}).items():
                peaks[slot] = max(peaks.get(slot, 0), usage['peak'])
    maps = [(base/('i0-concurrent-'+mode)/'link.lst').read_text() for mode in ('raw', 'opt')]
    for text in maps:
        match = re.search(r"^server in section 'zhuge'.* of size ([0-9a-f]+)$", text, re.M)
        require(match and int(match[1], 16) == 84, 'Unmeasured server record')
    log = host.read_text()
    match = re.search(r'Ran (\d+) tests', log)
    require(match and re.search(r'\nOK(?: \(skipped=\d+\))?\s*$', log), 'Host checks failed')
    paths = ['tools/record_input_slice.py', 'tools/build_gem_artifact.py',
             'tools/package_demo.py', 'tests/test_demo_package.py',
             'docs/gem-vdi-distribution.txt']
    return dict(format='exec816-gem-input-i0-development-v1', status='pass', tier='development',
        qualification=False, base_revision=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Preallocated renderer stop, media-error text restoration and distinct graphics disk.',
        bank_zero=dict(fixed_delta_bytes=0, per_public_task_delta_bytes=[0]*8,
                       private_idle_delta_bytes=0,
                       accounting='Complete reservations include guards, alignment and unused capacity.'),
        upper_ram=dict(server_bytes=84, server_delta_bytes=4,
                       steady_heap_bytes=2656, stop_reserve_bytes=192,
                       heap_lifetime_delta_bytes=192, peak_heap_delta_bytes=0),
        maximum_observed_stack_bytes=peaks, runs=runs, distribution=package,
        source_inputs={p: sha256(ROOT/p) for p in paths},
        host_checks=dict(tests=int(match[1]), log_sha256=sha256(host)),
        limitations=['Focused development evidence on the pinned emulator, not full qualification.',
                     'Keyboard interaction and cursor remain later slices; no mouse or AES claim.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--slice', choices=['i0'], required=True)
    p.add_argument('--base', type=Path, default=ROOT/'build/gem-input')
    p.add_argument('--host-log', type=Path, required=True)
    args = p.parse_args()
    report = record_i0(args.base.resolve(), args.host_log)
    output = ROOT/'docs/development'/('gem-input-'+args.slice+'.json')
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(output)
