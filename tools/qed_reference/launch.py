#!/usr/bin/env python3
"""Launch GEM4XE/QED in AltirraSDL with settings kept inside this bundle."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

BUNDLE = Path(__file__).resolve().parent
PROFILES = r'User\AltirraSDL\Profiles'
FIRMWARE = r'User\AltirraSDL\Firmware'


def find_altirra(value=None):
    explicit = value or os.environ.get('ALTIRRA')
    candidates = [explicit] if explicit else [
        shutil.which('AltirraSDL'),
        Path.home() / 'atari/AltirraSDL/build/macos-release/src/AltirraSDL/AltirraSDL.app',
        Path('/Applications/AltirraSDL.app'),
        Path.home() / 'Applications/AltirraSDL.app',
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser().resolve()
            if path.suffix == '.app':
                path /= 'Contents/MacOS/AltirraSDL'
            if path.is_file() and os.access(path, os.X_OK):
                return path
    raise ValueError('AltirraSDL not found. Set ALTIRRA or pass --altirra /path/to/AltirraSDL.app')


def prepare(bundle=BUNDLE):
    bundle = bundle.resolve()
    rom = bundle / 'firmware/altirraos-816.rom'
    cart = bundle / 'GEM4XE.car'
    disk_inputs = (bundle / 'mydos-boot.atr', bundle / 'qed.atr')
    media = json.loads((bundle / 'profile.json').read_text())['media']
    for name, expected in media.items():
        path = bundle / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Packaged input checksum mismatch: {path.name}')
    settings = configparser.ConfigParser(interpolation=None, delimiters=('=',))
    settings.optionxform = str
    def put(name, values):
        if not settings.has_section(name):
            settings.add_section(name)
        for key, value in values.items():
            settings[name][json.dumps(key)] = json.dumps(value, ensure_ascii=False)
    put(PROFILES, {'Defaults inited': 1, 'Current profile': 964089481})
    put(PROFILES + r'\Defaults', {'XL': 964089481})
    profile = PROFILES + r'\3976D689'
    put(profile, {
        '_Name': 'GEM4XE v0.12 + QED', '_Visible': 1,
        '_Category Mask': 'hardware,firmware,input',
        '_Saved Category Mask': 'hardware,firmware,input',
        'Hardware mode': 1, 'PAL mode': 1, 'SECAM mode': 0, 'Mixed video mode': 0,
        'Memory mode': 2, 'Memory: High banks': 63, 'Memory: MapRAM': 0,
        'Memory: Ultimate1MB': 0, 'CPU: Chip type': 2, 'CPU: Clock multiplier': 8,
        'CPU: Shadow ROMs': 1, 'CPU: Shadow cartridges': 0,
        'Kernel path': str(rom), 'Kernel type': 'kernelxl',
        'Input: Active map names': 'Mouse -> ST Mouse (port 1)',
        'Input: Quick map names': '',
    })
    put(PROFILES + r'\00000000', {
        'BASIC enabled': 0, 'Console: Force self test': 0, 'Console: Cartridge switch': 1,
        'Kernel: Floating-point patch enabled': 0, 'Kernel: Fast boot enabled': 0,
        'Devices: CIO burst transfers enabled': 0, 'CPU: Stop on BRK': 0,
        'Debugger: Break on EXE run': 0,
        'Memory: Randomize on EXE load': 0, 'ExeLoader: Randomize launch delay': 0,
        'Unload on boot types': 6, 'Unload on boot mask': 7,
    })
    # Seed writable disks once. Keep edited documents across launches.
    disk_dir = bundle / 'runtime/disks'
    disk_dir.mkdir(parents=True, exist_ok=True)
    disks = []
    for source in disk_inputs:
        target = disk_dir / source.name
        if not target.exists():
            shutil.copyfile(source, target)
        disks.append(target)
    put(PROFILES + r'\00000000\Mounted Images', {
        'Disk 0': 'W' + str(disks[0]), 'Disk 1': 'W' + str(disks[1]),
    })
    identity = 14695981039346656037
    for char in str(rom).lower():
        identity = ((identity ^ ord(char)) * 1099511628211) & ((1 << 64) - 1)
    identity |= 1 << 63
    put(f'{FIRMWARE}\\Available\\{identity:016X}', {
        'Name': 'AltirraOS 3.44 for 65C816 (GEM4XE bundle)',
        'Path': str(rom), 'Type': 'kernelxl', 'Flags': 0,
    })
    put(FIRMWARE + r'\Default', {'kernelxl': str(rom)})
    config = bundle / 'runtime/config'
    destination = config / 'altirra/settings.ini'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8') as stream:
        settings.write(stream)
    args = [
        '--pal', '--hardware', '800xl', '--kernel', 'xl', '--nobasic',
        '--memsize', '1088K', '--cpu', '65c816,8', '--highbanks', '63',
        '--noultimate1mb', '--cleardevices', '--adddevice',
        'vbxe,version=126,alt_page=false,shared_mem=false',
        '--siopatch', '--nofastboot', '--diskemu', 'generic', '--cart', str(cart),
    ]
    return config, args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--altirra', help='AltirraSDL executable or .app (also ALTIRRA)')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    try:
        config, media_args = prepare()
        if args.prepare_only:
            print('Settings: ' + str(config / 'altirra/settings.ini'), flush=True)
            return 0
        binary = find_altirra(args.altirra)
        command = [str(binary), *media_args]
        print('GEM4XE v0.12 + QED: allow about a minute for the desktop.', flush=True)
        print('Settings: ' + str(config / 'altirra/settings.ini'), flush=True)
        print(shlex.join(command), flush=True)
        return subprocess.call(command, cwd=BUNDLE,
            env={**os.environ, 'XDG_CONFIG_HOME': str(config)})
    except (OSError, ValueError, configparser.Error) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
