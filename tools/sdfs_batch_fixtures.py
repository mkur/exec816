#!/usr/bin/env python3
"""Independent SDFS media with alternating occupied bits across a bitmap boundary."""
import argparse
import json
from pathlib import Path

from filesystem_audit import Audit, word
from native_program import require, sha256
from sdfs_reference import make, verify


def produce(output, size):
    output.mkdir(parents=True, exist_ok=True)
    source = output/'source'
    source.mkdir(exist_ok=True)
    content = bytes((i & 255) ^ 0x39 for i in range(30*size))
    (source/'KEEP.BIN').write_bytes(content)
    media = output/f'fragmented-{size}.atr'
    make(media, source, sectors=2880, sector_bytes=size)
    initial = Audit(media.read_bytes())
    initial.sdfs()
    image = initial.image
    header = image.sector(1)
    bitmap = word(header, 16)
    boundary = size*8
    old = [s for s, owner in initial.owners.items() if owner == 'KEEP.BIN data']
    targets = list(range(boundary-19, boundary+41, 2))
    require(len(old) == len(targets) == 30, 'Unexpected fixture extent')
    require(all(s not in initial.owners for s in targets), 'Relocation overlaps metadata')
    moved = dict(zip(old, targets))

    def free(sector, value):
        at = image.offset(bitmap+sector//(size*8))+(sector//8) % size
        bit = 0x80 >> (sector & 7)
        image.data[at] = image.data[at] | bit if value else image.data[at] & (255 ^ bit)

    for sector, target in moved.items():
        at = image.offset(target)
        image.data[at:at+size] = image.sector(sector)
        free(sector, True)
        free(target, False)
    for sector, owner in initial.owners.items():
        if owner == 'KEEP.BIN map':
            at = image.offset(sector)
            for offset in range(4, size, 2):
                payload = word(image.data, at+offset)
                if payload in moved:
                    image.data[at+offset:at+offset+2] = moved[payload].to_bytes(2, 'little')
    media.write_bytes(image.data)
    audit = Audit(media.read_bytes())
    report = audit.sdfs()
    require(audit.files == {'KEEP.BIN': content}, 'Relocation changed contents')
    verified = verify(media, audit.files, output/'independent-readback')
    record = dict(status='pass', sector_bytes=size, sectors=2880,
                  bitmap_boundary=boundary, allocation_hint=boundary-20,
                  image_sha256=sha256(media), allocation=report,
                  relocated=moved, independent_readback=verified,
                  scope='Host-generated disposable test media; not a runtime ownership scan')
    (output/'fixture.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=int, choices=(128, 256), required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(produce(args.output.resolve(), args.size), indent=2))
