#!/usr/bin/env python3
"""Make the small read-only playground ATR, separate from qualification fixtures.

720 sectors (128 or 256 bytes), DOS-2-compatible VTOC and MyDOS subdirectories.
The three boot sectors are empty: launch the shell XEX with this as a data disk.
"""
import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'examples/shell-disk'
SECTORS, SECTOR_BYTES = 720, 128


def make(path, source=SOURCE, binary_names=(), sector_bytes=128):
    if sector_bytes not in (128, 256):
        raise ValueError('Expected 128- or 256-byte sectors')
    disk = bytearray(16+384+(SECTORS-3)*sector_bytes)
    disk[:6] = struct.pack('<HHH', 0x296, (len(disk)-16)//16, sector_bytes)
    payload_bytes = sector_bytes-3
    free = set(range(4, 720)) - set(range(360, 369))
    contents = {}

    def offset(sector):
        return 16+(sector-1)*128 if sector<=3 else 16+384+(sector-4)*sector_bytes

    def allocate(count):
        if count == 0:
            return []
        start = next(s for s in sorted(free) if set(range(s, s+count)) <= free)
        chain = list(range(start, start+count))
        free.difference_update(chain)
        return chain

    def directory(folder, start):
        children = sorted(folder.iterdir(), key=lambda p: p.name)
        if len(children) > 64:
            raise ValueError('Directory exceeds 64 entries')
        for ordinal, child in enumerate(children):
            base, dot, suffix = child.name.partition('.')
            if not (1 <= len(base) <= 8 and len(suffix) <= 3 and
                    all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in base+suffix)):
                raise ValueError('Expected uppercase 8.3 playground name: '+child.name)
            name = base.encode().ljust(8, b' ')+suffix.encode().ljust(3, b' ')
            if child.is_dir():
                chain = allocate(8)
                directory(child, chain[0])
                flags = 0x10
            else:
                relative = child.relative_to(source).as_posix()
                payload = child.read_bytes() if relative in binary_names else child.read_text(encoding='ascii').encode('ascii')
                contents[child.relative_to(source).as_posix()] = payload
                chain = allocate((len(payload)+payload_bytes-1)//payload_bytes)
                flags = 0x42
                for index, sector in enumerate(chain):
                    chunk = payload[index*payload_bytes:(index+1)*payload_bytes]
                    following = chain[index+1] if index+1 < len(chain) else 0
                    at = offset(sector)
                    disk[at:at+len(chunk)] = chunk
                    disk[at+payload_bytes:at+sector_bytes] = bytes([(ordinal << 2) | (following >> 8), following & 255, len(chunk)])
            entry = bytes([flags])+struct.pack('<HH', len(chain), chain[0] if chain else 0)+name
            at = offset(start+ordinal//8)+16*(ordinal%8)
            disk[at:at+16] = entry

    directory(source, 361)
    vtoc = offset(360)
    disk[vtoc:vtoc+5] = bytes([2])+struct.pack('<HH', 707, len(free))
    for sector in free:
        disk[vtoc+10+sector//8] |= 0x80 >> (sector & 7)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(disk)
    return contents


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = make(args.output)
    print(f'{args.output}: {SECTORS} x {SECTOR_BYTES} bytes; {len(files)} files, {sum(map(len, files.values()))} text bytes')
