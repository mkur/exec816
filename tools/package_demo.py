#!/usr/bin/env python3
"""Create a small demo ZIP from an existing OF816 build."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(bundle, archive):
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
    files = {}
    for name, digest in expected.items():
        if Path(name).name != name:
            raise ValueError('Distribution files must be bundle-local')
        content = (bundle/name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Changed demo artifact: {name}')
        files[name] = content
    files['OF816-LICENSE.txt'] = (bundle/'OF816-LICENSE.txt').read_bytes()
    guide = (ROOT/'docs/demo-distribution.txt').read_text()
    guide = guide.replace('@SYSTEM_DISK@', media['name'])
    guide = guide.replace('@SYSTEM_DRIVE@', str(record['boot_config']['system_drive']))
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
    args = parser.parse_args()
    print('Demo distribution:', package(args.bundle, args.output))
