#!/usr/bin/env python3
"""Boot a current SDX demo with an explicit ROM, use tools, persist, and exit."""
import argparse
import json
from pathlib import Path
import shutil

from desktop_menu_check import Menus
from desktop_mouse import schedule
from generate_sdx_firmware import identify
from native_program import ROOT, require, sha256
from test_bootable_atr import DiskBoot
from test_cartridge import run as cartridge
from test_demo import run as demo


class Smoke:
    def exercise(self, s):
        b = s.b

        def at(name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_DESKINPUT_'+name.upper()+'_' in d['name'])

        def move(x, y):
            position = [s.number(at(n), 2) for n in ('cursorX', 'cursorY')]
            s.saved['pointer'] = schedule(b, s.p, position, (x, y))
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (at('cursorX'), x, at('cursorY'), y))
            s.frames(3)

        def click(x, y):
            move(x, y)
            b._cmd_ok('MOUSE AT 2000 0 0 1')
            s.frames(12)
            b._cmd_ok('MOUSE AT 2000 0 0 0')
            s.frames(30)

        s.saved['desktop_menu'] = {}
        Menus(s, click, move).select('Shell')
        s.command('VER', b'Exec816')
        s.command('MD5 ABC.TXT', b'900150983CD24FB0D6963F7D28E17F72')
        s.command('ARC', b'filename is given.')
        s.command('ARC L SAMPLE.ARC', b'Filename')
        s.command('ECHO XLOS >WORK:FW.TXT')
        s.command('TYPE WORK:FW.TXT', b'XLOS')
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['firmware_smoke'] = dict(md5=True, arc_help=True,
                                        arc_listing=True, work_write_read=True)
        for character in 'EXIT':
            s.press(character)
        b._cmd_ok('KEY RETURN down')
        b.bp_clear_all()


def run(bundle, rom, out, route):
    observer_sha256 = sha256(Path(__file__))
    profile = identify(rom.read_bytes())
    out.mkdir(parents=True, exist_ok=True)
    if route == 'cart':
        cartridge(bundle/'cartridge', bundle, ROOT, out, 'new', False,
                  rom_override=rom, integration=Smoke())
        result = json.loads((out/'results.json').read_text())
    else:
        private = out/'demo'
        shutil.copytree(bundle, private, dirs_exist_ok=True)
        media = out/'system.atr'
        shutil.copyfile(bundle/'exec816.atr', media)
        boot = DiskBoot(private)
        result = demo(private, boot_smoke=True, bootstrap=boot, media_path=media,
                      rom_override=rom, integration=Smoke())
        result['boot_reader'] = boot.report
    record = dict(status='pass', tier='development', qualification=False,
                  firmware=profile, route=route, results=result,
                  # Identify the private inputs actually executed, even if
                  # another process refreshes the source bundle meanwhile.
                  zip_sha256=sha256(out/'demo/exec816-demo.zip'),
                  runner_sha256=observer_sha256,
                  reserved_bank_zero_delta=dict(fixed=0, root_kernel=0,
                                               per_public_task=[0]*12, idle=0))
    (out/'firmware-results.json').write_text(json.dumps(record, indent=2)+'\n')
    print(profile['name'], route, 'tools/persistence/exit passed', flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--route', choices=('cart', 'atr'), default='atr')
    args = parser.parse_args()
    run(args.bundle.resolve(), args.rom.resolve(), args.output.resolve(), args.route)
