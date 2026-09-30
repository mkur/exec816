"""Independent byte offsets for corrupt-input fixtures, never a guest loader."""
import struct


def inspect(raw):
    at = 0
    positions = {}

    def number(n, label=None):
        nonlocal at
        if label: positions[label] = at
        value = int.from_bytes(raw[at:at+n], 'little')
        assert at+n <= len(raw)
        at += n
        return value

    def name():
        nonlocal at
        end = raw.index(0, at)
        value = raw[at:end].decode('ascii')
        at = end+1
        return value

    assert raw[:8] == b'\x01\x00o65\x00\x02\xa2'
    at = 8
    sections = [(number(4, f'base{i}'), number(4, f'size{i}')) for i in range(4)]
    number(4, 'stack')
    while (option := number(1)):
        assert option >= 2
        at += option-1
    text_at = at
    at += sections[0][1]+sections[1][1]
    imports = [name() for _ in range(number(4, 'wire.imports'))]
    reloc_at = at
    relocs = []
    for section in (2, 3):
        offset = -1
        while (delta := number(1)):
            offset += 254 if delta == 255 else delta
            if delta == 255: continue
            tag_at = at
            tag = number(1)
            index = number(4) if tag & 31 == 0 else 0
            carry_at = at
            carry = number({0x40: 1, 0xa0: 2}.get(tag & 0xe0, 0))
            relocs.append(dict(section=section, offset=offset, tag=tag,
                               index=index, carry=carry, tag_at=tag_at, carry_at=carry_at))
    count = number(4, 'wire.exports')
    exports = {}
    for i in range(count):
        symbol = name()
        segment = number(1, f'export{i}.segment')
        value = number(4, f'export{i}.value')
        exports[symbol] = (segment, value)
    assert at == len(raw)
    descriptor_at = text_at+exports['__a816_o65_compact_v3'][1]
    at = descriptor_at
    number(4, 'descriptor.magic')
    number(2, 'descriptor.abi')
    number(2, 'descriptor.flags')
    signatures = [number(4, f'import{i}.signature') for i in range(len(imports))]
    assert at == text_at+sections[0][1]
    # Consumers compare resident sections, excluding the descriptor trailer.
    sections[0] = (sections[0][0], descriptor_at-text_at)
    return dict(positions=positions, sections=sections, text_at=text_at,
                descriptor_at=descriptor_at, entry=exports['__a816_entry_v2'][1],
                imports=imports, signatures=signatures, relocation_at=reloc_at, relocations=relocs)


def mutations(raw):
    info = inspect(raw)
    p = info['positions']
    # First two cases reject the previous compact-v2 descriptor and magic.
    changes = [(raw.index(b'__a816_o65_compact_v3')+20, ord('2')),
               (p['descriptor.magic']+3, ord('2')), (0, 0), (6, 0), (p['base0'], 1), (p['size0']+3, 255),
               (p['size1']+3, 255), (p['size2']+3, 255), (p['size3'], 1),
               (p['stack'], 1), (p['wire.imports']+3, 1), (p['wire.exports'], 3),
               (p['export0.segment'], 4), (p['export1.value']+3, 1),
               (p['descriptor.magic'], 0), (p['descriptor.abi'], 1),
               (p['descriptor.flags'], 1), (p['import0.signature'], 1),
               (p['export0.value']+3, 1), (p['export1.value'], raw[p['export1.value']] ^ 1)]
    for relocation in info['relocations'][:2]:
        changes.append((relocation['tag_at'], 0xff))
    # Bad standard encoding, import index and nonzero import addend.
    r = next(r for r in info['relocations'] if r['tag'] & 31 == 0)
    changes += [(r['tag_at'], 0x80), (r['tag_at']+1, 255)]
    section_at = info['text_at'] if r['section']==2 else info['text_at']+int.from_bytes(raw[12:16],'little')
    changes.append((section_at+r['offset'], 1))
    return [(offset, value) for offset, value in changes if raw[offset] != value]


def mutation_bytes(raw):
    return b''.join(struct.pack('<IB', offset, value) for offset, value in mutations(raw))
