"""Inventory the pinned EDX control flow and reviewed RAWCON binding.

This host decoder does not admit EDX to Exec or emulate a CPU. Dispatch tables,
the error continuation and six self-modified JMP veneers are reviewed roots.
Dynamic pointer aliasing, stack bounds and all runtime paths remain unqualified.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from sdx_file import FormatError, parse, place
from sdx_md5_audit import OPCODES


EDX_SHA256 = '1f9b1082bc6ad53f8b7cbac15044f434454c942a3b13f7f6b428e7b8b0ba8f69'
RAWCON = {
    0x0E2: (3, 'close'),
    0x0E5: (1, 'open'),
    0x0ED: (9, 'clear'),
    0x0F0: (13, 'get_character'),
    0x10C: (15, 'put_character'),
    0x120: (17, 'special'),
}
WRITE_OPS = {'STA', 'STX', 'STY', 'INC', 'DEC', 'ASL', 'LSR', 'ROL', 'ROR'}
DECODER = {**OPCODES, 0x6C: ('JMP', 'ind', 3)}


def word(memory, address):
    if address < 0 or address + 2 > len(memory):
        raise FormatError('Word outside image')
    return int.from_bytes(memory[address:address + 2], 'little')


def dispatch_tables(memory, pointer_table, counts, lower, upper):
    """EDX checks entries 1..count-1, with separate BREAK and fallback words."""
    tables = []
    for mode in range(3):
        address = word(memory, pointer_table + 2 * mode)
        count = memory[counts + mode]
        if not count or not lower <= address < address + 4 * count + 2 <= upper:
            raise FormatError('Dispatch table outside initialized block')
        entries = []
        for index in range(count):
            at = address + 4 * index
            target = word(memory, at)
            if not lower <= target < upper:
                raise FormatError('Dispatch target outside initialized block')
            entries.append(dict(target=target, key=memory[at + 2],
                                modifiers=memory[at + 3], break_entry=index == 0))
        fallback = word(memory, address + 4 * count)
        if not lower <= fallback < upper:
            raise FormatError('Dispatch fallback outside initialized block')
        tables.append(dict(mode=mode, address=address, entries=entries,
                           fallback=fallback))
    return tables


def decode(memory, lower, upper, roots, imports, veneers, indirect):
    """Conservative traversal: both branch arms and every supplied root."""
    pending, code, external = list(roots), {}, []
    while pending:
        pc = pending.pop()
        if pc in code:
            continue
        if not lower <= pc < upper:
            raise FormatError(f'Control flow outside initialized block: {pc:#x}')
        op = memory[pc]
        if op not in DECODER:
            raise FormatError(f'Unknown opcode at {pc:#x}: {op:#x}')
        name, mode, size = DECODER[op]
        if pc + size > upper:
            raise FormatError('Truncated instruction')
        operand = int.from_bytes(memory[pc + 1:pc + size], 'little')
        instruction = dict(instruction=name, mode=mode, operand=operand, bytes=size)
        code[pc] = instruction
        after = pc + size
        if pc in veneers:
            if name != 'JMP' or mode != 'abs' or operand != 0xFFFF:
                raise FormatError('RAWCON veneer differs from reviewed JMP')
            instruction['rawcon'] = veneers[pc]
            continue
        if name in ('JSR', 'JMP'):
            if mode == 'ind':
                if indirect.get(pc) != operand:
                    raise FormatError(f'Unreviewed indirect jump at {pc:#x}')
                continue
            if operand in imports:
                external.append(dict(offset=pc - lower, symbol=imports[operand],
                                     tail=name == 'JMP'))
                if imports[operand] == 'U_FAIL':
                    continue
            else:
                pending.append(operand)
            if name == 'JMP':
                continue
        if name == 'RTS':
            continue
        if mode == 'rel':
            pending.append(after + (operand if operand < 128 else operand - 256))
        pending.append(after)
    return code, sorted(external, key=lambda call: call['offset'])


def audit(raw, start=0x3000):
    if hashlib.sha256(raw).hexdigest() != EDX_SHA256:
        raise FormatError('Unknown EDX application identity')
    program = parse(raw)
    symbols = {name: 0xF000 + index * 16
               for index, name in enumerate(program.imports)}
    memory, layout = place(program, start, 0xE000, symbols)
    base = layout['blocks'][1]
    end = base + program.blocks[0].size
    tables = dispatch_tables(memory, base + 0x14D3, base + 0x14D9, base, end)
    roots = [base, word(memory, base + 0x141E)]
    for table in tables:
        roots += [entry['target'] for entry in table['entries']]
        roots.append(table['fallback'])
    veneers = {base + offset: dict(table_offset=slot, function=name)
               for offset, (slot, name) in RAWCON.items()}
    code, calls = decode(memory, base, end, roots,
                         {address: name for name, address in symbols.items()},
                         veneers, {base + 0x242: 0x87})
    bindings = []
    for offset in range(0, 24, 4):
        source = word(memory, base + 0x71 + offset)
        target = word(memory, base + 0x73 + offset)
        if target - 1 not in veneers:
            raise FormatError('Unreviewed bootstrap write to code')
        expected = veneers[target - 1]['table_offset']
        if source != symbols['_RAWCON'] + expected:
            raise FormatError('RAWCON bootstrap binding mismatch')
        bindings.append(dict(source_table_offset=expected,
                             target_operand_offset=target - base,
                             function=veneers[target - 1]['function']))
    relocations = {(block, offset): fix.base for fix in program.fixups
                   for block, offset in fix.sites}
    accesses, hardware, dp = [], [], set()
    for pc, item in sorted(code.items()):
        mode, operand = item['mode'], item['operand']
        if mode in ('dp', 'dpx', 'dpy', 'indx', 'indy'):
            dp.add(operand)
        if item['instruction'] in ('JSR', 'JMP') or mode in ('imp', 'imm', 'rel'):
            continue
        row = dict(offset=pc - base, **item)
        row['write'] = item['instruction'] in WRITE_OPS
        if mode.startswith('abs'):
            row['relocation'] = relocations.get((1, pc + 1 - base))
            if row['relocation'] is None and 0xD000 <= operand <= 0xD7FF:
                hardware.append(row)
        accesses.append(row)
    for table in tables:
        table['offset'] = table.pop('address') - base
        table['fallback_offset'] = table.pop('fallback') - base
        for entry in table['entries']:
            entry['offset'] = entry.pop('target') - base
    shared = sorted({item['operand'] for item in accesses
                     if item['mode'].startswith('abs')
                     and item['relocation'] is None
                     and not 0xD000 <= item['operand'] <= 0xD7FF})
    occupied = Counter(byte for pc, item in code.items()
                       for byte in range(pc, pc + item['bytes']))
    return dict(
        status='reviewed-static-inventory-complete', execution_admitted=False,
        scope='Reviewed control-flow roots and veneer binding; no pointer-alias, '
              'stack-bound or complete runtime-safety proof',
        sha256=EDX_SHA256, bytes=len(raw), placement=layout,
        blocks=[dict(number=block.number, control=block.control, origin=block.offset,
                     allocated_bytes=block.size, initialized_bytes=len(block.data))
                for block in program.blocks],
        relocation_sites=sum(len(fix.sites) for fix in program.fixups),
        imports=list(program.imports), import_calls=calls,
        dispatch_tables=tables, rawcon_bindings=bindings,
        trap_root_offset=word(memory, base + 0x141E) - base,
        instruction_count=len(code), instruction_bytes=len(occupied),
        overlapping_instruction_bytes=[byte - base for byte, count in occupied.items()
                                       if count > 1],
        instructions_sha256=hashlib.sha256(json.dumps(
            {str(pc - base): item for pc, item in sorted(code.items())},
            sort_keys=True).encode()).hexdigest(),
        direct_page_operands=sorted(dp), unrelocated_absolute_addresses=shared,
        hardware_accesses=hardware,
        processor_control=[dict(offset=pc - base, **item) for pc, item in sorted(code.items())
                           if item['instruction'] in ('SEI', 'CLI', 'SED', 'CLD', 'TXS')],
        memory_accesses=accesses,
        instruction_offsets=[pc - base for pc in sorted(code)],
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path)
    parser.add_argument('--start', type=lambda value: int(value, 0), default=0x3000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.application.read_bytes(), args.start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in
                      ('status', 'instruction_count', 'relocation_sites', 'imports')}))
