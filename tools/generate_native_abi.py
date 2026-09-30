#!/usr/bin/env python3
"""Copy compiler-owned ABI definitions into the pinned Exec build inputs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate(compiler_dir):
    pin = json.loads((ROOT / 'toolchain/actionc.json').read_text())
    spec = json.loads((compiler_dir / pin['abi_json']).read_text())
    if spec['abi'] != pin['abi']:
        raise ValueError('Compiler ABI differs from the pin')
    return {
        ROOT / 'lib/exec/a816abi.act': (compiler_dir / pin['abi_action']).read_text(),
        ROOT / 'abi/native-dp.json': json.dumps(dict(abi=spec['abi'],
            direct_page=spec['direct_page']), indent=2) + '\n',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT / 'build/actionc')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, content in generate(args.compiler_dir).items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                raise SystemExit('Stale native ABI definition: ' + str(path))
        else:
            path.write_text(content)
