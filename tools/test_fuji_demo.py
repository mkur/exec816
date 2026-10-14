#!/usr/bin/env python3
"""Focused FUJI availability/help and provider smoke on the extracted demo ZIP."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from native_program import ROOT, require, sha256
from test_demo import run
from test_cartridge import run as run_cartridge


class FujiDemo:
    def __init__(self, output):
        self.output = output

    def exercise(self, session):
        session.command('DIR C:', b'FUJI')
        session.result(0)
        session.command('HELLO | WC', b'1 3 17')
        session.result(0)
        session.command('CLS')
        # ReadArgs help belongs to the foreground console, even with selected
        # Output redirected; reports use selected Output instead.
        screen = session.command('FUJI ? >RAM:FUJI.TXT')
        for keyword in (b'COMMAND', b'HOST', b'IMAGE', b'READWRITE'):
            require(keyword in screen, 'Missing FUJI help field: ' + str(keyword))
        session.result(0)
        session.command('WC <RAM:FUJI.TXT', b'0 0 0')
        session.result(0)
        session.save_screen(self.output / 'boot-smoke.png')
        for character in 'EXIT':
            session.press(character)
        session.b._cmd_ok('KEY RETURN down')
        session.b.bp_clear_all()


def check(bundle, cartridge=False):
    extracted = bundle / 'fuji-smoke-extracted'
    with zipfile.ZipFile(bundle / 'exec816-demo.zip') as archive:
        checks = archive.read('exec816-demo/SHA256SUMS').decode('ascii').splitlines()
        for line in checks:
            digest, name = line.split('  ', 1)
            require(hashlib.sha256(archive.read('exec816-demo/' + name)).hexdigest()
                    == digest, 'Changed ZIP payload: ' + name)
        require(len(checks) == len(archive.namelist()) - 1, 'Incomplete checksums')
        archive.extractall(extracted)
    distribution = extracted / 'exec816-demo'
    if cartridge:
        output = bundle.parent / (bundle.name + '-fuji-cart-smoke')
        result = run_cartridge(bundle / 'carts/cartridge-build/Exec-of816',
            bundle, ROOT, output, 'new', False,
            integration=FujiDemo(output / 'demo'), distribution_root=distribution)
    else:
        result = run(bundle, boot_smoke=True, integration=FujiDemo(bundle),
                     distribution_root=distribution)
    result.update(tier='development', runner_sha256=sha256(Path(__file__)),
                  zip_sha256=sha256(bundle / 'exec816-demo.zip'),
                  scope='Extracted OF816 boot, C:FUJI help/redirection, native providers, guards and EXIT')
    (bundle / ('fuji-cart-results.json' if cartridge else 'fuji-demo-results.json')).write_text(
        json.dumps(result, indent=2) + '\n')
    print('Packaged FUJI passed', bundle, 'cart' if cartridge else 'xex', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--cartridge', action='store_true')
    args = parser.parse_args()
    check(args.bundle.resolve(), args.cartridge)
