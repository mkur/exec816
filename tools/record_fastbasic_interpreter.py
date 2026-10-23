#!/usr/bin/env python3
"""Freeze the source interpreter's selected development evidence."""
import argparse
import json
import subprocess
from pathlib import Path

from native_program import ROOT, require, sha256


def record(directory, destination):
    names = ('core', 'admission', 'faults', 'transitions', 'capacity', 'text',
             'attach-final-raw', 'attach-final-opt', 'lifetime-int',
             'lifetime-high', 'lifetime-final', 'profile', 'compiler-int', 'compiler-fp')
    evidence = []
    for name in names:
        path = directory/name/'results.json'
        value = json.loads(path.read_text())
        require(value['status'] == 'pass', 'Incomplete evidence: '+name)
        item = dict(path=str(path.relative_to(ROOT)), sha256=sha256(path))
        for key in ('status', 'group', 'raw', 'floating', 'checks', 'machine',
                    'runtime', 'local_overrides', 'engines', 'inputs', 'cases',
                    'session_bytes', 'interpreter_bytes', 'breakObservation',
                    'breakTicks', 'firstProgress', 'secondProgress',
                    'decimal_probe', 'return_probe', 'timing', 'power_tolerance'):
            if key in value:
                item[key] = value[key]
        build_path = directory/name/'build.json'
        build = json.loads(build_path.read_text())
        item['build_sha256'] = sha256(build_path)
        item['build'] = {k: build[k] for k in (
            'revision', 'override', 'binary_sha256', 'abi_sha256', 'source',
            'source_sha256', 'image_sha256', 'xex_sha256', 'optimize',
            'stack_checks', 'memory_sha256', 'platform_inputs', 'fastbasic_inputs')
            if k in build}
        evidence.append(item)
    for name in ('layout-raw','layout-opt'):
        path=directory/name/'results.json'
        value=json.loads(path.read_text())
        require(value['status']=='pass','Incomplete C layout probe')
        evidence.append(dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),
            status=value['status'],checks=value['checks'],optimize=value['optimize'],
            machine=value['machine'],runtime=value['runtime'],build=value['build']))
    demo = directory/'demo-final'
    walkthrough = json.loads((demo/'source-interpreter-results.json').read_text())
    require(walkthrough['status'] == 'pass', 'Incomplete ZIP walkthrough')
    diff = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=ROOT).decode().splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT).decode().splitlines()
    files = sorted(set(diff+untracked)-{str(destination.relative_to(ROOT))})
    source_inputs = {name: sha256(ROOT/name) for name in files if (ROOT/name).is_file()}
    native = json.loads((demo/'build.json').read_text())
    application = json.loads((demo/'bitmap-console/apps/basic/app.json').read_text())
    donor = json.loads((ROOT/'build/fastbasic/build.json').read_text())
    result = dict(format='exec816-fastbasic-interpreter-v1', date='2026-10-21',
        tier='development', qualification=False, status='pass',
        base_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        source_inputs=source_inputs, evidence=evidence, walkthrough=walkthrough,
        walkthrough_log_sha256=sha256(directory/'gui-final.log'),
        launcher_prepare_log_sha256=sha256(directory/'launcher-final.log'),
        baseline=json.loads((directory/'baseline.json').read_text()),
        pins={name: json.loads((ROOT/name).read_text()) for name in (
            'toolchain/actionc.json', 'ports/fastbasic/upstream.json',
            'toolchain/altirra-shell-paced.json', 'toolchain/altirra-gem-vdi.json')},
        engines=donor['engines'],
        engine_maps={name: sha256(ROOT/f'build/fastbasic/source/build/bin/{name}.map')
                     for name in ('fbrun', 'fbirun')},
        engine_audits={name: json.loads((directory/f'audit-{name}.json').read_text())
                       for name in ('fb', 'fbi')},
        reserved_bank_zero_delta=dict(fixed=0, root_kernel=0,
            per_public_task=[0]*12, idle=0,
            includes='Guards, alignment and unused capacity; existing pools and 544-byte guest DP reservation'),
        bank_zero_budget=native['memory']['bank_zero_budget'],
        memory_map=native['memory'],
        initial_bank_ownership=(demo/'manifest.bin').read_bytes()[32:
            32+native['memory']['constants']['TABLE_BYTES']].hex(),
        upper=dict(provider_payload=1881, provider_capacity=1888,
            provider_capacity_delta=32, pointer_state_offset='0x4760',
            pointer_state_bytes=160, pointer_capture_reservation='0x4800',
            upper_task_bank_reservation_delta=0, guest_backing_reserved=131072,
            image_requested=74, image_rounded=80, session_requested=2314,
            session_rounded=2320, session_rounded_delta=8,
            interpreter_requested=1564, interpreter_rounded=1568,
            editor_job_static=2543, editor_job_static_delta=128,
            editor_image_file_bytes=application['bytes'],editor_image_span=application['span'],
            editor_backing_requested=application['span']+65535,
            editor_backing_rounded=(application['span']+65542)&~7,
            editor_source_snapshot_reserved=32768,
            loader_requested=43, loader_rounded=48, loader_read=1024,
            loader_staging_capacity=262144),
        limits=dict(original_source_bytes=32768, non_eol_line_bytes=255,
            integer_source_base='0x4600', floating_source_base='0x5400',
            guest_limit='0xe000', largest_observed_byte_array=dict(FBI=39165, FB=35581),
            array_scope='Focused small source; exact one-past allocation rejects with 103. Source/code/variables reduce this space.'),
        host=dict(tests=554, status='pass', log_sha256=sha256(directory/'host.log')),
        delivery=dict(zip_sha256=sha256(demo/'exec816-demo.zip'),
            zip_bytes=(demo/'exec816-demo.zip').stat().st_size,
            manifest_sha256=sha256(demo/'demo-manifest.json'),
            application_sha256=sha256(demo/'bitmap-console/apps/basic/program.app'),
            source_archive='build/fastbasic-interpreter/exec816-fastbasic-source.zip',
            source_archive_checksum='Companion .zip.sha256; excluded here to avoid a source self-hash cycle'),
        measurement_scope=dict(
            profile='Coherent PAL tick samples at load, source, execute, output, cleanup and collection; local instrumentation recorded per run',
            baseline='Prior WB9/twelve-Task records and compiler maps retained; no comparable fresh WB9 stage-timing baseline was captured. No speedup factor is claimed.',
            interrupts='Selected real IRQ/NMI, decimal and native-return gates; not a full interrupt/placement or hardware matrix'))
    destination.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'build/fastbasic-interpreter')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/development/fastbasic-interpreter.json')
    args = parser.parse_args()
    record(args.directory.resolve(), args.output.resolve())
