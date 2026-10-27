#!/usr/bin/env python3
"""Observe early diagnostics and tools on exact extracted demo boot media."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from generate_sdx_firmware import catalog, identify
from native_program import ROOT, require, sha256
from test_boot_diagnostics import os_text
from test_bootable_atr import DiskBoot, wait_at
from test_cartridge import run as cartridge
from test_rom_diagnostics import call_site, profile_table
from test_sdx_firmware_demo import Smoke
import test_demo


class Tools(Smoke):
    def exercise(self, session):
        title = session.p['build']['exec_build']['strings']['banner'].strip()
        # The ordinary physical VER command below must reach this same identity.
        original = session.command

        def command(line, expected=None):
            return original(line, title.encode('ascii') if line == 'VER' else expected)

        session.command = command
        super().exercise(session)


def run(bundle, rom, out, route, assumed=False):
    out.mkdir(parents=True, exist_ok=True)
    extracted = out/'extracted'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        archive.extractall(extracted)
    extracted = extracted/'exec816-demo'
    for line in (extracted/'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split(None, 1)
        require(sha256(extracted/filename.strip().lstrip('*')) == digest,
                'Extracted package checksum differs: '+filename)
    private = out/'demo'
    shutil.copytree(bundle, private, dirs_exist_ok=True)
    profile = identify(rom.read_bytes())
    observation = {}
    original_execute = test_demo.execute

    def observed_execute(bridge, p, *args, **kwargs):
        before = kwargs.get('before_run')

        def observe(b):
            if assumed:
                wait_at(b, call_site(p, 'sdx_probe_install'), (p['labels']['done'],), 30)
                table = profile_table(p)
                for index in range(len(catalog()['profiles'])):
                    address = table+index*10+2
                    b.memload(address, (b.peek16(address)^1).to_bytes(2, 'little'))
                observation['injection'] = 'Private catalog CRC mismatch; stock ROM/package unchanged'
            at = call_site(p, 'boot_rom_diagnostics')+4
            wait_at(b, at, (p['labels']['done'],), 30)
            title = p['build']['exec_build']['strings']['banner'].strip()
            text = os_text(b)
            require(title in text and
                    'ROM CRC32     =$'+profile['visible_crc32'].upper() in text and
                    'ROM PROFILE   ='+('XLOS (assumed)' if assumed else profile['display_name']) in text and
                    'SDX ROM       =OK' in text, 'Packaged startup diagnostics differ: '+text)
            # The PNG is the last scanout frame; current text assertions above
            # use OS screen RAM because startup can finish within that frame.
            b.screenshot(str(out/'kernel-diagnostics.png'))
            observation.update(identity=title, crc32=profile['visible_crc32'],
                               screen=text, screenshot='kernel-diagnostics.png')
            b.bp_clear_all()
            if before is not None:
                before(b)

        kwargs.update(before_run=observe, boot_verbose=True)
        return original_execute(bridge, p, *args, **kwargs)

    test_demo.execute = observed_execute
    try:
        if route == 'cart':
            result = cartridge(bundle/'cartridge', bundle, ROOT, out/'cart', 'new',
                               False, rom_override=rom, integration=Tools(),
                               distribution_root=extracted)
        else:
            media = out/'system.atr'
            shutil.copyfile(extracted/'exec816.atr', media)
            bootstrap = DiskBoot(private) if route == 'atr' else None
            result = test_demo.run(private, boot_smoke=True, bootstrap=bootstrap,
                                   media_path=media, rom_override=rom, integration=Tools(),
                                   distribution_root=extracted,
                                   boot_route='xex' if route == 'xex' else None,
                                   boot_verbose=True)
            if bootstrap is not None:
                result['boot_reader'] = bootstrap.report
        record = dict(status='pass', tier='development', qualification=False,
                      route=route, firmware=profile, diagnostics=observation,
                      zip_sha256=sha256(bundle/'exec816-demo.zip'), results=result,
                      observer_sha256=sha256(Path(__file__)),
                      walkthrough_sha256=sha256(ROOT/'tools/test_demo.py'))
        (out/'results.json').write_text(json.dumps(record, indent=2)+'\n')
        print(profile['name'], route, 'diagnostics, VER, disk tools and EXIT passed', flush=True)
        return record
    finally:
        test_demo.execute = original_execute


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--route', choices=('atr', 'cart', 'xex'), required=True)
    parser.add_argument('--assume-xlos', action='store_true',
                        help='Test-only private catalog mismatch; leaves ROM and package unchanged')
    args = parser.parse_args()
    run(args.bundle.resolve(), args.rom.resolve(), args.output.resolve(), args.route,
        args.assume_xlos)
