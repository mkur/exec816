#!/usr/bin/env python3
"""Add the current production QED to a verified native Exec desktop preview."""
import argparse
import configparser
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from c_program import ABI
from check_qed_baseline import provider_identity
from filesystem_audit import Audit
from launch_demo import PROFILES, set_values
from make_data_disk import make
from native_program import ROOT, require, sha256
from package_demo import QED_NOTICES

SAMPLE = b'QED running natively on Exec816.\nEdit this file, then save it on WORK:.\n'
PACKAGING_TOOLS = {'tools/build_demo.py', 'tools/package_demo.py'}


def read(path):
    return json.loads(path.read_text())


def launcher(output):
    """Start from a private, deterministic profile rather than user settings."""
    settings = configparser.ConfigParser(interpolation=None, delimiters=('=',))
    settings.optionxform = str
    set_values(settings, PROFILES, {'Defaults inited': 1, 'Current profile': 0})
    set_values(settings, PROFILES + r'\00000000', {
        'Input: Active map names': 'Mouse -> ST Mouse (port 1)',
        'Input: Quick map names': '', 'Devices': '[]',
        'CPU: Stop on BRK': 0, 'Debugger: Break on EXE run': 0,
        'Memory: Randomize on EXE load': 0,
    })
    with (output / 'launcher-seed.ini').open('w') as stream:
        settings.write(stream)
    path = output / 'launch-qed.command'
    path.write_text('#!/bin/sh\n'
        'demo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\n'
        'exec python3 ' + shlex.quote(str(ROOT / 'tools/launch_demo.py')) +
        ' --demo "$demo_dir" --config "$demo_dir/launcher-seed.ini" "$@"\n')
    path.chmod(0o755)


def prepare(output, base, qed):
    output, base, qed = output.resolve(), base.resolve(), qed.resolve()
    require(output != base and output != qed and output not in base.parents and
            base not in output.parents and qed not in output.parents, 'Choose a separate output directory')
    desktop = read(base / 'demo-manifest.json')
    require(desktop.get('gem_desktop') and desktop['filesystem'] == 'sdfs', 'Use the SDFS GEM desktop')
    changes = {}
    for name, digest in desktop['source_inputs'].items():
        actual = sha256(ROOT / name)
        if actual != digest:
            require(name in PACKAGING_TOOLS, 'Rebuild the desktop after changed input: ' + name)
            changes[name] = dict(before=digest, after=actual, scope='Packaging only; resident code unchanged')
    for name, digest in desktop['artifacts'].items():
        require(sha256(base / name) == digest, 'Changed base artifact: ' + name)
    layout = read(qed / 'layout.json')
    patches = {p.name: sha256(p) for p in (ROOT / 'ports/gem4xe/apps/qed/patches').glob('*.patch')}
    require(read(qed / 'inputs/sources.json')['patches'] == patches,
            'Rebuild QED after changing its ordered source patches')
    require(layout['status'] == 'executable-development' and layout['abi'] == ABI and
            not layout['image']['provenance']['analysis_only'], 'Use current executable QED')
    require(not any('/tests/programs/' in name for name in layout['build_inputs']), 'Do not package a QED fixture')
    for name, digest in layout['build_inputs'].items():
        require(sha256(Path(name)) == digest, 'Rebuild QED after changed input: ' + name)
    require(sha256(qed / 'program.app') == layout['app']['sha256'], 'Changed production QED')
    provider = read(base / 'bitmap-console/c-image.json')
    require(provider_identity(provider) == provider_identity(read(Path(layout['resident_provider']['path']))),
            'QED and desktop providers differ')
    # Keep saved writable media and private settings on refresh. Test output and
    # archives from the frozen source build do not belong in this new build.
    def ignore(directory, names):
        return [n for n in names if n in {'altirra', 'extracted', 'emulator.log', 'exec816-demo.zip'}
                or n.endswith('-results.json')]
    shutil.copytree(base, output, dirs_exist_ok=True, ignore=ignore)
    media = output / 'media'
    shutil.copyfile(qed / 'program.app', media / 'C/QED.APP')
    shutil.copyfile(qed / 'inputs/resource/QED.RSC', media / 'QED.RSC')
    sources = qed / 'inputs/source'
    notices = ('qed/gem4xe/NOTICE', 'qed/dist/liesmich.txt',
               'cflib/COPYING.LIB', 'qed/gem4xe/LICENSE-APACHE-2.0')
    for name, source in zip(QED_NOTICES, notices):
        shutil.copyfile(sources / source, output / name)
    pins = read(ROOT / 'ports/gem4xe/apps/qed/inputs.json')['sources']
    (output / 'QED-PROVENANCE.txt').write_text(
        'Native Exec816 QED development preview\n\n' +
        ''.join(p['id'] + ': ' + p['repository'] + '\nRevision: ' + p['revision'] + '\n' for p in pins) +
        '\nCurrent C APP ABI: ' + str(ABI['version']) + '\n' +
        'QED.APP SHA256: ' + layout['app']['sha256'] + '\n\n' +
        'Adaptations: native Exec Process/ABI and owned runtime; English resource,\n'
        'native input/dialogs, clipboard/Undo, canonical DOS paths, checked\n'
        'serialization/Close, backup/publication and recovery decisions.\n'
        'The donor GEM4XE startup/application kit is replaced by Exec bindings.\n'
        'The included upstream NOTICE describes the original GEM4XE binary.\n'
        'Retained/adapted CF-Lib and Calypsi C runtime keep their own terms.\n'
        'Source pins, ordered patches and native adapters are in the Exec816\n'
        'repository: ports/gem4xe/apps/qed/; see its inputs.json and README.md.\n'
        'QED and the port must not be distributed for a fee.\n')
    files = make(output / 'system.atr', media,
        binary_names={p.relative_to(media).as_posix() for p in media.rglob('*') if p.is_file()},
        filesystem='sdfs', sector_bytes=256, sectors=desktop['system_sectors'], label='SYS')
    desktop['files'] = {name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                 **(dict(lines=data.count(b'\n'), words=len(data.split()))
                                    if name.endswith('.TXT') else {}))
                        for name, data in files.items()}
    workspace = output / 'workspace-source'
    (workspace / 'SAMPLE.TXT').write_bytes(SAMPLE)
    make(output / 'work.atr', workspace, filesystem='sdfs', sector_bytes=256, sectors=2880, label='WORK')
    desktop['additional_media'][0]['sha256'] = sha256(output / 'work.atr')
    desktop['artifacts'].update({name: sha256(output / name) for name in
        ('system.atr', 'system.verification.json', 'work.atr', *QED_NOTICES)})
    desktop['qed_preview'] = dict(abi=ABI['version'], app_sha256=layout['app']['sha256'],
        production_layout=str(qed / 'layout.json'), production_layout_sha256=sha256(qed / 'layout.json'),
        base_manifest=str(base / 'demo-manifest.json'), base_manifest_sha256=sha256(base / 'demo-manifest.json'),
        host_tool_changes=changes, scope='User-requested local preview; strategy steps 6/7 and release qualification remain open')
    desktop['source_inputs'].update({str(p.relative_to(ROOT)): sha256(p) for p in
        (Path(__file__), ROOT / 'tools/build_demo.py', ROOT / 'tools/package_demo.py',
         ROOT / 'docs/qed-exec-distribution.txt')})
    (output / 'demo-manifest.json').write_text(json.dumps(desktop, indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/build_demo.py'), '--output', str(output),
                    '--refresh-monitor'], check=True)
    launcher(output)
    system = Audit((output / 'system.atr').read_bytes()); system_allocation = system.sdfs()
    work = Audit((output / 'work.atr').read_bytes()); work_allocation = work.sdfs()
    require(system.files['C/QED.APP'] == (qed / 'program.app').read_bytes() and
            system.files['QED.RSC'] == (qed / 'inputs/resource/QED.RSC').read_bytes() and
            work.files['SAMPLE.TXT'] == SAMPLE, 'Packaged QED/resource/sample differs')
    report = dict(status='pass', tier='development', qualification=False,
        native_payload_unchanged=sha256(output / 'program.xex') == sha256(base / 'program.xex'),
        production_app_sha256=sha256(qed / 'program.app'), abi=ABI['version'],
        zip_sha256=sha256(output / 'exec816-demo.zip'),
        system_allocation=system_allocation, work_allocation=work_allocation,
        bank_zero_delta=dict(fixed=0, per_public_task=0, private_idle=0))
    (output / 'qed-preview.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/qed-coexist/preview')
    parser.add_argument('--demo-from', type=Path, default=ROOT / 'build/qed-saving/qw1-gem')
    parser.add_argument('--qed-from', type=Path, default=ROOT / 'build/qed-coexist/production-final')
    args = parser.parse_args()
    prepare(args.output, args.demo_from, args.qed_from)
    print('Launch: ' + str(args.output / 'launch-qed.command'))
