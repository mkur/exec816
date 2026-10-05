#!/usr/bin/env python3
"""Build the physical desktop fixture with an optional independent application."""
import argparse
from pathlib import Path
from build_bitmap_console import build_bitmap
from native_program import ROOT


def build(out, mode='opt', second_app=False, profile=4, aes=False):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'tests/programs/desktop_input.act'
    if second_app:
        text = source.read_text().replace('USE DESKBOOT\n', 'USE DESKBOOT\nUSE DESKAPP\n')
        text = text.replace('  ready=1\n', '  Require(DESKAPP.Start()<>0)\n  ready=1\n')
        text = text.replace('  Send(DESKTYPES.CLOSE,panel)', '  DESKAPP.Stop()\n  Send(DESKTYPES.CLOSE,panel)')
        source = out/'two-client-input.act'
        source.write_text(text)
    return build_bitmap(source, out, mode == 'opt', desktop=True, aes=aes, stack_checks=True,
        dos_mounts=[dict(alias='D1', unit=49, sectors=720, sector_bytes=128, profile=profile, format=2)])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--second-app', action='store_true')
    parser.add_argument('--aes', action='store_true')
    parser.add_argument('--profile', choices=(1, 4), type=int, default=4)
    args = parser.parse_args()
    build(args.output.resolve(), args.mode, args.second_app, args.profile, args.aes)
