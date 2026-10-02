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
        runner = ROOT/{'G5': 'tools/test_gem_concurrent.py',
                       'I1': 'tools/test_input.py'}[report['slice']]
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


def host_checks(host):
    log = host.read_text()
    match = re.search(r'Ran (\d+) tests', log)
    require(match and re.search(r'\nOK(?: \(skipped=\d+\))?\s*$', log), 'Host checks failed')
    return dict(tests=int(match[1]), log_sha256=sha256(host))


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
        host_checks=host_checks(host),
        limitations=['Focused development evidence on the pinned emulator, not full qualification.',
                     'Keyboard interaction and cursor remain later slices; no mouse or AES claim.'])


def record_i1(base, host):
    from generate_input import ABI, expected_layout, files
    for path, content in files().items():
        require(path.read_text() == content, 'Stale generated input ABI')
    runs = {mode: read_run(base/('i1-'+mode)) for mode in ('raw', 'opt')}
    for mode, run in runs.items():
        require(run['mode'] == mode and [c['name'] for c in run['cases']] == ['abi'],
                'Missing input ABI probe')
        require(all(run['layout'][label] == value for label, value in expected_layout()),
                'Emitted input layout mismatch')
        require(run['cases'][0]['c_context'] and run['cases'][0]['failures'] == 0,
                'Missing guarded C context')
        require(run['bank_zero_delta'] == dict(fixed=0, per_task=[0]*8, private_idle=0),
                'Unexpected bank-zero reservation')
    paths = ['abi/input.json', 'abi/tasks.json', 'tools/record_input_slice.py',
             'tools/library_paths.py', 'tests/test_input_abi.py', 'LICENSING.md']
    return dict(format='exec816-gem-input-i1-development-v1', status='pass', tier='development',
        qualification=False, base_revision=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Generated input records and checked C/native marshalling; no hardware admission.',
        abi=ABI, runs=runs, host_checks=host_checks(host),
        bank_zero=dict(fixed_delta_bytes=0, per_public_task_delta_bytes=[0]*8,
                       private_idle_delta_bytes=0,
                       accounting='Complete reservations include guards, alignment and unused capacity.'),
        upper_ram=dict(c_entry_table_bytes=24, lease_bytes=32, config_bytes=16, event_bytes=24,
                       reserved_c_banks=[12, 13], reserved_c_bytes=131072,
                       reserved_c_delta_bytes=0, heap_lifetime_delta_bytes=0),
        source_inputs={p: sha256(ROOT/p) for p in paths},
        limitations=['Acquire and all other runtime operations explicitly return UNSUPPORTED until I3.',
                     'No keyboard, physical pointer, AES or hosted qualification claim.'])


def read_native_run(folder, runner):
    """Audit native-only and mixed C reports using their actual build paths."""
    folder = Path(folder).resolve()
    report = json.loads((folder/'results.json').read_text())
    require(report['status'] == 'pass', 'Failed/incomplete run: '+str(folder))
    if 'cases' in report:
        require(report['cases'] and all(c['status'] == 'pass' for c in report['cases']),
                'Missing or failed native cases')
    build = report['build']
    inputs = {}
    for key in ('platform_inputs', 'task_inputs', 'banked_inputs', 'console_inputs',
                'console_fixture_inputs'):
        inputs.update(build.get(key, {}))
    inputs.update(build.get('foreign_image', {}).get('source_inputs', {}))
    for path, digest in inputs.items():
        require(sha256(ROOT/path) == digest, 'Stale source: '+path)
    candidates = [ROOT/p for p in subprocess.check_output(
        ['rg', '--files', '-g', build['source']], cwd=ROOT, text=True).splitlines()]
    if 'foreign_image' in build:
        # C builders emit their native launcher beside the frozen C image.
        candidates.append(folder/build['source'])
    require(any(p.exists() and sha256(p) == build['source_sha256'] for p in candidates),
            'Changed native fixture: '+build['source'])
    digest = sha256(ROOT/runner)
    require(report.get('harness_sha256', digest) == digest, 'Stale native observer')
    xex = folder/'program/program.xex'
    if not xex.exists():
        xex = folder/'program.xex'
    require(sha256(xex) == build['xex_sha256'], 'Changed tested native XEX')
    require(report.get('xex_sha256', build['xex_sha256']) == build['xex_sha256'],
            'Mismatched native XEX')
    report.update(evidence_path=str(folder.relative_to(ROOT)),
                  evidence_sha256=sha256(folder/'results.json'),
                  observer=dict(path=runner, sha256=digest))
    return report


def record_i2(base, host):
    from test_producer_lifetime import CASES
    specs = {'producer': 'test_producer_lifetime', 'task': 'test_task_lifetime',
             'sio': 'test_sio_lifetime', 'create': 'test_create_task',
             'calypsi': 'test_calypsi', 'console-life': 'test_console_lifetime',
             'console-nmi': 'test_console_input'}
    runs = {}
    for mode in ('raw', 'opt'):
        for name, runner in specs.items():
            key = name+'-'+mode
            runs[key] = read_native_run(base/('i2-'+key), 'tools/'+runner+'.py')
        for order in (0, 1):
            key = 'console-'+mode+'-'+str(order)
            runs[key] = read_native_run(base/('i2-'+key), 'tools/test_console_input.py')
        require(len(runs['producer-'+mode]['cases']) == 2*len(CASES)+1,
                'Missing producer admission cases')
        require(runs['console-nmi-'+mode]['input_observations']['post_nmi_checkpoints'] > 0,
                'Missing asynchronous publication checkpoints')
    abi = json.loads((ROOT/'abi/tasks.json').read_text())
    require(abi['raw']['profile_tag']['value'] == 7, 'Wrong producer profile')
    return dict(format='exec816-gem-input-i2-development-v1', status='pass',
        tier='development', qualification=False,
        base_revision=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        scope='Source-qualified serial/keyboard admission, signal and Task retention, retirement.',
        profile_tag=7, producer_packet=abi['producer_packet'], producer_imports=abi['producer_imports'],
        runs=runs, host_checks=host_checks(host),
        bank_zero=dict(fixed_delta_bytes=0, per_public_task_delta_bytes=[0]*8,
                       private_idle_delta_bytes=0,
                       accounting='Complete reservations include guards, alignment and unused capacity.'),
        upper_ram=dict(binding_bytes_per_source=12, binding_storage_delta_bytes=0,
                       native_code_reservation_delta_bytes=0),
        source_inputs={'tools/record_input_slice.py': sha256(Path(__file__))},
        limitations=['Focused development checks, not hosted qualification.',
            'No reusable input acquisition, interactive application, mouse or AES claim.',
            'Task/SIO legacy runners record their actual paced binary separately from the older signal pin.',
            'Console physical wire tests use the unchanged pinned console emulator and its FASTEST125 control.'])


def record_i3(base, host):
    specs = {'abi': 'test_input', 'capture': 'test_input_capture',
             'focus': 'test_console_focus', 'break': 'test_foreground_break',
             'life': 'test_console_lifetime', 'console-emu': 'test_console_input'}
    runs = {}
    baseline = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
    for mode in ('raw', 'opt'):
        for name, runner in specs.items():
            key = name+'-'+mode
            runs[key] = read_native_run(base/('i3-'+key), 'tools/'+runner+'.py')
        for order in (0, 1):
            key = 'console-'+mode+'-'+str(order)
            runs[key] = read_native_run(base/('i3-'+key), 'tools/test_console_input.py')
        require(runs['capture-'+mode]['cases'][0]['checks'][0] >= 217,
                'Missing input lifetime checks')
        require(runs['break-'+mode]['publication']['nmi_after'] >
                runs['break-'+mode]['publication']['nmi_before'], 'No split-publication NMI')
    for name in ('console-full-raw', 'console-loss-opt'):
        runs[name] = read_native_run(base/('i3-'+name), 'tools/test_console_input.py')
    runs['quota-raw'] = read_native_run(base/'i3-quota-raw','tools/test_console_focus.py')
    require(runs['quota-raw']['quota_probe'] and runs['quota-raw']['quota_drains']>0,
            'Missing empty-notification/nonempty-queue check')
    for run in runs.values():
        memory = run['build']['memory']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key] == baseline[key], 'Input changed '+key)
    return dict(format='exec816-gem-input-i3-development-v1',status='pass',tier='development',
        qualification=False,base_revision=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Exclusive reusable keyboard capture and console migration; native and emulation input.',
        runs=runs,host_checks=host_checks(host),
        bank_zero=dict(fixed_delta_bytes=0,per_public_task_delta_bytes=[0]*8,
                       private_idle_delta_bytes=0,
                       accounting='Complete reservations include guards, alignment and unused capacity.'),
        upper_ram=dict(capture_bytes=560,capture_delta_bytes=0,
                       generic_state_bytes=128,generic_state_reserved_delta_bytes=0,
                       state_location='Existing Task arena slack at +$A60; capture remains +$C00.',
                       console_image_state_delta_bytes=78,additional_tasks=0),
        source_inputs={'tools/record_input_slice.py':sha256(Path(__file__))},
        limitations=['Development checks on the recorded pins; not hosted qualification.',
                     'No physical mouse, cursor or AES support. GUI work remains I4 onward.',
                     'Console physical SIO controls use FASTEST125; interactive latency is measured separately in I6.'])


def record_i4(base, host):
    from test_gem_interactive import CASES
    from generate_gem_interactive import files, expected_layout
    for path, content in files().items():
        require(path.read_text() == content, 'Stale interactive ABI')
    runs = {}
    peaks = {}
    maps = {}
    for mode in ('raw', 'opt'):
        run = read_native_run(base/('i4-'+mode), 'tools/test_gem_interactive.py')
        require([c['name'] for c in run['cases']] == CASES, 'Missing I4 cases')
        require(all(run['layout'][expr] == value for expr, value in expected_layout()),
                'Unverified control-message/boot layout')
        for case in run['cases']:
            require(case['failures'] == 0, 'Target assertion failed')
            require(case['counters']['submitted'] == case['counters']['collected'], 'Uncollected packet')
            for slot, usage in case['stack_usage'].items():
                peaks[slot] = max(peaks.get(slot, 0), usage['peak'])
        keyboard = run['cases'][0]
        require(keyboard['scanout_sha256'] and keyboard['counters']['inputWhilePending'] > 0,
                'Missing keyboard/render overlap or pixel check')
        require(keyboard['counters']['maxCommands'] <= 4 and keyboard['counters']['maxGlyphs'] <= 8,
                'Unbounded interactive packet')
        image = json.loads((base/('i4-'+mode)/'c-image.json').read_text())
        maps[mode] = dict(segments=[dict(address=part['address'], bytes=len(part['bytes']),
                         executable=part['executable']) for part in image['segments']],
                         zero_fill=image['zero_fill'], symbols=image['symbols'],
                         compiler=image['provenance']['compiler_flags'],
                         link_sha256=sha256(base/('i4-'+mode)/'link.lst'))
        runs[mode] = run
        service = read_native_run(base/('i4-service-'+mode), 'tools/test_gem_service.py')
        require([c['name'] for c in service['cases']] == ['protocol'], 'Missing exact-collection check')
        runs['service-'+mode] = service
    return dict(format='exec816-gem-input-i4-development-v1', status='pass', tier='development',
        qualification=False, base_revision=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Two large Tasks, bounded keyboard scene, nonblocking exact collection and retained disk/exit handshake.',
        runs=runs, maps=maps, maximum_observed_stack_bytes=peaks, host_checks=host_checks(host),
        bank_zero=dict(fixed_delta_bytes=0,per_public_task_delta_bytes=[0]*8,private_idle_delta_bytes=0,
                       accounting='Complete reservations include guards, alignment and unused capacity.'),
        upper_ram=dict(reserved_c_banks=[12,13],reserved_c_bytes=131072,reserved_c_delta_bytes=0,
                       boot_descriptor_bytes=48,control_slots=4,control_bytes_per_slot=32,
                       embedded_ports=4,port_bytes=27,input_lease_bytes=32,input_config_bytes=16,
                       input_event_bytes=24,text_bytes=25,
                       note='Static records and alignment use existing C banks; maps record all linked storage.'),
        source_inputs={'tools/record_input_slice.py':sha256(Path(__file__))},
        limitations=['Development checks, not hosted qualification or a latency claim.',
                     'Cursor, normalized pointer input, deeper failure closure and artifact remain I5-I7.',
                     'No physical mouse or AES support.',
                     'Uncertain missing-drive timeout retains the offline SIO bus at FF93 after GUI retirement.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--slice', choices=['i0', 'i1', 'i2', 'i3', 'i4'], required=True)
    p.add_argument('--base', type=Path, default=ROOT/'build/gem-input')
    p.add_argument('--host-log', type=Path, required=True)
    args = p.parse_args()
    report = {'i0': record_i0, 'i1': record_i1, 'i2': record_i2, 'i3': record_i3, 'i4': record_i4}[args.slice](args.base.resolve(), args.host_log)
    output = ROOT/'docs/development'/('gem-input-'+args.slice+'.json')
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(output)
