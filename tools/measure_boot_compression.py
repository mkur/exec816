#!/usr/bin/env python3
"""Host-only compression experiment on existing fixed-image demo builds.

EBC1 files are experiment artifacts, not bootable images or a proposed ABI.
This tool measures archived uncompressed builds. No 65816 timing is measured.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

from banked_image import extents
from lz4_block import LZ4


ROOT = Path(__file__).resolve().parents[1]
HEADER = struct.Struct('<4sIII')
BLOCK = struct.Struct('<3sBII')
COMPRESSED = 0x80
CODECS = {'lz4': 1, 'lz4-hc12': 1, 'deflate9': 2}
CART_CAPACITY = 126 * 8192 - 1


def digest(data):
    return hashlib.sha256(data).hexdigest()


def split_blocks(spans, maximum):
    for address, payload, size, flags, _ in spans:
        for offset in range(0, size, maximum):
            count = min(maximum, size - offset)
            yield address + offset, flags, count, payload[offset:offset + count]


def compress_block(codec, data, lz4):
    if CODECS[codec] == 1:
        return lz4.compress(data, codec == 'lz4-hc12')
    encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
    return encoder.compress(data) + encoder.flush()


def encode(blocks, codec, lz4):
    archive = bytearray(HEADER.pack(b'EBC1', 1, CODECS[codec], len(blocks)))
    compressed = raw = stored = 0
    maximum_stored = 0
    for address, flags, size, data in blocks:
        payload = data
        if flags != 1:
            candidate = compress_block(codec, data, lz4)
            if len(candidate) < len(data):
                payload = candidate
                flags |= COMPRESSED
                compressed += 1
            else:
                raw += 1
        archive += BLOCK.pack(address.to_bytes(3, 'little'), flags, size, len(payload))
        archive += payload
        stored += len(payload)
        maximum_stored = max(maximum_stored, len(payload))
    return bytes(archive), dict(compressed_blocks=compressed, raw_blocks=raw,
                               stored_payload_bytes=stored,
                               largest_stored_block_bytes=maximum_stored)


def decode(archive, lz4):
    magic, version, codec, count = HEADER.unpack_from(archive)
    if magic != b'EBC1' or version != 1 or codec not in (1, 2):
        raise ValueError('Invalid experiment archive')
    result = []
    offset = HEADER.size
    for _ in range(count):
        address, flags, size, stored = BLOCK.unpack_from(archive, offset)
        offset += BLOCK.size
        payload = archive[offset:offset + stored]
        if len(payload) != stored:
            raise ValueError('Truncated experiment block')
        offset += stored
        kind = flags & ~COMPRESSED
        if kind not in (0, 1, 2) or not 0 < size <= 65535:
            raise ValueError('Invalid experiment block')
        address = int.from_bytes(address, 'little')
        if (address & 65535) + size > 65536:
            raise ValueError('Experiment block crosses a bank')
        if kind == 1:
            if stored or flags & COMPRESSED:
                raise ValueError('Invalid zero-fill block')
        else:
            if flags & COMPRESSED:
                payload = lz4.decompress(payload, size) if codec == 1 else zlib.decompress(payload, -15)
            if len(payload) != size:
                raise ValueError('Decompressed length mismatch')
        result.append((address, kind, size, payload))
    if offset != len(archive):
        raise ValueError('Trailing experiment archive bytes')
    return result


def xex_segment(address, data):
    return struct.pack('<HH', address, address + len(data) - 1) + data


def original_records(spans, memory):
    """Archived uncompressed transport measured by the original experiment."""
    for index, (_, payload, size, flags, _) in enumerate(spans):
        for offset in range(0, size, memory['constants']['CHUNK']):
            count = min(size-offset, memory['constants']['CHUNK'])
            yield struct.pack('<HHHBB', index, offset, count, flags, 0) + (
                payload[offset:offset+count] if flags != 1 else b'')


def measure(name, build, output, sizes, lz4):
    image_bytes = (build / 'program.a816.json').read_bytes()
    image = json.loads(image_bytes)
    memory = json.loads((build / 'memory.json').read_text())
    compiler = json.loads((build / 'build.json').read_text())
    source = json.loads((build / 'exec-build.json').read_text())
    if digest(image_bytes) != compiler['image_sha256']:
        raise ValueError('Image differs from recorded build: ' + name)
    spans = extents(image, memory)
    payload_size = sum(len(payload) for _, payload, _, _, _ in spans)
    zero_size = sum(size for _, _, size, flags, _ in spans if flags == 1)
    xex = (build / 'of816/Exec-of816.xex').read_bytes()
    labels = {row.split()[2].lstrip('.'): int(row.split()[1], 16)
              for row in (build / 'loader.lbl').read_text().splitlines()}
    chunk = memory['constants']['CHUNK']
    legacy = b''.join(xex_segment(memory['constants']['STAGE'], record) +
                      xex_segment(0x02e2, struct.pack('<H', labels['loader_init']))
                      for record in original_records(spans, memory))
    if not xex.endswith(legacy + xex_segment(0x02e0, struct.pack('<H', labels['loader_start']))):
        raise ValueError('OF816 XEX does not contain the exact native image: ' + name)
    unchanged = len(xex) - len(legacy)
    result = dict(name=name, build_path=str(build.relative_to(ROOT)) if build.is_relative_to(ROOT) else str(build),
                  source_revision=source['revision'], source_dirty=source['dirty'],
                  compiler_revision=compiler['revision'], compiler_override=compiler['override'],
                  optimized=compiler['optimize'], image_sha256=digest(image_bytes),
                  xex_sha256=digest(xex), xex_bytes=len(xex), resident_payload_bytes=payload_size,
                  zero_fill_bytes=zero_size, native_xex_records_bytes=len(legacy),
                  unchanged_xex_bytes=unchanged, staging_chunk_bytes=chunk, cases=[])
    folder = output / name
    folder.mkdir(parents=True, exist_ok=True)
    for kib in sizes:
        blocks = list(split_blocks(spans, kib * 1024))
        for codec in CODECS:
            archive, stats = encode(blocks, codec, lz4)
            path = folder / f'{codec}-{kib}k.ebc'
            path.write_bytes(archive)
            if decode(path.read_bytes(), lz4) != blocks:
                raise ValueError('Round-trip mismatch: ' + str(path))
            # Existing staging costs 8 bytes of record + 4 bytes of XEX header
            # + 6 bytes of INITAD segment per chunk. Future setup/decoder growth
            # is excluded; this is a size model, not an executable XEX.
            wire_bytes = len(archive) + 18 * ((len(archive) + chunk - 1) // chunk)
            projected = unchanged + wire_bytes
            row = dict(codec=codec, maximum_block_bytes=kib * 1024, blocks=len(blocks),
                       archive_bytes=len(archive), metadata_bytes=HEADER.size + BLOCK.size * len(blocks),
                       remaining_percent=round(100 * len(archive) / payload_size, 2),
                       resident_saving_bytes=payload_size - len(archive),
                       modeled_xex_bytes=projected, modeled_xex_saving_bytes=len(xex) - projected,
                       modeled_cart_free_bytes=CART_CAPACITY - projected,
                       archive_path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                       archive_sha256=digest(archive), round_trip='pass', **stats)
            result['cases'].append(row)
            print(f'{name:22} {codec:10} {kib:2} KiB: {len(archive):7,} bytes '
                  f'({row["remaining_percent"]:5.2f}%), modeled XEX {projected:,}', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', required=True, metavar='NAME=BUILD_DIRECTORY')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--block-kib', type=int, nargs='+', default=[1, 16, 32, 64])
    parser.add_argument('--lz4-library', type=Path)
    args = parser.parse_args()
    if any(size not in (1, 16, 32, 64) for size in args.block_kib):
        parser.error('Block sizes must be 1, 16, 32 or 64 KiB')
    inputs = []
    for item in args.input:
        name, separator, directory = item.partition('=')
        if not separator or not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name):
            parser.error('Each input must use a simple unique NAME=BUILD_DIRECTORY')
        if name in {label for label, _ in inputs}:
            parser.error('Duplicate input name: ' + name)
        inputs.append((name, Path(directory).resolve()))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lz4 = LZ4(args.lz4_library)
    report = dict(schema_version=1, scope='Host compression and exact-byte round trips; no boot or target timing.',
                  tool_sha256=digest(Path(__file__).read_bytes()), lz4_version=lz4.version,
                  lz4_library=lz4.path,
                  lz4_library_sha256=digest(Path(lz4.path).read_bytes()) if Path(lz4.path).is_file() else None,
                  zlib_version=zlib.ZLIB_RUNTIME_VERSION, python_version=sys.version,
                  command=['python3', 'tools/measure_boot_compression.py', *sys.argv[1:]],
                  archive_header_bytes=HEADER.size, block_header_bytes=BLOCK.size,
                  cart_xex_capacity=CART_CAPACITY,
                  model='Keep OF816/setup/final RUNAD; replace native records with EBC1 at current staging granularity. Excludes new decoder/setup bytes.',
                  bank_zero_delta=dict(fixed=0, per_task=0), images=[])
    for name, build in inputs:
        report['images'].append(measure(name, build, output, args.block_kib, lz4))
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
