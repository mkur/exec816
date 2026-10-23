#!/usr/bin/env python3
"""Launch a local demo in AltirraSDL using a private copy of saved settings."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROFILES = r'User\AltirraSDL\Profiles'
FIRMWARE = r'User\AltirraSDL\Firmware'


def write_launcher(output):
    """Keep the developer launcher beside the build, outside the boot ZIP."""
    path = output / 'launch-altirra.command'
    path.write_text('#!/bin/sh\n'
        'demo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\n'
        f'exec python3 {shlex.quote(str(ROOT / "tools/launch_demo.py"))} '
        '--demo "$demo_dir" "$@"\n')
    path.chmod(0o755)
    return path


def read_settings(path):
    # Colons belong to Altirra key names; percent signs are literal paths.
    settings = configparser.ConfigParser(interpolation=None, delimiters=('=',), strict=False)
    settings.optionxform = str
    with path.open(encoding='utf-8-sig') as source:
        settings.read_file(source)
    return settings


def section(settings, name):
    if not settings.has_section(name):
        settings.add_section(name)
    return settings[name]


def set_values(settings, name, values):
    target = section(settings, name)
    for key, value in values.items():
        target[json.dumps(key)] = json.dumps(value, ensure_ascii=False)


def profile_owner(settings, category):
    """Respect the current profile's saved categories and parent inheritance."""
    current = int(settings.get(PROFILES, '"Current profile"', fallback='0')) & 0xffffffff
    seen = set()
    while current:
        if current in seen:
            raise ValueError('Altirra profile inheritance contains a cycle')
        seen.add(current)
        name = f'{PROFILES}\\{current:08X}'
        enabled = json.loads(settings.get(name, '"_Category Mask"', fallback='""')).split(',')
        saved = json.loads(settings.get(name, '"_Saved Category Mask"', fallback='""')).split(',')
        if category in enabled and category in saved:
            return name
        current = int(settings.get(name, '"_Parent"', fallback='0')) & 0xffffffff
    return f'{PROFILES}\\00000000'


def register_firmware(settings, path, kind):
    # Altirra hashes the case-folded path to identify an imported ROM.
    identity = 14695981039346656037
    for char in str(path).lower():
        identity = ((identity ^ ord(char)) * 1099511628211) & ((1 << 64) - 1)
    identity |= 1 << 63
    set_values(settings, f'{FIRMWARE}\\Available\\{identity:016X}',
               {'Name': 'Exec816 demo ' + kind, 'Path': str(path), 'Type': kind, 'Flags': 0})
    set_values(settings, FIRMWARE + r'\Default', {kind: str(path)})


def require_file(path):
    if not path.is_file():
        raise ValueError(f'Missing demo input: {path}')
    return path


def writable_copy(source, local):
    """Preserve package inputs and reuse the user's WORK disk across launches."""
    require_file(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    target = local / f'{source.stem}-{digest}{source.suffix}'
    if not target.exists():
        shutil.copyfile(source, target)
    return target


def prepare(demo, config, ide_firmware, cart=None, disks=()):
    demo = demo.resolve()
    record = json.loads(require_file(demo / 'demo-manifest.json').read_text())
    monitor = json.loads(require_file(demo / 'of816/of816.json').read_text())
    settings = read_settings(require_file(config))
    local = demo / 'altirra'
    local.mkdir(exist_ok=True)
    hardware = profile_owner(settings, 'hardware')
    machine = record['pin']['machine']
    set_values(settings, hardware, {
        'Hardware mode': 1, 'PAL mode': int(machine['video'].upper() == 'PAL'),
        'SECAM mode': 0, 'Mixed video mode': 0, 'Memory mode': 2,
        'Memory: High banks': machine['high_banks'], 'Memory: Ultimate1MB': 0,
        'Memory: MapRAM': 0, 'CPU: Chip type': 2,
        'CPU: Clock multiplier': machine['clock_multiplier'],
        'CPU: Shadow ROMs': int(machine.get('shadow_rom', True)),
        'CPU: Shadow cartridges': 0,
    })
    rom = require_file(demo / 'of816' / monitor['rom']['name'])
    register_firmware(settings, rom, 'kernelxl')
    set_values(settings, profile_owner(settings, 'firmware'),
               {'Kernel path': str(rom), 'Kernel type': 'kernelxl'})
    set_values(settings, profile_owner(settings, 'startupconfig'),
               {'BASIC enabled': 0, 'Console: Force self test': 0, 'Console: Cartridge switch': 1})
    set_values(settings, profile_owner(settings, 'acceleration'), {
        'Cassette: SIO patch enabled': 0, 'Disk: SIO patch enabled': 0,
        'Disk: SIO override detection enabled': 0, 'Disk: Burst transfers enabled': 0,
        'Devices: SIO patch enabled': 0, 'Devices: SIO burst transfers enabled': 0,
        'Devices: Accelerate with SIO patch': 0, 'Devices: Accelerate with PBI patch': 0,
        'Devices: CIO burst transfers enabled': 0, 'Kernel: Fast boot enabled': 0,
    })
    # Loading the XEX/cart must retain the disks already mounted from settings.
    set_values(settings, profile_owner(settings, 'boot'),
               {'Unload on boot types': 6, 'Unload on boot mask': 7,
                'ExeLoader: Randomize launch delay': 0})

    device_profile = profile_owner(settings, 'devices')
    devices = json.loads(json.loads(settings.get(device_profile, '"Devices"', fallback='"[]"')))
    existing_ide = next((d for d in devices if d.get('tag') == 'kmkjzide2'), {})
    devices = [d for d in devices if d.get('tag') != 'kmkjzide2']
    if record.get('bitmap') and not any(d.get('tag') == 'vbxe' for d in devices):
        devices.append({'tag': 'vbxe', 'params': {'version': 126, 'alt_page': False, 'shared_mem': False}})
    if record.get('ide_only') or record.get('ideplus'):
        firmware = require_file(ide_firmware.resolve())
        register_firmware(settings, firmware, 'kmkjzide2')
        source = demo / ('ideplus.img' if record.get('ide_only') else 'ideplus/ideplus.img')
        image = writable_copy(source, local) if record.get('ide_only') else require_file(source)
        params = {**existing_ide.get('params', {}), 'revision': 'e', 'id': 0,
                  'enablesdx': False, 'writeprotect': False}
        devices.append({'tag': 'kmkjzide2', 'params': params, 'buses': {'0': {'children': [
            {'tag': 'hdrawimage', 'params': {'path': str(image), 'solid_state': True,
                                           'write_enabled': bool(record.get('ide_only'))}}]}}})
    set_values(settings, device_profile, {'Devices': json.dumps(devices, ensure_ascii=False),
                                        'Disk: Emulation mode': 10, 'Disk: Accurate sector timing': 1})
    mounted = section(settings, profile_owner(settings, 'mountedimages') + r'\Mounted Images')
    mounted.clear()
    if not record.get('ide_only'):
        drive = monitor['boot_config']['system_drive']
        if record.get('bootable_atr'):
            set_values(settings,mounted.name,
                {f'Disk {drive-1}':'W'+str(writable_copy(demo/record['media'],local))})
        else:
            set_values(settings, mounted.name, {
                f'Disk {drive - 1}': 'R' + str(require_file(demo / record['media'])),
                'Disk 7': 'W' + str(writable_copy(demo / 'work.atr', local)),
            })
    for drive, source in disks:
        if not 1 <= drive <= 8:
            raise ValueError('Additional disk drive must be in D1..D8')
        key = f'Disk {drive - 1}'
        if json.dumps(key) in mounted:
            raise ValueError(f'D{drive}: already has a demo disk attached')
        set_values(settings, mounted.name,
                   {key: 'W' + str(writable_copy(source.resolve(), local))})
    boot = require_file(demo / record['boot_image'])
    if record.get('bootable_atr'):
        boot=writable_copy(demo/record['media'],local)
    mode = '--run'
    if cart:
        name = f'exec816-demo/cartridge/Exec-of816-atarimax-8mbit-{cart}.car'
        boot = local / f'boot-{cart}.car'
        with zipfile.ZipFile(require_file(demo / record['distribution'])) as archive:
            boot.write_bytes(archive.read(name))
        mode = '--cart'
    config_home = local / 'config'
    destination = config_home / 'altirra/settings.ini'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if config.resolve() == destination.resolve():
        raise ValueError('Select the normal Altirra settings, not the generated demo copy')
    with destination.open('w', encoding='utf-8') as output:
        settings.write(output)
    return config_home, [mode, str(boot)]


def find_altirra(value=None):
    candidates = [value or os.environ.get('ALTIRRA')] if value or os.environ.get('ALTIRRA') else [
        shutil.which('AltirraSDL'),
        str(Path.home() / 'atari/AltirraSDL/build/macos-release/src/AltirraSDL/AltirraSDL.app/Contents/MacOS/AltirraSDL'),
        '/Applications/AltirraSDL.app/Contents/MacOS/AltirraSDL',
        str(Path.home() / 'Applications/AltirraSDL.app/Contents/MacOS/AltirraSDL'),
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser().resolve()
            if path.suffix == '.app':
                path /= 'Contents/MacOS/AltirraSDL'
            if path.is_file() and os.access(path, os.X_OK):
                return path
    raise ValueError('AltirraSDL not found; set ALTIRRA or pass --altirra /path/to/AltirraSDL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', type=Path, required=True)
    parser.add_argument('--config', type=Path,
                        default=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'altirra/settings.ini')
    parser.add_argument('--altirra', help='AltirraSDL executable or macOS .app; also accepts ALTIRRA')
    parser.add_argument('--ide-firmware', type=Path, default=ROOT / 'build/firmware/ideplus-bios-2.1.rom')
    parser.add_argument('--cart', choices=('old', 'new'), help='Boot a cartridge instead of the combined OF816 XEX')
    parser.add_argument('--disk', nargs=2, action='append', default=[], metavar=('DRIVE', 'IMAGE'),
                        help='Attach a persistent writable copy of an additional disk, e.g. --disk 2 utils.atr')
    parser.add_argument('--prepare-only', action='store_true', help='Write demo settings and print the launch command')
    args = parser.parse_args()
    try:
        binary = find_altirra(args.altirra)
        disks = [(int(drive), Path(image).expanduser()) for drive, image in args.disk]
        config_home, media_args = prepare(args.demo, args.config.expanduser(), args.ide_firmware.expanduser(), args.cart, disks)
        command = [str(binary), *media_args]
        print(f'Demo settings: {config_home / "altirra/settings.ini"}', flush=True)
        print(shlex.join(command), flush=True)
        if not args.prepare_only:
            return subprocess.call(command, env={**os.environ, 'XDG_CONFIG_HOME': str(config_home)})
    except (OSError, ValueError, KeyError, configparser.Error, zipfile.BadZipFile) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
