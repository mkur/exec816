"""Inspect and place conventional relocatable SDX records (host audit/oracle).

SDX 4.50 Programming Guide, chapter 2. This does not certify that the contained
instructions can execute in an Exec guest. Absolute and extended-memory records
are deliberately outside this initial subset.
"""
from dataclasses import dataclass
import struct


class FormatError(ValueError):
    pass


@dataclass(frozen=True)
class Block:
    number: int
    control: int
    offset: int
    size: int
    data: bytes


@dataclass(frozen=True)
class Fixup:
    base: int | str
    sites: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Export:
    name: str
    block: int
    offset: int


@dataclass(frozen=True)
class File:
    blocks: tuple[Block, ...]
    fixups: tuple[Fixup, ...]
    exports: tuple[Export, ...]

    @property
    def imports(self):
        return tuple(dict.fromkeys(f.base for f in self.fixups if isinstance(f.base, str)))


class Reader:
    def __init__(self, data):
        self.data, self.at = bytes(data), 0

    def take(self, count):
        if count < 0 or count > len(self.data)-self.at:
            raise FormatError(f'Truncated record at {self.at:#x}')
        start = self.at
        self.at += count
        return self.data[start:self.at]

    def byte(self):
        return self.take(1)[0]

    def word(self):
        return int.from_bytes(self.take(2), 'little')

    def name(self):
        raw = self.take(8)
        if not all(32 <= c < 127 for c in raw) or not raw.rstrip(b' '):
            raise FormatError('Unsupported or invalid symbol name')
        return raw.decode('ascii').rstrip(' ')


def parse(data):
    if not 8 <= len(data) <= 65536:
        raise FormatError('Invalid SDX file length')
    r = Reader(data)
    blocks, fixups, exports = {}, [], []
    while r.at < len(r.data):
        tag = r.word()
        if tag == 0xfffe:
            number, control, offset, size = struct.unpack('<BBHH', r.take(6))
            if not number or number in blocks or control & 0x3f or not size:
                raise FormatError('Unsupported, empty or duplicate block')
            blocks[number] = Block(number, control, offset, size,
                                   b'' if control & 0x80 else r.take(size))
        elif tag == 0xfffc:
            block, offset = r.byte(), r.word()
            name = r.name()
            if any(e.name == name for e in exports):
                raise FormatError('Duplicate export')
            exports.append(Export(name, block, offset))
        elif tag in (0xfffd, 0xfffb):
            base = r.byte() if tag == 0xfffd else r.name()
            size, start = r.word(), r.at
            sites, target, position = [], None, 0
            while True:
                op = r.byte()
                if op == 0xfc:
                    break
                if op == 0xfd:
                    raise FormatError('Absolute fixup outside supported subset')
                if op == 0xfe:
                    target, position = r.byte(), 0
                elif op == 0xff:
                    position += 250
                else:
                    position += op
                    if target is None:
                        raise FormatError('Fixup has no target block')
                    sites.append((target, position))
                if position > 65535:
                    raise FormatError('Fixup offset overflow')
                if size and r.at-start >= size:
                    raise FormatError('Missing fixup terminator within record')
            if size and r.at-start != size:
                raise FormatError('Fixup record size mismatch')
            fixups.append(Fixup(base, tuple(sites)))
        else:
            raise FormatError(f'Unsupported SDX record {tag:#x}')
    if not blocks:
        raise FormatError('No program blocks')
    touched = set()
    for f in fixups:
        if isinstance(f.base, int) and f.base not in blocks:
            raise FormatError('Undefined relocation base')
        for target, offset in f.sites:
            if target not in blocks or offset+2 > blocks[target].size:
                raise FormatError('Fixup outside target block')
            if blocks[target].control & 0x80:
                raise FormatError('Fixup into uninitialized block')
            for byte in (offset, offset+1):
                if (target, byte) in touched:
                    raise FormatError('Overlapping fixups')
                touched.add((target, byte))
    for e in exports:
        if e.block not in blocks or not 0 <= e.offset-blocks[e.block].offset < blocks[e.block].size:
            raise FormatError('Export outside its block')
    return File(tuple(blocks.values()), tuple(fixups), tuple(exports))


def place(program, start, end, symbols):
    """Return a bank image and placement metadata; all addresses are near.

    The SDX block offset describes the assembled origin. Both references to a
    block and exports are adjusted by placed_address - assembled_origin.
    """
    if not 0 <= start < end <= 65536:
        raise FormatError('Invalid placement interval')
    missing = set(program.imports)-symbols.keys()
    if missing:
        raise FormatError('Undefined imports: '+', '.join(sorted(missing)))
    if any(not 0 <= symbols[n] <= 65535 for n in program.imports):
        raise FormatError('Import address outside bank')
    image, addresses, blocks = bytearray(65536), {}, {}
    cursor = start
    for b in program.blocks:
        if b.control & 0x40:
            cursor = (cursor+255) & ~255
        if cursor+b.size > end:
            raise FormatError('Program exceeds placement interval')
        addresses[b.number], blocks[b.number] = cursor, b
        image[cursor:cursor+len(b.data)] = b.data
        cursor += b.size
    for fix in program.fixups:
        if isinstance(fix.base, int):
            base = addresses[fix.base]-blocks[fix.base].offset
        else:
            base = symbols[fix.base]
        for target, offset in fix.sites:
            at = addresses[target]+offset
            value = int.from_bytes(image[at:at+2], 'little')+base
            if not 0 <= value <= 65535:
                raise FormatError('Relocated address outside bank')
            image[at:at+2] = value.to_bytes(2, 'little')
    exports = {e.name: addresses[e.block]+e.offset-blocks[e.block].offset
               for e in program.exports}
    return bytes(image), dict(blocks=addresses, end=cursor, exports=exports)
