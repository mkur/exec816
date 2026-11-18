#!/usr/bin/env python3
"""Check and prepare the original-source MGEDIT and EDITOBJC inputs."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, command, require, sha256


PORT = ROOT / 'ports/magic/mgedit'
APP_SOURCE = Path('magic/apps/mgedit/src')


def prepare(output, native=False):
    pin = json.loads((PORT / 'inputs.json').read_text())
    reference = json.loads((ROOT / 'toolchain/atari-st-reference.json').read_text())['magic']
    require(pin['revision'] == reference['revision'] and pin['repository'] == reference['repository'],
            'MGEDIT selection does not match the MagiC reference')
    licence = PORT / pin['license']['file']
    require(sha256(licence) == pin['license']['sha256'] == reference['license']['sha256'],
            'Changed original MagiC licence')
    output = Path(output).resolve()
    for name, digest in pin['files'].items():
        source = PORT / 'upstream' / name
        require(sha256(source) == digest, 'Changed original MGEDIT input: ' + name)
        target = output / name.lower()
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in ('.C', '.H', '.S', '.PRJ', '.TXT'):
            content = source.read_text(encoding='latin-1')
            target.write_text(content if content.endswith('\n') else content + '\n', encoding='utf-8')
        else:
            target.write_bytes(source.read_bytes())
    record = dict(pin)
    if native:
        patch = PORT / 'native.patch'
        command(['patch', '-p1', '-F', '0', '-t', '-i', patch], cwd=output / APP_SOURCE)
        record['native_patch_sha256'] = sha256(patch)
    (output / 'sources.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--native', action='store_true', help='Apply the named-document port')
    args = parser.parse_args()
    prepare(args.output, native=args.native)
