"""Checked fixed-image manifests and ordinary XEX staging records."""
import hashlib
import json
import struct

from generate_memory import require, integer


def extents(image, memory):
    """Normalize compiler regions; each descriptor fits within one native bank."""
    result = []
    for segment in image['segments']:
        integer(segment['address'], 0, 0xffffff, 'image address')
        require(len(segment['bytes']) > 0, 'Empty image segment')
        # A fixed disk component keeps its banks reserved and cleared during
        # boot. Its native bootstrap publishes code only after a complete load.
        deferred = segment.get('deferred', False)
        result.append((segment['address'], b'' if deferred else bytes(segment['bytes']), len(segment['bytes']),
                       1 if deferred else 2 if segment['executable'] else 0, 2))
    for zero in image['zero_fill']:
        integer(zero['address'], 0, 0xffffff, 'image address')
        integer(zero['size'], 1, 0x1000000, 'image size')
        result.append((zero['address'], b'', zero['size'], 1, 2))
    # Compiler routines and data objects are separate regions. Coalesce only
    # contiguous regions with identical wire attributes; object count must not
    # consume manifest capacity. Preserve gaps and initialized/zero/code kinds.
    merged = []
    for region in sorted(result):
        address, payload, size, flags, owner = region
        if merged and merged[-1][3:] == (flags,owner) and merged[-1][0]+merged[-1][2] == address:
            previous = merged.pop()
            merged.append((previous[0],previous[1]+payload,previous[2]+size,flags,owner))
        else:
            merged.append(region)
    return validate_extents(merged, memory)


def reserved_banks(memory):
    return {bank for region in [*memory.get('upper_reservations',[]),
                           *([memory['image_data']] if 'image_data' in memory else [])]
            for bank in range(region['address'] >> 16,
                              ((region['address']+region['size']-1) >> 16)+1)}


def validate_extents(regions, memory):
    result, claims = [], {bank:2 for bank in reserved_banks(memory)}
    c = memory['constants']
    previous_end = 0
    for address, payload, size, flags, owner in sorted(regions):
        integer(address, 0, 0xffffff, 'image address')
        integer(size, 1, 0x1000000, 'image size')
        require(address + size <= 0x1000000 and address >= previous_end, 'Image overlap/overflow')
        previous_end = address + size
        require(all(address+size<=r['address'] or address>=r['address']+r['size']
                    for r in memory.get('upper_reservations',[])), 'Image overlaps upper kernel reservation')
        require(flags in (0, 1, 2) and owner in (2, 3, 4), 'Invalid extent kind/owner')
        require((flags == 1 and not payload) or (flags != 1 and len(payload) == size),
                'Extent payload length mismatch')
        arena = memory.get('image_data')
        if arena and address < arena['address']+arena['size'] and arena['address'] < address+size:
            require(flags != 2 and owner == 2 and arena['address'] <= address
                    and address+size <= arena['address']+arena['size'],
                    'Image conflicts with global data arena')
        for bank in range(address >> 16, ((address + size - 1) >> 16) + 1):
            require(bank < c['MAX_BANKS'], 'Image outside MAX_BANKS')
            if bank == 0:
                require(False, 'Resident image payload in bank zero')
            else:
                require(bank in memory['usable_banks'], 'Unavailable image bank')
                require(bank not in claims or claims[bank] == owner, 'Conflicting bank owners')
                claims[bank] = owner
        offset = 0
        while offset < size:
            at = address + offset
            n = min(size - offset, 0x10000 - (at & 0xffff), 0xffff)
            result.append((at, payload[offset:offset+n] if flags != 1 else b'', n, flags, owner))
            offset += n
    require(len(result) <= c['MAX_EXTENTS'], 'Manifest extent capacity exceeded')
    return result


def manifest(image, memory):
    spans = extents(image, memory)
    c = memory['constants']
    seed = bytearray(c['TABLE_BYTES'])
    seed[:4] = bytes([2, 0, 1, 0])
    for bank in memory['usable_banks']:
        seed[bank*4] = 1
    for bank in reserved_banks(memory):
        seed[bank*4:bank*4+4] = struct.pack('<BBH', 2, 0, 2)
    for address, _, size, flags, owner in spans:
        bank = address >> 16
        if bank:
            seed[bank*4:bank*4+4] = struct.pack('<BBH', 2, 0, owner)
    require(any(flags == 2 and address <= image['entry'] < address + size
                for address, _, size, flags, _ in spans), 'Entry outside executable extent')
    descriptors = b''.join(address.to_bytes(3, 'little') + bytes([flags]) + struct.pack('<HH', size, owner)
                           for address, _, size, flags, owner in spans)
    header = b'EBM1' + struct.pack('<HHH', 1, c['MAX_BANKS'], len(spans))
    header += image['entry'].to_bytes(3, 'little') + b'\0'
    size = 32 + len(seed) + len(descriptors)
    header += struct.pack('<H', size)
    identity = hashlib.sha256(json.dumps(memory, sort_keys=True).encode() + header + seed + descriptors
                              + b''.join(p for _,p,_,_,_ in spans)).digest()[:16]
    return header + identity + seed + descriptors, spans


def records(spans, memory):
    for index, (_, payload, size, flags, _) in enumerate(spans):
        for offset in range(0, size, memory['constants']['CHUNK']):
            count = min(size-offset, memory['constants']['CHUNK'])
            yield struct.pack('<HHHBB', index, offset, count, flags, 0) + (
                payload[offset:offset+count] if flags != 1 else b'')


def package(loader, manifest_bytes, spans, memory, labels, resident):
    from native_program import xex_segment
    c = memory['constants']
    # The first load address is itself a guarded RUNAD entry, including on hosts
    # that default RUNAD to the first segment. Setup/consume share one callback.
    result = b'\xff\xff' + xex_segment(c['LOADER'], loader)
    result += xex_segment(0x02e0, struct.pack('<H', labels['loader_start']))
    result += xex_segment(memory['regions']['resident'][0], resident)
    result += xex_segment(c['MANIFEST'], manifest_bytes)
    result += xex_segment(c['STAGE'], bytes(8))
    result += xex_segment(0x02e2, struct.pack('<H', labels['loader_init']))
    for record in records(spans, memory):
        result += xex_segment(c['STAGE'], record)
        result += xex_segment(0x02e2, struct.pack('<H', labels['loader_init']))
    result += xex_segment(0x02e0, struct.pack('<H', labels['loader_start']))
    return result


def split_setup(segments, memory, labels):
    """Identify the generated setup callback before any native payload work."""
    c = memory['constants']
    require(len(segments) >= 9, 'Missing native setup/payload records')
    prefix, payload = segments[:6], segments[6:]
    run = (0x02e0, struct.pack('<H', labels['loader_start']))
    init = (0x02e2, struct.pack('<H', labels['loader_init']))
    require(prefix[0][0] == c['LOADER'] and 0 < len(prefix[0][1]) <= c['LOADER_BYTES']
            and prefix[1] == run and prefix[2][0] == memory['regions']['resident'][0]
            and prefix[3][0] == c['MANIFEST'] and prefix[3][1][:4] == b'EBM1'
            and prefix[4] == (c['STAGE'], bytes(8)) and prefix[5] == init,
            'Invalid native setup boundary')
    require(payload[-1] == run and len(payload) % 2 == 1,
            'Invalid native payload/final RUNAD')
    for index in range(0, len(payload)-1, 2):
        address, record = payload[index]
        require(address == c['STAGE'] and len(record) >= 8 and payload[index+1] == init,
                'Unexpected native payload destination/callback')
        _, _, count, kind, reserved = struct.unpack('<HHHBB', record[:8])
        require(0 < count <= c['CHUNK'] and kind in (0, 1, 2) and reserved == 0
                and len(record) == (8 if kind == 1 else 8+count),
                'Invalid native payload record')
    return prefix, payload


def emit(output, image, memory, labels, probe=False):
    """Assemble a bootstrap bound to the fully validated fixed image."""
    from native_program import command, ROOT
    manifest_bytes, spans = manifest(image, memory)
    (output / 'manifest.bin').write_bytes(manifest_bytes)
    (output / 'loader-image.inc').write_text(
        f'IMAGE_MANIFEST_SIZE = {len(manifest_bytes)}\nIMAGE_EXTENTS = {len(spans)}\nHOST_START = {labels["start"]}\n')
    c = memory['constants']
    (output / 'loader.cfg').write_text(
        f'MEMORY {{ RAM: start=${c["LOADER"]:x}, size=${c["LOADER_BYTES"]:x}, file=%O; }} '
        'SEGMENTS { LOADER: load=RAM, type=ro; }\n')
    command(['ca65', '-I', output, '--bin-include-dir', output, '-D', f'LOADER_PROBE={int(probe)}',
             '-l', output/'loader.lst', '-o', output/'loader.o', ROOT/'platform/altirraos/loader.s'])
    command(['ld65', '-C', output/'loader.cfg', '-o', output/'loader.bin',
             '-Ln', output/'loader.lbl', output/'loader.o'])
    loader_labels = {line.split()[2].lstrip('.'):int(line.split()[1],16)
                     for line in (output/'loader.lbl').read_text().splitlines()}
    payload = package((output/'loader.bin').read_bytes(), manifest_bytes, spans, memory,
                      loader_labels, (output/'hosted.bin').read_bytes())
    return payload, loader_labels
