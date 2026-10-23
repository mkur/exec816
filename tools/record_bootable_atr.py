#!/usr/bin/env python3
"""Freeze the one-disk boot development evidence; no qualification claim."""
import argparse
from collections import Counter
import json
import re
import subprocess
from pathlib import Path
import zipfile

from native_program import ROOT, require, sha256


def record(directory, destination):
    demo = directory/'demo'
    evidence = {}
    selected = {
        'reader_large': directory/'reader-large-final/results.json',
        'reader_errors': directory/'reader-errors-visible/results.json',
        'disk_full': directory/'full/results.json',
        'read_only': directory/'readonly/results.json',
        'fujinet_boot_save': demo/'atr-fujinet-boot-results.json',
        'fujinet_manual_reboot': demo/'atr-fujinet-reboot-results.json',
    }
    boot = json.loads((demo/'boot-media/boot-atr.json').read_text())
    for name, path in selected.items():
        value = json.loads(path.read_text())
        require(value['status'] == 'pass', 'Incomplete evidence: '+name)
        summary = {key: value[key] for key in
                   ('cases', 'atr_boot', 'persisted', 'case', 'error',
                    'native_entry_replay', 'initial_media_sha256', 'media_sha256',
                    'boot_code_locator_and_protection')
                   if key in value}
        if 'runtime' in value:
            require(value['runtime']['guards'] == 'intact', 'Damaged native guards')
            summary['guards'] = 'intact'
            summary['machine'] = value['machine']
        if name.startswith('fujinet_'):
            require(value['atr_boot']['first_stage_rom_boot'], 'Not a cold disk boot')
            require(value['boot_xex_sha256'] in (None, boot['xex_sha256']), 'Changed boot XEX')
            relay = value['fujinet_pc']['relay']
            require(relay['error'] is None, 'FujiNet relay failed')
            summary['fujinet_pc'] = dict(
                binary=value['fujinet_pc']['binary'],
                sha256=value['fujinet_pc']['sha256'], scope=relay['scope'],
                commands=dict(Counter(str(c['command']) for c in relay['commands'])),
                bit_cycles=dict(Counter(str(c['bit_cycles']) for c in relay['commands'])))
        evidence[name] = dict(path=str(path.relative_to(ROOT)), sha256=sha256(path), summary=summary)
    saved = json.loads(selected['fujinet_boot_save'].read_text())
    restored = json.loads(selected['fujinet_manual_reboot'].read_text())
    require(saved['bundle_manifest_sha256']==sha256(demo/'demo-manifest.json'), 'Not the final package')
    require(saved['initial_media_sha256'] in (None, boot['image_sha256']), 'Not the final packaged ATR')
    if saved['initial_media_sha256'] is None:
        evidence['fujinet_boot_save']['summary']['initial_media_origin'] = (
            'Runner made a fresh byte-for-byte copy of the checksum-verified packaged ATR; generic runner field was unset for external SIO peer')
    require(restored['initial_media_sha256'] == saved['media_sha256'], 'Reboot did not retain saved disk')
    require(restored['persisted'], 'No persistence check')
    require(restored['boot_code_locator_and_protection']=='intact', 'Changed boot sectors/protection')
    host = (directory/'host-final.log').read_text()
    tests = re.search(r'Ran (\d+) tests', host)
    require(tests and host.rstrip().endswith('OK'), 'Host suite incomplete')
    native = json.loads((demo/'build.json').read_text())
    manifest = json.loads((demo/'demo-manifest.json').read_text())
    monitor = json.loads((demo/'of816/of816.json').read_text())
    snapshot = demo/'fuji-boot/before-native.altstate2'
    with zipfile.ZipFile(snapshot) as state:
        address = monitor['boot_config']['address']
        settings = state.read('memory.bin')[address:address+8]
    require(int.from_bytes(settings[4:6], 'little') == 128 and
            settings[6] == 1 and settings[7] & 1 == 0,
            'Manual Forth settings did not survive resumed loading')
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
    inputs = {name.decode(): sha256(ROOT/name.decode()) for name in names
              if name and (ROOT/name.decode()).is_file() and ROOT/name.decode() != destination}
    artifacts = {name: dict(bytes=(demo/name).stat().st_size, sha256=sha256(demo/name))
                 for name in ('exec816-demo.zip', 'of816/exec816.atr',
                              'of816/Exec-of816.xex', 'launch-altirra.command')}
    firmware_version = re.search(r'FujiNet v[^\r\n]+',
                                (demo/'fujinet-peer/firmware.log').read_text())[0]
    result = dict(format='exec816-bootable-system-atr-development-v1', date='2026-10-22',
        status='pass', tier='development', qualification=False, source_inputs=inputs,
        evidence=evidence, host=dict(tests=int(tests[1]), log_sha256=sha256(directory/'host-final.log')),
        build=dict(revision=native['revision'], override=native['override'],
                   compiler_sha256=native['binary_sha256'], optimize=native['optimize'],
                   native_build_sha256=sha256(demo/'build.json'),
                   manifest_sha256=sha256(demo/'demo-manifest.json'),
                   reuse='C applications/renderer reused only after input and product hash validation; native kernel and commands rebuilt optimized'),
        boot=boot, rom=monitor['rom'], emulator_pin=manifest['pin'],
        manual_handoff_settings=dict(snapshot_sha256=sha256(snapshot),
            bytes=settings.hex(), cache_blocks=128, system_drive=1, verbose=False),
        integration_emulator=dict(path='build/mouse-bridge/AltirraBridgeServer',
            sha256=sha256(ROOT/'build/mouse-bridge/AltirraBridgeServer'),
            configuration=manifest['configuration']),
        fujinet_configuration=dict(text=(demo/'fujinet-peer/fnconfig.ini').read_text(),
            raw_sio_device_sha256=sha256(demo/'fujinet-peer/peer.atdevice'),
            device=dict(tag='custom',hotreload=False,allowunsafe=True),
            firmware_log_sha256=sha256(demo/'fujinet-peer/firmware.log')),
        of816=monitor['of816'], artifacts=artifacts,
        reserved_bank_zero_delta=dict(fixed=0, root=0, kernel=0,
            per_public_task=[0]*12, idle=0, includes='Guards, alignment and unused capacity'),
        boot_phase_budget=boot['boot_phase_budget'],
        firmware_version=firmware_version,
        source_archive='build/bootable-atr/exec816-fastbasic-source.zip; companion checksum and source-rebuild/results.json recorded separately to avoid self-hash cycles',
        scope=dict(native='Optimized pinned compiler, no override; assembly reader emitted on pinned ROM/emulator',
            failures='Nine emitted reader failures plus full/read-only native-entry snapshot replays',
            transport='Real FujiNet-PC media/NetSIO, raw-SIO relay pauses emulation during host responses',
            direct='Earlier direct emulator cold boot/save/EXIT passed with same native XEX; final error display/readme covered by final FujiNet delivery and emitted reader cases',
            excluded=['Physical hardware and UART timing', 'Full release qualification',
                      'IDE power-on boot', 'Arbitrary DOS and cartridges']))
    destination.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'build/bootable-atr')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/development/bootable-system-atr.json')
    args = parser.parse_args()
    record(args.directory.resolve(), args.output.resolve())
