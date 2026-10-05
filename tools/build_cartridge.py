#!/usr/bin/env python3
"""Wrap an unchanged Exec816 XEX in an Atarimax 8 Mbit cartridge."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BANK_BYTES = 8192
ROM_BYTES = 1024 * 1024
RAM_START = 0x9000
RAM_END = 0x9400
SOURCE = ROOT / 'platform/altirraos/cartridge.s'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def segments(raw):
    """Validate this wrapper's deliberately narrow Exec XEX input contract."""
    if raw[:2] != b'\xff\xff':
        raise ValueError('Expected an XEX executable')
    offset = 2
    result = []
    run = None
    while offset < len(raw):
        if offset + 2 <= len(raw) and raw[offset:offset+2] == b'\xff\xff':
            offset += 2
            continue
        if offset + 4 > len(raw):
            raise ValueError('Truncated XEX header')
        low, high = struct.unpack_from('<HH', raw, offset)
        offset += 4
        size = high - low + 1
        if size <= 0 or offset + size > len(raw):
            raise ValueError('Truncated or reversed XEX segment')
        # INITAD effects remain the responsibility of the Exec image builder.
        # Direct records must not overwrite this reader, the screen, or ROM.
        if not (0x0800 <= low <= high < RAM_START or
                (low, high) in ((0x02e0, 0x02e1), (0x02e2, 0x02e3))):
            raise ValueError(f'Unsupported cartridge XEX destination: ${low:04x}-${high:04x}')
        payload = raw[offset:offset+size]
        if low == 0x02e0:
            run = int.from_bytes(payload, 'little')
        if low == 0x02e2 and not 0x0800 <= int.from_bytes(payload, 'little') < RAM_START:
            raise ValueError('INITAD must point into the Exec loading arena')
        result.append((low, payload))
        offset += size
    if run is None or not 0x0800 <= run < RAM_START:
        raise ValueError('An explicit Exec RUNAD is required')
    if not result or len(raw) > 126 * BANK_BYTES - 1:
        raise ValueError('XEX does not fit between the two cartridge boot banks')
    return result


def build(xex, output):
    xex, output = Path(xex), Path(output).resolve()
    raw = xex.read_bytes()
    records = segments(raw)
    output.mkdir(parents=True, exist_ok=True)
    (output/'cartridge.inc').write_text(f'XEX_BYTES = {len(raw)}\n')
    (output/'cartridge.cfg').write_text('''MEMORY {
    RAM: start=$9000, size=$400, file="loader.bin", fill=yes, fillval=$ff;
    ROM: start=$be00, size=$1fa, file="stub.bin", fill=yes, fillval=$ff;
}
SEGMENTS {
    LOADER: load=RAM, type=ro;
    STUB: load=ROM, type=ro;
}
''')
    subprocess.run(['ca65', '-I', str(output), '-o', 'cartridge.o',
                    '-l', 'cartridge.lst', str(SOURCE)], cwd=output, check=True)
    subprocess.run(['ld65', '-C', 'cartridge.cfg', '-Ln', 'cartridge.lbl',
                    '-m', 'cartridge.map', 'cartridge.o'], cwd=output, check=True)
    labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
              for line in (output/'cartridge.lbl').read_text().splitlines()}
    boot = bytearray(b'\xff' * BANK_BYTES)
    boot[0x1a00:0x1e00] = (output/'loader.bin').read_bytes()
    boot[0x1e00:0x1ffa] = (output/'stub.bin').read_bytes()
    # Non-diagnostic, run cartridge, no disk boot. OF816 retains its countdown.
    boot[0x1ffa:] = struct.pack('<HBBH', labels['cart_start'], 0, 4, labels['cart_init'])
    rom = bytearray(b'\xff' * ROM_BYTES)
    rom[:BANK_BYTES] = rom[-BANK_BYTES:] = boot
    rom[BANK_BYTES:BANK_BYTES+len(raw)] = raw
    name = xex.stem + '-atarimax-8mbit'
    files = {name+'.bin': bytes(rom)}
    for variant, kind in (('old', 42), ('new', 75)):
        files[f'{name}-{variant}.car'] = (
            struct.pack('>4sIII', b'CART', kind, sum(rom) & 0xffffffff, 0) + rom)
    for filename, data in files.items():
        (output/filename).write_bytes(data)
    record = dict(format='exec816-atarimax-v1', input_xex=xex.name,
                  input_xex_bytes=len(raw), input_xex_sha256=digest(raw),
                  segments=len(records), init_callbacks=sum(a == 0x02e2 for a, _ in records),
                  cartridge_bytes=ROM_BYTES, types={'old':42, 'new':75},
                  labels=labels, source_sha256=digest(SOURCE.read_bytes()),
                  builder_sha256=digest(Path(__file__).read_bytes()),
                  files={n:digest(d) for n,d in files.items()},
                  bank_zero_delta=dict(fixed_runtime=0, per_public_task=0, idle=0),
                  boot_only_borrowed=dict(start=RAM_START, end=RAM_END, bytes=RAM_END-RAM_START),
                  scope='Cold boot on the pinned native-65816 AltirraOS profile; physical hardware unqualified.')
    (output/'cartridge.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def augment_demo(source, output, expected_sha256):
    """Preserve every released payload; add cartridges, guide and checksums."""
    source, output = Path(source), Path(output).resolve()
    if source.resolve() == output/'exec816-demo.zip':
        raise ValueError('Keep the original demo ZIP in a separate directory')
    original = source.read_bytes()
    if digest(original) != expected_sha256:
        raise ValueError('Source demo ZIP checksum differs')
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
                not n.startswith('exec816-demo/') or '..' in Path(n).parts or n.endswith('/')
                for n in names):
            raise ValueError('Unexpected demo archive layout')
        files = {n.removeprefix('exec816-demo/'): archive.read(n) for n in names}
    checks = files.get('SHA256SUMS', b'').decode('ascii').splitlines()
    verified = set()
    for line in checks:
        sha, name = line.split('  ', 1)
        if name not in files or digest(files[name]) != sha or name in verified:
            raise ValueError('Invalid source demo checksums')
        verified.add(name)
    if verified != set(files)-{'SHA256SUMS'} or 'Exec-of816.xex' not in files:
        raise ValueError('Source demo checksums do not cover every file')
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, payload in list(files.items()):
        if not name.endswith('.xex'):
            continue
        work = output/'cartridge-build'/Path(name).stem
        work.mkdir(parents=True, exist_ok=True)
        xex = work/Path(name).name
        xex.write_bytes(payload)
        record = build(xex, work)
        for artifact in record['files']:
            if 'cartridge/'+artifact in files:
                raise ValueError('Source demo already contains cartridge images')
            files['cartridge/'+artifact] = (work/artifact).read_bytes()
        records[name] = record
    files['cartridge/README.txt'] = (ROOT/'docs/cartridge-distribution.txt').read_bytes()
    for name, path in (('EXEC816-GPL-3.0.txt','LICENSE'), ('EXEC816-MIT.txt','LICENSE-MIT'),
                       ('EXEC816-LICENSING.md','LICENSING.md')):
        files.setdefault(name, (ROOT/path).read_bytes())
    files['SHA256SUMS'] = ''.join(f'{digest(data)}  {name}\n'
                                for name,data in sorted(files.items())
                                if name != 'SHA256SUMS').encode('ascii')
    result = output/'exec816-demo.zip'
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('exec816-demo/'+name, date_time=(2026,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    record = dict(source_zip_sha256=digest(original), zip_sha256=digest(result.read_bytes()),
                  cartridges=records, files={n:digest(d) for n,d in files.items()})
    (output/'cartridge-demo.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xex', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.xex, args.output)
