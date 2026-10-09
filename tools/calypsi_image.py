"""Read the linked Calypsi ELF subset used by the standalone C target."""
import struct
from pathlib import Path

from native_program import require, sha256


def check_layout(path, expected):
    """Validate target-emitted constants, not the frontend's host-like layout."""
    raw = Path(path).read_bytes()
    require(len(raw) >= 52 and raw[:7] == b'\x7fELF\x01\x01\x01', 'Expected ELF32 layout probe')
    h = struct.unpack_from('<HHIIIIIHHHHHH', raw, 16)
    require(h[0:2] == (1, 257) and h[10] == 40 and h[5]+h[10]*h[11] <= len(raw), 'Invalid layout object')
    rows = [struct.unpack_from('<IIIIIIIIII', raw, h[5]+i*h[10]) for i in range(h[11])]
    require(h[12] < len(rows), 'Missing layout section names')
    names = rows[h[12]]
    names = raw[names[4]:names[4]+names[5]]
    sections = [r for r in rows if names[r[0]:].split(b'\0', 1)[0] == b'exec_layout']
    require(len(sections) == 1, 'Missing emitted C layout')
    row = sections[0]
    require(row[1] == 1 and row[5] == 2*len(expected) and row[4]+row[5] <= len(raw), 'Invalid emitted C layout')
    values = struct.unpack_from('<'+'H'*len(expected), raw, row[4])
    for (expression, target), actual in zip(expected, values):
        require(actual == target, f'C ABI mismatch: {expression} = {actual}, expected {target}')
    return dict(expected)


def read_image(path, task_entries=(), base_bank=12):
    path = Path(path)
    raw = path.read_bytes()
    require(1 <= base_bank <= 251, 'Invalid C link bank')
    code_base = base_bank << 16
    data_base, extra_base, table_base = (code_base+n*65536 for n in (1,2,3))

    more_code_base = code_base+4*65536

    def bytes_at(offset, size):
        require(0 <= offset <= offset+size <= len(raw), 'Truncated Calypsi ELF')
        return raw[offset:offset+size]

    def unpack(fmt, offset):
        return struct.unpack(fmt, bytes_at(offset, struct.calcsize(fmt)))

    require(bytes_at(0, 7) == b'\x7fELF\x01\x01\x01', 'Expected little-endian ELF32')
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, shstrings = unpack('<HHIIIIIHHHHHH', 16)
    require((kind, machine, version, ehsize, phsize, shsize) == (2, 257, 1, 52, 32, 40),
            'Unsupported Calypsi ELF header')
    require(0 < phnum <= 16 and 0 < shnum <= 256, 'Invalid ELF table size')
    sections = [unpack('<IIIIIIIIII', shoff+i*shsize) for i in range(shnum)]
    symbols = {}
    functions = set()
    for row in sections:
        if row[1] != 2:
            continue
        require(row[9] == 16 and row[5] % 16 == 0 and row[6] < shnum, 'Invalid ELF symbols')
        names = sections[row[6]]
        require(names[1] == 3, 'Invalid ELF string table')
        strings = bytes_at(names[4], names[5])
        for offset in range(row[4], row[4]+row[5], 16):
            name, value, size, info, other, index = unpack('<IIIBBH', offset)
            require(name < len(strings) and b'\0' in strings[name:], 'Invalid ELF symbol name')
            name = strings[name:].split(b'\0', 1)[0].decode('ascii')
            if not name:
                continue
            require(index != 0, 'Unresolved C symbol: ' + name)
            require(name not in symbols or symbols[name] == value, 'Ambiguous C symbol: ' + name)
            symbols[name] = value
            if info & 15 == 2:
                functions.add(name)
    require(symbols.get('main') == entry and 'main' in functions, 'C entry must be main')
    require(symbols.get('_Dp') == 0 and symbols.get('_Vfp') == 16 and
            symbols.get('_DirectPageStart') == 0 and symbols.get('_NearBaseAddress') == 0,
            'C runtime must use task-relative lower DP and DBR zero')
    segments, info, direct_page = [], None, False
    for number in range(phnum):
        ptype, offset, address, physical, size, reserved, permissions, alignment = unpack('<IIIIIIII', phoff+number*phsize)
        require(ptype == 1 and address == physical and size <= reserved, 'Unsupported ELF load segment')
        payload = bytes_at(offset, size)
        if address == 0:
            require(not direct_page and not payload and reserved == 128 and permissions == 6,
                    'Unexpected fixed bank-zero C storage')
            direct_page = True
        elif address == 0x100:
            require(info is None and len(payload) == 16 and reserved == 16 and permissions == 4,
                    'Invalid host-only C metadata')
            info = struct.unpack('<IIII', payload)
        else:
            require((address in (code_base, extra_base, more_code_base) and reserved == 65536 and
                     (permissions == 5 or (permissions == 4 and not payload))) or
                    (data_base <= address <= address+reserved <= extra_base and permissions in (4, 6)) or
                    (address == table_base and reserved == 65536 and permissions == 4),
                    'C sections must fit the standalone upper-bank layout')
            if payload:
                segments.append(dict(address=address, bytes=list(payload), writable=bool(permissions & 2), executable=bool(permissions & 1)))
    # Calypsi may link the spill helper's three-byte task-relative indirect
    # pointer after its fixed pseudo-registers. Both are inside caller DP;
    # reject unrecognized layouts instead of changing the kernel reservation.
    workspace = info[3] if info is not None else 0
    require(direct_page and info is not None and info[0] == 0x31434345 and
            (workspace == 20 or (workspace == 23 and symbols.get('_FillInd') == 20)),
            'C runtime register allocation changed')
    _, bss, bss_size, workspace = info
    require(bss_size == 0 or data_base <= bss < bss+bss_size <= extra_base, 'C BSS outside data bank')
    zero_fill = [dict(address=bss, size=bss_size, writable=True)] if bss_size else []
    extents = sorted((s['address'], s['address']+len(s['bytes'])) for s in segments)
    extents += [(s['address'], s['address']+s['size']) for s in zero_fill]
    extents.sort()
    require(all(a[1] <= b[0] for a, b in zip(extents, extents[1:])),
            'Overlapping C storage')
    for name in ('main', *task_entries):
        require(name in functions and any(s['executable'] and s['address'] <= symbols[name] < s['address']+len(s['bytes']) for s in segments),
                'C Task entry is not a linked function: ' + name)
    require(len(set(task_entries)) == len(task_entries), 'Duplicate C Task entry')
    return dict(segments=segments, zero_fill=zero_fill,
                task_entries=[symbols[name] for name in task_entries], symbols=symbols,
                provenance=dict(format='calypsi65816-standalone-v1', elf_sha256=sha256(path),
                    entry=entry, task_entries=list(task_entries), dp_workspace_bytes=workspace,
                    readonly_table_banks=[base_bank+3] if any(s['address']==table_base for s in segments) else [],
                    stack_checks=False, bank_zero_delta=dict(fixed=0, per_task=0)))
