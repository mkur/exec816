#!/usr/bin/env python3
"""Build the original-source, disk-loaded MagiC text editor."""
import argparse
from pathlib import Path

from build_c_program import build as application
from native_program import ROOT
from prepare_mgedit import APP_SOURCE, PORT, prepare


def build(output, optimize=True, extra_sources=(), definitions=None):
    output = Path(output).resolve()
    prepare(output / 'source', native=True)
    source = output / 'source' / APP_SOURCE
    sources = [source / 'mgedit.c', source / 'mgedwind.c', ROOT / 'c/compat/gem/rect.c', *extra_sources]
    flags = ['--char-is-unsigned', '--no-inline', '-Werror=implicit-function-declaration']
    return application(output, sources, optimize, includes=[source],
        definitions={**{str(path): flags for path in sources}, **(definitions or {})},
        main_signature='args', gemdos=True, minimum_stack=2560,
        extra_inputs=[source / 'globals.h', PORT / 'inputs.json', PORT / 'native.patch'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw', action='store_true')
    args = parser.parse_args()
    build(args.output, not args.raw)
