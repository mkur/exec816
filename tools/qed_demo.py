"""QED staging shared by the ordinary demo builder and package refresh."""
import json
import shutil
from pathlib import Path

from c_program import ABI
from native_program import ROOT, require, sha256
from package_demo import QED_NOTICES
from qed_delivery import production, read, checked

SAMPLE = b'QED running natively on Exec816.\nEdit this file, then save it on WORK:.\n'


def guide(version, profile):
    from package_demo import pointer_description
    return (ROOT/'docs/qed-exec-distribution.txt').read_text().replace(
        '@VERSION@', version).replace('@SYSTEM_DISK@', 'system.atr').replace(
        '@POINTER_DESCRIPTION@', pointer_description(profile))


def stage(output, directory, provider):
    layout, identity = production(directory, provider)
    frames = read(directory/'stack-frames.json')
    require(frames['analysis_sha256'] == sha256(directory/'layout.json') and
            frames['status'] == 'conditional-source-bound' and frames['margin_bytes'] >= 0,
            'Stale or excessive QED source stack bound')
    shutil.copyfile(directory/'program.app', output/'media/C/QED.APP')
    shutil.copyfile(directory/'inputs/resource/QED.RSC', output/'media/QED.RSC')
    sources = directory/'inputs/source'
    for name, source in zip(QED_NOTICES, ('qed/gem4xe/NOTICE', 'qed/dist/liesmich.txt',
            'cflib/COPYING.LIB', 'qed/gem4xe/LICENSE-APACHE-2.0')):
        shutil.copyfile(sources/source, output/name)
    pins = read(ROOT/'ports/gem4xe/apps/qed/inputs.json')['sources']
    (output/'QED-PROVENANCE.txt').write_text(
        'Native Exec816 QED development delivery\n\n'+
        ''.join(p['id']+': '+p['repository']+'\nRevision: '+p['revision']+'\n' for p in pins)+
        '\nC APP ABI: '+str(ABI['version'])+'\nQED.APP SHA256: '+layout['app']['sha256']+'\n\n'+
        'Adaptations: Exec Process/ABI and owned runtime, English resource,\n'
        'input/dialogs, clipboard/Undo, native DOS paths, checked Save/Close,\n'
        'backup/publication, recovery decisions and bounded drawing.\n'
        'The donor startup/application kit is replaced by native Exec bindings.\n'
        'The upstream NOTICE describes the original GEM4XE binary.\n'
        'Source pins, ordered patches and adapters: ports/gem4xe/apps/qed/\n'
        'in https://github.com/mkur/exec816 (see LICENSING.md).\n'
        'QED and this port must not be distributed for a fee.\n'
        'CF-Lib and Calypsi runtime retain their file-specific terms.\n')
    return dict(abi=ABI['version'], app_sha256=layout['app']['sha256'],
        resource_sha256=sha256(directory/'inputs/resource/QED.RSC'), provider_identity=identity,
        production_layout=str(directory/'layout.json'), production_layout_sha256=sha256(directory/'layout.json'),
        frames_sha256=sha256(directory/'stack-frames.json'),
        scope='Development delivery candidate; full release qualification is separate')


def verify(record, output):
    entry = record['qed']
    directory = Path(entry['production_layout']).parent
    checked(directory/'layout.json', entry['production_layout_sha256'])
    checked(directory/'stack-frames.json', entry['frames_sha256'])
    layout, identity = production(directory, output/'bitmap-console/c-image.json')
    require(entry['abi'] == ABI['version'] and entry['provider_identity'] == identity and
            entry['app_sha256'] == layout['app']['sha256'], 'Changed QED manifest identity')
    checked(output/'media/C/QED.APP', entry['app_sha256'])
    checked(output/'media/QED.RSC', entry['resource_sha256'])
    checked(directory/'inputs/resource/QED.RSC', entry['resource_sha256'])

    # Refresh/package may reuse executable bytes only while their runtime inputs match.
    provider = read(output/'bitmap-console/c-image.json')
    for name, digest in provider['provenance']['source_inputs'].items():
        checked(ROOT/name, digest)
    native = read(output/'build.json')
    for group in ('platform_inputs', 'task_inputs', 'console_inputs', 'banked_inputs'):
        for name, digest in native.get(group, {}).items():
            checked(ROOT/name, digest)
