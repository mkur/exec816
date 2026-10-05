"""Host-only allocation oracle for disposable MyDOS and SDFS write tests.

This module is never linked into Exec816. It deliberately reconstructs whole
volume ownership, independently of the Action! allocator and read cache.
"""
import argparse
import json
from pathlib import Path

from mydos_fixtures import Image


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], 'little')


class Audit:
    def __init__(self, data):
        self.image = Image(data)
        self.owners = {0: 'reserved zero'}
        self.files = {}
        self.directories = 0

    def claim(self, sector, owner):
        if not 1 <= sector <= self.image.count:
            raise ValueError(f'{owner}: out-of-range sector {sector}')
        if sector in self.owners:
            raise ValueError(f'{owner}: sector {sector} also owned by {self.owners[sector]}')
        self.owners[sector] = owner

    def finish(self, free, recorded):
        expected = set(range(self.image.count + 1)) - self.owners.keys()
        if free != expected:
            raise ValueError(f'Allocation mismatch: live/free={sorted(free - expected)[:8]}, '
                             f'lost={sorted(expected - free)[:8]}')
        if recorded != len(free):
            raise ValueError(f'Free count {recorded}, bitmap has {len(free)}')
        return dict(sectors=self.image.count, sector_bytes=self.image.size,
                    allocated=len(self.owners) - 1, free=len(free),
                    files=len(self.files), directories=self.directories)

    def mydos(self):
        image = self.image
        header = image.sector(360)
        marker = header[0]
        if marker < 2:
            raise ValueError('Unsupported MyDOS VTOC')
        pages = 1 if marker == 2 else (marker - 2) * (2 if image.size == 128 else 1)
        if pages > 357:
            raise ValueError('VTOC overlaps boot sectors')
        bitmap = b''.join(image.sector(360 - i) for i in range(pages))
        if 10 + image.count // 8 >= len(bitmap):
            raise ValueError('VTOC does not cover geometry')
        for sector in [1, 2, 3, *range(361 - pages, 361)]:
            self.claim(sector, 'fixed metadata')
        stack = [(361, '', 0)]
        while stack:
            directory, prefix, depth = stack.pop()
            if depth > 16:
                raise ValueError('Directory nesting limit')
            self.directories += 1
            for sector in range(directory, directory + 8):
                self.claim(sector, prefix or 'root')
            for ordinal in range(64):
                data = image.sector(directory + ordinal // 8)
                entry = data[(ordinal % 8) * 16:(ordinal % 8 + 1) * 16]
                flags = entry[0]
                if not flags:
                    break
                if flags & 0x80:
                    continue
                if flags & 1:
                    raise ValueError('Incomplete MyDOS entry')
                name = entry[5:13].decode('ascii').rstrip()
                suffix = entry[13:16].decode('ascii').rstrip()
                path = prefix + name + ('.' + suffix if suffix else '')
                if flags & ~0x20 not in (0x10, 0x42, 0x46):
                    raise ValueError('Unsupported MyDOS entry flags')
                count, sector = word(entry, 1), word(entry, 3)
                if flags & 0x10:
                    if count != 8:
                        raise ValueError('Bad MyDOS directory extent')
                    stack.append((sector, path + '/', depth + 1))
                    continue
                payload = bytearray()
                actual = 0
                while sector:
                    self.claim(sector, path)
                    data = image.sector(sector)
                    high, low, used = data[-3:]
                    if used > len(data) - 3:
                        raise ValueError('Bad MyDOS payload count')
                    if not flags & 4 and high >> 2 != ordinal:
                        raise ValueError('Bad MyDOS file ordinal')
                    sector = ((high if flags & 4 else high & 3) << 8) | low
                    payload.extend(data[:used])
                    actual += 1
                if actual != count:
                    raise ValueError('MyDOS chain count mismatch')
                if path in self.files:
                    raise ValueError('Duplicate stored filename')
                self.files[path] = bytes(payload)
        free = {s for s in range(image.count + 1)
                if bitmap[10 + s // 8] & (0x80 >> (s & 7))}
        # DOS 2-compatible producers may deliberately exclude the last sector.
        allocatable = image.count - (3 + pages + 8)
        if (marker == 2 and word(header, 1) == allocatable - 1
                and image.count not in free and image.count not in self.owners):
            self.claim(image.count, 'DOS 2 reserved final sector')
            allocatable -= 1
        if word(header, 1) != allocatable:
            raise ValueError('MyDOS formatted capacity mismatch')
        return self.finish(free, word(header, 3))

    def sdfs(self):
        image = self.image
        header = image.sector(1)
        if header[32] not in (0x20, 0x21) or word(header, 11) != image.count:
            raise ValueError('Unsupported SDFS header/geometry')
        start, pages = word(header, 16), header[15]
        if start < 4 or not pages or start + pages - 1 > image.count:
            raise ValueError('Invalid SDFS bitmap extent')
        bitmap = b''.join(image.sector(start + i) for i in range(pages))
        if image.count // 8 >= len(bitmap):
            raise ValueError('SDFS bitmap does not cover geometry')
        for sector in [1, 2, 3, *range(start, start + pages)]:
            self.claim(sector, 'fixed metadata')
        stack = [(word(header, 9), 0, '', None, 0)]
        while stack:
            sector, parent, path, length, depth = stack.pop()
            directory = sector
            if depth > 16:
                raise ValueError('Directory nesting limit')
            previous = 0
            data_sectors = []
            while sector:
                self.claim(sector, path + ' map')
                data = image.sector(sector)
                if word(data, 2) != previous:
                    raise ValueError('SDFS map back-link mismatch')
                for offset in range(4, image.size, 2):
                    target = word(data, offset)
                    if target:
                        self.claim(target, path + ' data')
                    data_sectors.append(target)
                previous, sector = sector, word(data, 0)
            payload = b''.join(image.sector(s) if s else bytes(image.size)
                               for s in data_sectors)
            if length is not None:
                if length > len(payload):
                    raise ValueError('Missing SDFS map extent')
                if path in self.files:
                    raise ValueError('Duplicate stored filename')
                self.files[path] = payload[:length]
                continue
            self.directories += 1
            if len(payload) < 23 or word(payload, 1) != parent:
                raise ValueError('Invalid SDFS directory parent')
            length = int.from_bytes(payload[3:6], 'little')
            if length < 23 or length % 23 or length > len(payload):
                raise ValueError('Invalid SDFS directory length')
            if 0 in data_sectors[:(length + image.size - 1) // image.size]:
                raise ValueError('Sparse SDFS directory')
            for offset in range(23, length, 23):
                entry = payload[offset:offset + 23]
                flags = entry[0]
                if not flags:
                    break
                if flags & 0x10 and not flags & 8:
                    continue
                if not flags & 8 or flags & 0x90:
                    raise ValueError('Incomplete/invalid SDFS entry')
                name = entry[6:14].decode('ascii').rstrip()
                suffix = entry[14:17].decode('ascii').rstrip()
                child = path + name + ('.' + suffix if suffix else '')
                extent = None if flags & 0x20 else int.from_bytes(entry[3:6], 'little')
                stack.append((word(entry, 1), directory, child + '/' if extent is None else child,
                              extent, depth + 1 if extent is None else depth))
        free = {s for s in range(image.count + 1) if bitmap[s // 8] & (0x80 >> (s & 7))}
        # Native SpartaDOS can reserve its final sector; the pinned Altirra
        # validator has the same explicitly documented exception.
        if image.count not in free and image.count not in self.owners:
            self.claim(image.count, 'SpartaDOS reserved final sector')
        return self.finish(free, word(header, 13))


def audit(path, format):
    result = Audit(Path(path).read_bytes())
    return getattr(result, format)()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('format', choices=('mydos', 'sdfs'))
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.image, args.format), indent=2))
