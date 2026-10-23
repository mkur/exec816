#!/usr/bin/env python3
"""Reproduce the pinned, writable GEM4XE/QED reference setup for AltirraSDL.

This packages the upstream Calypsi application, independently of the Exec port.
Downloads are cached and hash checked; generated media must match the working
reference. Rebuilding never overwrites runtime/disks or includes them in the ZIP.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from filesystem_audit import Audit
from make_shell_disk import make

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'tools/qed_reference'
PIN_PATH = ROOT / 'toolchain/gem4xe-reference.json'
PIN = json.loads(PIN_PATH.read_text())
ROM_PIN = json.loads((ROOT / PIN['rom_pin']).read_text())['rom']
QED_FILES = ('QED.PRG', 'QED.RSC', 'QED.TXT', 'QEDLGPL.TXT', 'QEDAPACH.TXT')
CONFIG = (b'ID=qed v 5.0\r\nWindow=1 8 24 608 184\r\n'
          b'WinFontID=1\r\nWinFontSize=8\r\nGlobalGEMClip=FALSE\r\n'
          b'GlobalAutosaveCfg=FALSE\r\nGlobalSaveWindows=TRUE\r\n')
SAMPLE = b'GEM4XE QED reference test.\r\nSelect this line, copy it, paste it, then undo.\r\n'
DESKTOP = (b'#R 02\r\n#E 00 00 00 00 00\r\n'
           b'#W 00 00 02 04 32 10 00 B:\\*.PRG@\r\n'
           b'#W 00 00 02 08 26 0C 00 @\r\n'
           b'#W 00 00 02 0A 26 0C 00 @\r\n'
           b'#W 00 00 02 0D 26 0C 00 @\r\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path, expected):
    require(digest(path.read_bytes()) == expected, f'Checksum mismatch: {path}')


def fetch(path, url, expected, offline=False):
    if not path.exists():
        require(not offline, f'Missing cached input: {path}')
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
        require(digest(raw) == expected, f'Changed upstream input: {url}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify(path, expected)
    return path


def prepare_inputs(cache, firmware, offline):
    release_base = f'https://github.com/slaapliedje/gem4xe/releases/download/{PIN["tag"]}/'
    for name, expected in PIN['assets'].items():
        fetch(cache / name, release_base + name, expected, offline)
    published = (cache / 'gem4xe-0.12.sha256').read_text().splitlines()
    for name, expected in PIN['assets'].items():
        if not name.endswith('.sha256'):
            require(any(line.split() == [expected, name] for line in published),
                    f'Asset differs from publisher checksum: {name}')
    source_base = f'https://raw.githubusercontent.com/slaapliedje/gem4xe/{PIN["commit"]}/'
    for name, expected in PIN['source_files'].items():
        fetch(cache / name, source_base + name, expected, offline)
    boot = fetch(cache / 'mydos-4.50.atr', PIN['mydos']['url'], PIN['mydos']['sha256'], offline)
    rom = firmware / 'altirraos-816.rom'
    if not rom.exists():
        require(not offline, f'Missing ROM: run python3 tools/build_rom.py --output-dir {firmware}')
        subprocess.run([sys.executable, str(ROOT / 'tools/build_rom.py'),
                        '--output-dir', str(firmware)], check=True)
    verify(rom, ROM_PIN['sha256'])
    verify(firmware / 'ALTIRRAOS-LICENSE.txt', PIN['rom_notice_sha256'])
    require(rom.stat().st_size == ROM_PIN['bytes'], 'Wrong ROM size')
    require(ROM_PIN['sha256'] == PIN['media']['firmware/altirraos-816.rom'],
            'Shared ROM pin differs from the working reference')
    return boot, rom


def cartridge(original):
    """Change configuration/directory aliases, preserving every code payload."""
    require(original[:4] == b'CART' and len(original) == 16 + 1048576,
            'Wrong cartridge shape')
    rom = bytearray(original[16:])
    directory = 0xff502
    require(rom[directory:directory + 11] == b'GEM     COM' and rom[directory - 1] == 22,
            'Changed pinned ROM directory')
    entries = []
    end = 0
    for i in range(22):
        entry = bytes(rom[directory + i * 16:directory + (i + 1) * 16])
        start = entry[11] * 8192 + entry[12] * 256
        length = int.from_bytes(entry[13:16], 'little')
        entries.append((entry, start, bytes(rom[start:start + length])))
        end = max(end, start + length)
    start = (end + 255) // 256 * 256
    require(start + len(DESKTOP) < 127 * 8192 and
            all(value == 255 for value in rom[start:start + len(DESKTOP)]),
            'Insufficient unused ROM capacity')
    bank, page = divmod(start, 8192)
    rom[directory + 22 * 16:directory + 23 * 16] = (
        b'DESKTOP INF' + bytes((bank, page // 256)) + len(DESKTOP).to_bytes(3, 'little'))
    rom[start:start + len(DESKTOP)] = DESKTOP
    rom[directory - 1] = 23
    disabled = []
    for i, (entry, start, raw) in enumerate(entries):
        if entry[8:11] == b'ACC':
            disabled.append(entry[:8].decode().strip())
            rom[directory + i * 16 + 8:directory + i * 16 + 11] = b'ACX'
        if entry[:11] == b'GEM4XE  CFG':
            require(raw.count(b'# MOUSEPORT=2') == 1, 'Changed pinned boot configuration')
            rom[start:start + len(raw)] = raw.replace(b'# MOUSEPORT=2', b'MOUSEPORT=1  ')
    require(sorted(disabled) == ['CALC', 'CLOCK', 'CONTROL'], 'Changed startup accessories')
    for entry, start, raw in entries:
        if entry[:11] != b'GEM4XE  CFG':
            require(rom[start:start + len(raw)] == raw, 'Original ROM payload changed')
    return original[:8] + struct.pack('>I', sum(rom) & 0xffffffff) + original[12:16] + rom


def write_zip(path, stage):
    """Fixed ordering, timestamp and permissions; only staged static files."""
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(stage.rglob('*')):
            if not source.is_file():
                continue
            name = source.relative_to(stage).as_posix()
            item = zipfile.ZipInfo('gem4xe-altirra/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            mode = 0o755 if name in ('launch.py', 'launch-gem4xe.command') else 0o644
            item.external_attr = (0o100000 | mode) << 16
            archive.writestr(item, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def build(output, cache, firmware, offline=False):
    output, cache, firmware = output.resolve(), cache.resolve(), firmware.resolve()
    boot, rom = prepare_inputs(cache, firmware, offline)
    source = Audit((cache / 'gem4xe-0.12-qed.atr').read_bytes())
    source_inventory = source.sdfs()
    expected = {name: source.files['APPS/' + name] for name in QED_FILES}
    expected.update({'QED.CFG': CONFIG, 'SAMPLE.TXT': SAMPLE})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gem4xe-reference-') as temporary:
        stage = Path(temporary) / 'bundle'
        stage.mkdir()

        def write(name, raw):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

        # Supply every file as binary: notices and ATASCII are byte-preserved.
        disk_files = Path(temporary) / 'disk-files'
        disk_files.mkdir()
        for name, raw in expected.items():
            (disk_files / name).write_bytes(raw)
        make(stage / 'qed.atr', disk_files, binary_names=set(expected),
             sector_bytes=256, sectors=2880)
        disk = Audit((stage / 'qed.atr').read_bytes())
        disk_inventory = disk.mydos()
        require(disk.files == expected, 'QED disk files differ from release/configuration')
        write('mydos-boot.atr', boot.read_bytes())
        boot_audit = Audit(boot.read_bytes())
        boot_inventory = boot_audit.mydos()
        write('licenses/MYDOS-READ.ME', boot_audit.files['READ.ME'])
        write('GEM4XE.car', cartridge((cache / 'gem4xe-0.12.car').read_bytes()))
        write('firmware/altirraos-816.rom', rom.read_bytes())
        write('licenses/ALTIRRAOS-816-LICENSE.txt', (firmware / 'ALTIRRAOS-LICENSE.txt').read_bytes())
        for name in PIN['assets']:
            write('original-media/' + name, (cache / name).read_bytes())
        for name in ('COPYING', 'COPYING.LIB'):
            write('licenses/' + name, (cache / name).read_bytes())
        for name in QED_FILES[2:]:
            write('licenses/' + name, expected[name])
        write('docs/upstream-guide.md', (cache / 'docs/guide.md').read_bytes())
        for name in ('launch.py', 'launch-gem4xe.command', 'README.txt', 'SOURCES.txt'):
            write(name, (TEMPLATES / name).read_bytes())
        write('profile.json', (json.dumps(PIN, indent=2) + '\n').encode())
        for name, checksum in PIN['media'].items():
            verify(stage / name, checksum)
        files = {p.relative_to(stage).as_posix(): digest(p.read_bytes())
                 for p in sorted(stage.rglob('*')) if p.is_file()}
        write('SHA256SUMS', ''.join(f'{value}  {name}\n' for name, value in files.items()).encode())

        # Only publish a fully verified build. Do not traverse/copy runtime/.
        output.mkdir(parents=True, exist_ok=True)
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                relative = path.relative_to(stage)
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                target.chmod(0o755 if str(relative) in ('launch.py', 'launch-gem4xe.command') else 0o644)
        archive = output.with_suffix('.zip')
        write_zip(archive, stage)
    report = {
        'schema_version': 1, 'scope': 'Upstream GEM4XE/QED reference; independent of Exec816',
        'pin_sha256': digest(PIN_PATH.read_bytes()),
        'builder_sha256': digest(Path(__file__).read_bytes()),
        'media': PIN['media'], 'files': files, 'source_inventory': source_inventory,
        'qed_inventory': disk_inventory, 'boot_inventory': boot_inventory,
        'qed_files': {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in expected.items()},
        'archive': {'name': archive.name, 'sha256': digest(archive.read_bytes())},
        'checks': ['publisher and cached input hashes', 'unchanged ROM payloads',
                   'independent MyDOS allocation/file audit', 'media equal to working reference'],
        'bank_zero_delta': {'fixed': 0, 'per_task': 0},
    }
    output.with_name(output.name + '-build.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/gem4xe-altirra')
    parser.add_argument('--cache', type=Path, default=ROOT / 'build/qed-gem4xe-reference/v0.12')
    parser.add_argument('--firmware', type=Path, default=ROOT / 'build/firmware')
    parser.add_argument('--offline', action='store_true', help='Require all inputs already cached')
    args = parser.parse_args()
    try:
        report = build(args.output, args.cache, args.firmware, args.offline)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
    print('Prepared:', args.output.resolve())
    print('ZIP SHA256:', report['archive']['sha256'])


if __name__ == '__main__':
    main()
