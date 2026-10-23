#!/usr/bin/env python3
"""Reconcile the selected step 6 development cohorts without widening their scope."""
import argparse
import hashlib
import json
import statistics
import zipfile
from pathlib import Path

from filesystem_audit import Audit
from check_qed_baseline import provider_identity
from native_program import ROOT, require, read_build
from test_qed_coexist import DOCUMENT, LOAD


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stamp(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=digest(path))


def read(path):
    return json.loads(path.read_text())


def record(output, root, production, bundle, host):
    app = read(production/'app.json'); layout = read(production/'layout.json')
    sources = read(production/'inputs/sources.json')
    patches = {p.name: digest(p) for p in (ROOT/'ports/gem4xe/apps/qed/patches').glob('*.patch')}
    require(sources['patches'] == patches, 'Rebuild QED after changing patches')
    require(digest(production/'program.app') == app['sha256'], 'Changed production APP')
    frames = read(production/'stack-frames.json')
    require(frames['analysis_sha256'] == digest(production/'layout.json') and frames['margin_bytes'] >= 0,
            'Stale or over-budget source frame ledger')
    for name, sha in frames['listings'].items():
        require(digest(production/name) == sha, 'Changed emitted source listing: '+name)
    for name, sha in layout['build_inputs'].items():
        require(digest(Path(name)) == sha, 'Changed production build input: '+name)
    manifest = read(bundle/'demo-manifest.json')
    previous_native = read_build(ROOT/'build/qed-exec-altirra-fixed')
    current_native = read_build(bundle)
    require(provider_identity(read(bundle/'bitmap-console/c-image.json')) ==
            provider_identity(read(ROOT/'build/qed-exec-altirra-fixed/bitmap-console/c-image.json')),
            'Changed resident C provider identity')
    require(provider_identity(read(bundle/'bitmap-console/c-image.json')) ==
            provider_identity(read(Path(layout['resident_provider']['path']))),
            'Production APP and package providers differ')
    before_budget = previous_native['build']['memory']['bank_zero_budget']
    after_budget = current_native['build']['memory']['bank_zero_budget']
    require(after_budget == before_budget, 'Changed native bank-zero reservations')
    require(current_native['build']['memory']['task_capacity'] == 8, 'Changed Task capacity')
    for name, sha in manifest['source_inputs'].items():
        require(digest(ROOT/name) == sha, 'Changed package source input: '+name)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        sums = archive.read('exec816-demo/SHA256SUMS').decode().splitlines()
        require(set(archive.namelist()) == {'exec816-demo/SHA256SUMS'} |
                {'exec816-demo/'+line.split('  ', 1)[1] for line in sums}, 'Unexpected ZIP entries')
        for line in sums:
            sha, name = line.split('  ', 1)
            require(hashlib.sha256(archive.read('exec816-demo/'+name)).hexdigest() == sha,
                    'Changed packaged file: '+name)
    cohorts = {}
    for name, folder in [('baseline', 'qc1-caption'), ('peer', 'qc2-peer-caption'), ('checksum', 'qc2-checksum-caption')]:
        case = root/folder; result = read(case/'coexist-results.json'); session = result['integration']
        require(result['status'] == 'pass' and session['normal_collection'], 'Incomplete cohort: '+name)
        require(result['production_app_sha256'] == app['sha256'] and
                result['zip_sha256'] == digest(bundle/'exec816-demo.zip'), 'Unmatched cohort APP/ZIP: '+name)
        require(result['runtime']['status'] == 0 and result['runtime']['guards'] == 'intact', 'Runtime failure: '+name)
        require(249 <= result['autoboot_frames'] <= 251, 'Changed OF816 countdown')
        for file, sha in result['observer_inputs'].items():
            require(digest(ROOT/file) == sha, 'Changed cohort observer: '+file)
        rows = session['qed_editing'][0]['timings']; groups = {}
        require(len(rows) == 15 and all(v['elapsed_ms'] <= v['limit_ms'] for v in rows), 'Missing/failed response gate')
        for kind in ('insert', 'navigate', 'find'):
            values = [v['elapsed_ms'] for v in rows if v['name'].startswith(kind)]
            groups[kind] = dict(samples=len(values), median_ms=statistics.median(values), maximum_ms=max(values))
        for field in ('free_bytes', 'largest_bytes', 'free_extents'):
            require(session['initial_heap'][field] == session['final_heap'][field], 'Retained heap/fragmentation: '+name)
        disk = Audit((case/'work-walkthrough.atr').read_bytes()); allocation = disk.sdfs()
        require(disk.files['LOAD.BIN'] == LOAD, 'Checksum input was changed')
        if name == 'peer':
            require(disk.files['STOP.CMD'] == b'; delay\n'*8192+b'STOPQED\n', 'Stop dispatch script changed')
        first = [b'abcdef'+DOCUMENT.split(b'\n')[0], *DOCUMENT.split(b'\n')[1:]]
        final = list(first); final[32] = final[32][:13]+b'g'+final[32][13:]
        require(disk.files['SESSION.TXT'] == b'\n'.join(final) and
                disk.files['SESSION.BAK'] == b'\n'.join(first), 'Persisted document/backup changed')
        cohorts[name] = dict(result=stamp(case/'coexist-results.json'), trace=stamp(case/'emulator.log'),
            disk=stamp(case/'work-walkthrough.atr'), latency=groups, quit_ms=session['quit_ms'],
            load=session.get('load'), initial_heap=session['initial_heap'], final_heap=session['final_heap'],
            checkpoints=session['checkpoints'], allocation=allocation,
            runtime_status=result['runtime']['status'], guards=result['runtime']['guards'],
            machine=result['machine'], autoboot_frames=result['autoboot_frames'])
    warm = read(root/'qc2-peer-caption/desktop-warmup.json')
    require(warm['status'] == 'pass' and warm['iterations'] == 2 and warm['retained_upper_bytes'] == 368 and
            warm['warm_heaps'][0] == warm['warm_heaps'][1], 'Missing warm desktop ownership/reuse check')
    require(digest(ROOT/warm['observer']['path']) == warm['observer']['sha256'], 'Changed warm-up observer')
    require(cohorts['peer']['load']['collected'] and cohorts['peer']['load']['ninth_task_rejected'] and cohorts['peer']['load']['cooperative_stop_cancel'] and
            cohorts['peer']['load']['cover_expose'] and cohorts['peer']['load']['counter_label_pixels'] == 832,
            'Missing Counter/admission/Stop coverage')
    require(cohorts['checksum']['load']['form_progress'] and cohorts['checksum']['load']['collected'],
            'Missing checksum progress/collection')
    lifetime = root/'qc3-caption'; life = read(lifetime/'results.json')
    blink = root/'blink-caption'; idle = read(blink/'results.json')
    damage = root/'damage-caption'; policy = read(damage/'results.json')
    cache = root/'cache-caption'; cached = read(cache/'results.json')
    for path, result in [(lifetime, life), (blink, idle), (damage, policy), (cache, cached)]:
        require(result['status'] == 'pass' and result['runtime']['guards'] == 'intact' and result['runtime']['status'] == 0,
                'Incomplete focused gate: '+str(path))
        ledger = path/'inputs/sources.json' if path == damage else path/'app/inputs/sources.json'
        require(read(ledger)['patches'] == patches, 'Stale focused APP: '+str(path))
    require(life['completed'] == [4] and idle['completed'] == [4] and policy['completed'] == [2] and cached['completed'] == [4], 'Incomplete lifetimes')
    require(life['qed_editing'][0]['coexist_lifetime']['repeated_edits'] == 12 and
            life['qed_editing'][0]['coexist_lifetime']['navigation_keys'] == 64, 'Missing repeated-use/navigation gate')
    require(cached['qed_editing'][0]['cache_regressions']['old_eof_restored'] and
            cached['qed_editing'][0]['cache_regressions']['cover_expose'] and
            cached['qed_editing'][0]['cache_regressions']['edit_and_undo_invalidation'], 'Missing cache regressions')
    headroom = min(v['headroom'] for v in life['stacks']['minima'])
    require(headroom >= 128, 'Insufficient selected stack headroom')
    hidden = idle['qed_editing'][0]['hidden_carets']
    require(len(hidden) == 4 and all(v['blink'] == 1 and v['checked'] > 0 for v in hidden), 'Missing real hidden-caret pixels')
    require(idle['qed_editing'][0]['caret_draws']['outside_band'] == 0, 'Idle cursor repainted a row')
    text = host.read_text()
    require('Ran 552 tests' in text and 'OK (skipped=4)' in text, 'Incomplete host checks')
    r = dict(schema_version=1, status='pass', tier='development', qualification=False,
        scope='Strategy step 6 selected production coexistence, latency, lifetime and ownership gate; supported delivery/release remains step 7',
        production={name: stamp(production/file) for name, file in
            [('app','program.app'), ('layout','layout.json'), ('sources','inputs/sources.json'), ('frames','stack-frames.json')]},
        layout=layout['layout'], exec_image_backing_bytes=(layout['layout']['span_bytes']+65535+7)&~7,
        source_stack=dict(source_bytes=frames['source_chain_bytes'], margin_bytes=frames['margin_bytes'],
            continuation_cap_bytes=frames['continuation_cap_bytes'], admission_bytes=frames['admission_bytes']),
        package={name: stamp(bundle/file) for name, file in
            [('zip','exec816-demo.zip'), ('manifest','demo-manifest.json'), ('preview','qed-preview.json'),
             ('native_xex','program.xex'), ('boot_xex','of816/Exec-of816.xex'), ('rom','of816/altirraos-816.rom')]},
        local_preview=dict(refresh=stamp(root/'launcher-refresh.json'),
            prepare_only=stamp(root/'launcher-prepare-only.log'),
            scope='Existing launchers forward to the measured preview; private D8 settings reuse the existing writable disk through a symlink. No GUI emulator was launched.'),
        native_refresh=dict(before_xex=stamp(ROOT/'build/qed-exec-altirra-fixed/program.xex'),
            current_build=stamp(bundle/'build.json'), before_bank_zero=before_budget, after_bank_zero=after_budget,
            selector_source=stamp(ROOT/'lib/desktop/deskmenu.act'), resident_provider_identity_unchanged=True,
            focused_fixture_scope='Retained matched QED-source/C-ABI rendering and lifetime fixtures use their recorded native providers. The refreshed desktop selector and transport are exercised by all three new normal-package cohorts.'),
        preceding_attempts=dict(
            checksum=stamp(ROOT/'build/qed-coexist-qc2-checksum-native.log'),
            checksum_trace=stamp(root/'qc2-checksum-native/emulator.log'),
            baseline=stamp(ROOT/'build/qed-coexist-qc1-native.log'),
            counter=stamp(ROOT/'build/qed-coexist-qc2-peer-native.log'),
            scope='The refreshed selector completed the Counter workflow. These baseline/Counter attempts then failed report finalization because the observer omitted boot-smoke.png. The checksum attempt failed navigation at 1002.8 ms. The current observer saves the required scanout; patch 0026 paints content before caption RPCs. None of these preceding attempts counts as a passing cohort.'),
        cache=dict(result=stamp(cache/'results.json'), trace=stamp(cache/'emulator.log'),
            scope=cached['qed_editing'][0]['cache_regressions'], lifetimes=4),
        cohorts=cohorts, desktop_warmup=dict(result=stamp(root/'qc2-peer-caption/desktop-warmup.json'),
            cold_free_bytes=warm['cold_heap']['free_bytes'], warm_free_bytes=warm['warm_heaps'][0]['free_bytes'],
            retained_upper_bytes=368, accumulating_bytes=0, timer_backing_bytes=112, path_backing_bytes=256),
        lifetime=dict(result=stamp(lifetime/'results.json'), trace=stamp(lifetime/'emulator.log'),
            scope=life['qed_editing'][0]['coexist_lifetime'],
            private_peak_requested_backing_bytes=max(v['private_heap'][3] for scene in life['qed_editing'] for v in scene['snapshots']),
            private_stats_scope='QED allocator payload plus its headers, before native heap rounding; actual rounded system occupancy is covered by native free extents.',
            minimum_sampled_system_free_bytes=min(v['free_bytes'] for scene in life['qed_editing'] for v in scene.get('heap', [])),
            minimum_selected_headroom_bytes=headroom,
            stack_scope='Selected PCs in the first large-document lifetime only; guards and functional collection in all four. '+life['stacks']['scope']),
        idle=dict(result=stamp(blink/'results.json'), trace=stamp(blink/'emulator.log'),
                  draws=idle['qed_editing'][0]['caret_draws'], real_hidden_caret_checks=4),
        damage=dict(result=stamp(damage/'results.json'), trace=stamp(damage/'emulator.log'), cases=16),
        stop_dispatch='Owning shell EXECUTE reads 65,544-byte STOP.CMD, then resolves a temporary alias to ordinary BREAK; QED is focused before the decision opens; alias removed after Cancel.',
        host=dict(result=stamp(host), tests=552, skipped=4),
        inputs={str(p.relative_to(ROOT)): digest(p) for p in
            [Path(__file__), ROOT/'tools/test_qed_coexist.py', ROOT/'tools/qed_coexist_observe.py',
             ROOT/'tools/qed_coexist_load.py', ROOT/'tools/test_qed_coexist_load.py',
             ROOT/'tools/qed_coexist_warm.py', ROOT/'tools/test_qed_cache.py',
             ROOT/'c/calypsi/aes-events.c', ROOT/'lib/dos/doscalls.act',
             ROOT/'tools/test_qed_coexist_lifetime.py', ROOT/'tools/test_qed_cursor.py',
             ROOT/'tools/qed_stack_observer.py', ROOT/'tools/test_c_process.py',
             ROOT/'tools/test_qed_selection.py', ROOT/'tests/test_qed_stack_capture.py',
             ROOT/'tests/programs/qed_damage_core.c', ROOT/'lib/exec/heap-system.inc']},
        bank_zero_delta=dict(fixed=0, per_public_task=0, private_idle=0,
            basis='Refreshed desktop selector; complete measured bank-zero budget equals the interactive cursor preview, including every Task/DP/stack/guard/alignment/slack reservation'),
        limits='Pinned ROM/emulator and 8x PAL configuration; sampled response and backing, first-lifetime selected stack tracing plus all-lifetime guards. No worst-case or hosted/release qualification claim.')
    output.write_text(json.dumps(r, indent=2)+'\n')
    return r


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'docs/development/qed-coexistence-qc4.json')
    p.add_argument('--root', type=Path, default=ROOT/'build/qed-coexist')
    p.add_argument('--production', type=Path, default=ROOT/'build/qed-coexist/caption-production')
    p.add_argument('--bundle', type=Path, default=ROOT/'build/qed-coexist/caption-preview')
    p.add_argument('--host', type=Path, default=ROOT/'build/qed-coexist-caption-final-host.log')
    a = p.parse_args(); record(a.output.resolve(), a.root.resolve(), a.production.resolve(), a.bundle.resolve(), a.host.resolve())
    print('QED coexistence development gate reconciled')
