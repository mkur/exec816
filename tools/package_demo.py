#!/usr/bin/env python3
"""Create a small demo ZIP from an existing OF816 build."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LICENSE_FILES = {
    'EXEC816-GPL-3.0.txt': 'LICENSE',
    'EXEC816-MIT.txt': 'LICENSE-MIT',
    'EXEC816-LICENSING.md': 'LICENSING.md',
}

GEM_FILES = ('Exec-gem-vdi.xex', 'graphics.atr', 'README.txt', 'GEM-COPYING.txt',
             'GEM-COPYING.LIB.txt', 'GEM-LICENSING.md', 'GEM-FONT-NOTICE.txt')
BITMAP_FILES = ('Exec-bitmap-console.xex', 'system.atr', 'README.txt',
                'GEM-COPYING.txt', 'GEM-COPYING.LIB.txt', 'GEM-LICENSING.md',
                'GEM-FONT-NOTICE.txt')
GEM_NOTICES = BITMAP_FILES[3:]


def pointer_description(profile):
    return {
        'mild': 'The pointer uses mild acceleration: slow movement gives one screen pixel\n'
                'per ST step, and fast movement reaches up to four. The same curve applies\n'
                'while dragging. Moving back from an edge responds immediately.',
        'off': 'The pointer moves two screen pixels per ST mouse step, with fixed sensitivity\n'
               'and no acceleration. Moving back from an edge responds immediately.',
    }[profile]


def package(bundle, archive, graphics=None, bitmap=None, bitmap_shell=None):
    """Include only boot files and user documentation, checking recorded hashes."""
    record = json.loads((bundle/'of816.json').read_text())
    media = record['media']
    if not media:
        raise ValueError('The demo distribution requires a system disk')
    rom = record['rom']
    expected = {
        'Exec-of816.xex': record['xex_sha256'],
        media['name']: media['sha256'],
        rom['name']: rom['sha256'],
        rom['license']: rom['license_sha256'],
    }
    for item in record.get('additional_media', []):
        name = item['name']
        if name in expected or Path(name).name != name:
            raise ValueError('Invalid companion disk name')
        expected[name] = item['sha256']
    files = {}
    for name, digest in expected.items():
        if Path(name).name != name:
            raise ValueError('Distribution files must be bundle-local')
        content = (bundle/name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Changed demo artifact: {name}')
        files[name] = content
    files['OF816-LICENSE.txt'] = (bundle/'OF816-LICENSE.txt').read_bytes()
    for name, source in LICENSE_FILES.items():
        files[name] = (ROOT/source).read_bytes()
    guide = (ROOT/'docs/demo-distribution.txt').read_text()
    if bitmap_shell is not None:
        manifest = bitmap_shell/'demo-manifest.json'
        if hashlib.sha256(manifest.read_bytes()).hexdigest() != media['manifest_sha256']:
            raise ValueError('Changed bitmap shell manifest')
        demo = json.loads(manifest.read_text())
        if not demo.get('shell_only') or not demo.get('bitmap'):
            raise ValueError('Expected a shell-only bitmap build')
        if demo['artifacts']['program.xex'] != record['exec_xex_sha256']:
            raise ValueError('OF816 does not wrap this bitmap shell')
        for name in GEM_NOTICES:
            content = (bitmap_shell/name).read_bytes()
            if hashlib.sha256(content).hexdigest() != demo['artifacts'][name]:
                raise ValueError(f'Changed bitmap shell notice: {name}')
            files[name] = content
        guide = (ROOT/('docs/desktop-distribution.txt' if demo.get('desktop') else 'docs/bitmap-shell-distribution.txt')).read_text()
        if demo.get('desktop'):
            guide = guide.replace('@POINTER_DESCRIPTION@', pointer_description(demo['kernel']['desktop_mouse']['profile']))
    guide = guide.replace('@SYSTEM_DISK@', media['name'])
    guide = guide.replace('@SYSTEM_DRIVE@', str(record['boot_config']['system_drive']))
    if graphics is not None:
        record = json.loads((graphics/'graphics.json').read_text())
        if record.get('diagnostic') is not False or set(record['files']) != set(GEM_FILES):
            raise ValueError('Incomplete or diagnostic graphics artifact')
        for name in GEM_FILES:
            content = (graphics/name).read_bytes()
            if hashlib.sha256(content).hexdigest() != record['files'][name]:
                raise ValueError(f'Changed graphics artifact: {name}')
            files['gem-vdi/'+name] = content
        guide += '\nOptional graphics: see gem-vdi/README.txt. The default OF816 boot is unchanged.\n'
    if bitmap is not None:
        record = json.loads((bitmap/'bitmap.json').read_text())
        if record.get('diagnostic') is not False or set(record['files']) != set(BITMAP_FILES):
            raise ValueError('Incomplete or diagnostic bitmap artifact')
        for name in BITMAP_FILES:
            content = (bitmap/name).read_bytes()
            if hashlib.sha256(content).hexdigest() != record['files'][name]:
                raise ValueError(f'Changed bitmap artifact: {name}')
            files['bitmap-console/'+name] = content
        guide += '\nOptional bitmap shell preview: see bitmap-console/README.txt.\n'
    files['README.txt'] = guide.encode('utf-8')
    files['SHA256SUMS'] = ''.join(
        f'{hashlib.sha256(content).hexdigest()}  {name}\n'
        for name, content in sorted(files.items())).encode('ascii')
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Explicit members keep listings, logs and other build output out of the ZIP.
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for name, content in sorted(files.items()):
            member = zipfile.ZipInfo(f'exec816-demo/{name}')
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            output.writestr(member, content)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT/'build/demo/of816')
    parser.add_argument('--output', type=Path, default=ROOT/'build/demo/exec816-demo.zip')
    parser.add_argument('--gem-vdi', type=Path, help='Optional graphics build directory')
    parser.add_argument('--bitmap-console', type=Path, help='Optional bitmap shell build directory')
    args = parser.parse_args()
    print('Demo distribution:', package(args.bundle, args.output, args.gem_vdi, args.bitmap_console))
