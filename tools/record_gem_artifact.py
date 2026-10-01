#!/usr/bin/env python3
"""Freeze G6 artifact, package and standard OF816 development evidence."""
import hashlib
import json
from pathlib import Path
import zipfile
from native_program import ROOT, require, sha256
from package_demo import GEM_FILES


def record():
    base=ROOT/'build/gem-vdi'
    demo=base/'g6-demo'
    runs={}
    for mode,folder in [('raw',base/'g6-production-raw'),('opt',demo/'gem-vdi')]:
        r=json.loads((folder/'results.json').read_text())
        require(r['status']=='pass' and r['production'],'Incomplete production run')
        require(len(r['cases'])==1 and r['cases'][0]['scanout_sha256'],'No artifact pixel check')
        require(r['harness_sha256']==sha256(ROOT/'tools/test_gem_concurrent.py'),'Changed observer')
        require(r['xex_sha256']==sha256(folder/'program/program.xex'),'Changed tested image')
        c=json.loads((folder/'c-image.json').read_text())
        require(c['provenance']['diagnostic'] is False,'Diagnostic artifact')
        for path,digest in {**c['provenance']['source_inputs'],**r['build']['platform_inputs'],**r['build']['task_inputs']}.items():
            # Documentation moves cannot alter emitted code. Preserve the old
            # provenance verbatim and audit every actual target/build input.
            require(path.endswith('.md') or sha256(ROOT/path)==digest,'Changed source: '+path)
        r['provenance']=c['provenance']
        runs[mode]=r
    require(runs['raw']['cases'][0]['scanout_sha256']==runs['opt']['cases'][0]['scanout_sha256'],'Cross-mode pixels differ')
    artifact=json.loads((demo/'gem-vdi/graphics.json').read_text())
    require(artifact['files']['Exec-gem-vdi.xex']==runs['opt']['xex_sha256'],'Untested packaged graphics')
    boot=json.loads((demo/'of816/of816.json').read_text())
    require(boot['media']['manifest_sha256']==sha256(demo/'demo-manifest.json'),'Stale OF816 companion manifest')
    autoboot=json.loads((demo/'of816-results.json').read_text())
    shell=json.loads((demo/'of816/results.json').read_text())
    require(autoboot['status']==shell['status']=='pass','Incomplete OF816 checks')
    require(autoboot['boot_sha256']==sha256(demo/'of816/Exec-of816.xex'),'Untested standard boot')
    archive=demo/'exec816-demo.zip'
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'ZIP CRC failed')
        files={name.removeprefix('exec816-demo/'):z.read(name) for name in z.namelist()}
    expected={'Exec-of816.xex','system.atr','altirraos-816.rom','ALTIRRAOS-LICENSE.txt',
        'OF816-LICENSE.txt','EXEC816-GPL-3.0.txt','EXEC816-MIT.txt','EXEC816-LICENSING.md','README.txt','SHA256SUMS'}
    expected.update('gem-vdi/'+name for name in GEM_FILES)
    require(set(files)==expected,'Unexpected distribution members')
    hashes=dict(line.split('  ',1)[::-1] for line in files['SHA256SUMS'].decode().splitlines())
    require(set(hashes)==expected-{'SHA256SUMS'},'Incomplete checksums')
    for name,digest in hashes.items(): require(hashlib.sha256(files[name]).hexdigest()==digest,'ZIP digest mismatch: '+name)
    require(hashes['Exec-of816.xex']==boot['xex_sha256'] and hashes['system.atr']==boot['media']['sha256'] and
        hashes['altirraos-816.rom']==boot['rom']['sha256'],'Mismatched standard boot files')
    for name,digest in artifact['files'].items(): require(hashes['gem-vdi/'+name]==digest,'Mismatched graphics '+name)
    host=base/'g6-host.log'
    require('Ran 274 tests' in host.read_text() and 'OK (skipped=4)' in host.read_text(),'Host checks incomplete')
    prerequisites={name:sha256(ROOT/'docs/development'/name) for name in
        ['gem-vdi.json',*[f'gem-vdi-g{i}.json' for i in range(1,6)]]}
    for name in prerequisites:
        require(json.loads((ROOT/'docs/development'/name).read_text())['status']=='pass','Incomplete prerequisite '+name)
    # G6 changes the optional client's visible hold and packaging, not the G5
    # service, renderer, gateway, scheduler, SIO or display implementation.
    g5=json.loads((ROOT/'docs/development/gem-vdi-g5.json').read_text())
    for path,digest in g5['source_inputs'].items():
        if path.startswith(('ports/','c/','platform/','lib/','task-kernel/')) and not path.endswith('.md'):
            require(sha256(ROOT/path)==digest,'Changed G5 implementation: '+path)
    source_paths=['tools/build_demo.py','tools/build_gem_artifact.py','tools/package_demo.py',
        'tools/record_gem_artifact.py','tools/test_gem_concurrent.py','tests/test_demo_package.py',
        'tests/programs/gem_concurrent.c','docs/gem-vdi-distribution.txt',
        'docs/reference/gem-vdi.md','docs/guides/gem-vdi.md','docs/history/gem-vdi.md']
    record=dict(format='exec816-gem-vdi-g6-development-v1',status='pass',tier='development',
        date='2026-10-02',base_revision='416e9a9',qualification=False,
        scope='Explicit optional graphics artifact plus unchanged standard OF816 shell/prime boot behavior.',
        bank_zero=dict(fixed_delta_bytes=0,per_public_task_delta_bytes=[0]*8,private_idle_delta_bytes=0),
        visible_hold_frames=150,runs=runs,autoboot=autoboot,standard_shell=shell,
        prerequisites=prerequisites,source_inputs={p:sha256(ROOT/p) for p in source_paths},
        distribution=dict(path='build/gem-vdi/g6-demo/exec816-demo.zip',sha256=sha256(archive),
            bytes=archive.stat().st_size,members=hashes,crc='pass',
            excluded='Maps, manifests, listings, source intermediates and test output'),
        host_checks=dict(tests=274,skipped=4,log_sha256=sha256(host)),
        limitations=['Pinned emulator and executed development paths only; no full hosted/physical-hardware qualification.',
            'Optional artifact exercises text/concurrency. G4 remains the broader mixed-primitive corpus.',
            'No AES, desktop, input, GEMDOS, virtual workstations or multiple GUI clients.'])
    path=ROOT/'docs/development/gem-vdi-g6.json'
    path.write_text(json.dumps(record,indent=2)+'\n')
    print(path)

if __name__=='__main__': record()
