#!/usr/bin/env python3
"""Inventory the pinned ELSA X 1.05 input and its SDX native dependencies.

This is a host record/ABI audit, not a target loader or an execution certificate.
No opcode-pattern search or application admission is performed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from sdx_file import FormatError, Reader

ELSA_SHA256 = '6b55377eed3c1ef708f5d10e93d28f3d83e2bb755b097c80aa7be6e48e3ec859'
ELSA_ARCHIVE_SHA256 = '30f6861a7fa23b3e2f4a50dd3145a490031629a755be2dbe23f7562ff1da739d'
DRIVER_SYMBOLS = ('H_SFAIL', 'H_XFAIL', 'H_FAIL', 'H_MEMCPY', 'H_MEMSET', 'H_MALLOC', 'H_MFREE')


def inventory(raw):
    """Decode serialized records; retain fixup sites without applying them.

    Absolute INITAD records in the original SDX drivers are inventory only.
    Width validation follows the native loader rules: internal and low-memory
    references are 16-bit, cross-block high-memory references are 24-bit.
    External symbol widths require the dependency export inventory.
    """
    r = Reader(raw)
    blocks, absolute, fixes, exports, records = {}, [], [], [], []
    while r.at < len(raw):
        start, tag = r.at, r.word()
        if tag in (0xfffe, 0xfff9, 0xfff8):
            number, control = r.byte(), r.byte()
            if not number or number in blocks:
                raise FormatError('Duplicate or zero block number')
            origin = 0
            if tag == 0xfff9:
                loaded, allocated = r.word() or 65536, r.word() or 65536
                if control & 128 or loaded > allocated:
                    raise FormatError('Invalid compact block sizes/control')
            elif tag == 0xfff8:
                allocated = int.from_bytes(r.take(4), 'little')
                loaded = 0 if control & 128 else allocated
                if not 0 < allocated < 0x1000000:
                    raise FormatError('Invalid large block size')
            else:
                origin, allocated = r.word(), r.word() or 65536
                loaded = 0 if control & 128 else allocated
            payload_offset = r.at
            r.take(loaded)
            blocks[number] = dict(number=number, tag=tag, control=control,
                                  memory_index=control & 15, origin=origin,
                                  loaded_bytes=loaded, allocated_bytes=allocated,
                                  bss_bytes=allocated-loaded, payload_offset=payload_offset,
                                  alignment=65536 if control & 32 else 256 if control & 64 else 1)
        elif tag in (0xfffa, 0xffff) or tag < 0xfff8:
            address = r.word() if tag in (0xfffa, 0xffff) else tag
            end = r.word()
            if end < address:
                raise FormatError('Invalid absolute segment')
            absolute.append(dict(address=address, bytes=end-address+1, payload_offset=r.at))
            r.take(end-address+1)
        elif tag == 0xfffc:
            block, offset, name = r.byte(), r.word(), r.name()
            if any(e['name'] == name for e in exports):
                raise FormatError('Duplicate export')
            exports.append(dict(name=name, block=block, offset=offset))
        elif tag in (0xfffd, 0xfffb):
            weak = False
            if tag == 0xfffd:
                base = r.byte()
            else:
                encoded = bytearray(r.take(8))
                weak = bool(encoded[7] & 128)
                encoded[7] &= 127
                base = Reader(encoded).name()
            size, begin = r.word(), r.at
            sites, target, position = [], None, 0
            while True:
                op = r.byte()
                if op == 0xfc:
                    break
                if op == 0xfe:
                    target, position = r.byte(), 0
                elif op == 0xff:
                    position += 250
                elif op == 0xfd:
                    target, position = 0, r.word()
                    sites.append(dict(block=0, offset=position))
                else:
                    position += op
                    if target is None:
                        raise FormatError('Fixup has no target')
                    sites.append(dict(block=target, offset=position))
                if position > 65535:
                    raise FormatError('Fixup offset overflow')
                if size and r.at-begin >= size:
                    raise FormatError('Missing fixup terminator')
            if size and r.at-begin != size:
                raise FormatError('Fixup size mismatch')
            fixes.append(dict(base=base, weak=weak, sites=sites))
        else:
            raise FormatError(f'Unsupported record {tag:#06x} at {start:#x}')
        records.append(dict(file_offset=start, tag=tag, bytes=r.at-start))
    for export in exports:
        if export['block'] == 0:
            continue
        block = blocks.get(export['block'])
        if block is None or not 0 <= export['offset']-block['origin'] < block['allocated_bytes']:
            raise FormatError('Export outside allocation')
    for fix in fixes:
        if isinstance(fix['base'], int) and fix['base'] not in blocks and fix['base'] != 0:
            raise FormatError('Undefined fixup base')
        for site in fix['sites']:
            if site['block'] == 0:
                if not any(a['address'] <= site['offset'] and
                           site['offset']+2 <= a['address']+a['bytes'] for a in absolute):
                    raise FormatError('Fixup outside absolute payload')
            elif (site['block'] not in blocks or
                  site['offset']+2 > blocks[site['block']]['loaded_bytes']):
                raise FormatError('Fixup outside initialized block')
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                blocks=list(blocks.values()), absolute_segments=absolute, fixups=fixes,
                exports=exports, records=records,
                imports=list(dict.fromkeys(f['base'] for f in fixes if isinstance(f['base'], str))))


def validate_widths(module, imported_indexes):
    blocks = {b['number']: b for b in module['blocks']}
    occupied, counts = set(), Counter()
    for fix in module['fixups']:
        if isinstance(fix['base'], str):
            base_index = imported_indexes[fix['base']]
        else:
            base_index = blocks[fix['base']]['memory_index'] if fix['base'] else 0
        for site in fix['sites']:
            width = 3 if base_index == 3 and fix['base'] != site['block'] else 2
            if site['block'] and site['offset']+width > blocks[site['block']]['loaded_bytes']:
                raise FormatError('Native fixup outside initialized block')
            for byte in range(site['offset'], site['offset']+width):
                key = site['block'], byte
                if key in occupied:
                    raise FormatError('Overlapping native fixups')
                occupied.add(key)
            site['width'] = width
            counts[width] += 1
    return {str(width): count for width, count in sorted(counts.items())}


def formatter_records(code, fixes):
    """Read inline records at the pinned formatter's imported operand sites.

    JSL context is checked at every site. Reachability is a separate audit.
    """
    records = []
    for fix in fixes:
        if fix['base'] not in ('H_PRINTF', 'H_FPRNTF'):
            continue
        for site in fix['sites']:
            at = site['offset']
            if site['block'] != 1 or not at or code[at-1] != 0x22:
                raise FormatError('Formatter reference is not in reviewed JSL context')
            start = at+3
            stop = code.find(b'\0', start)
            if stop < 0:
                raise FormatError('Unterminated inline format')
            fmt, conversions, count, i = code[start:stop], [], 0, 0
            while i < len(fmt):
                if fmt[i] != 37:
                    i += 1
                    continue
                i += 1
                if i < len(fmt) and fmt[i] == 37:
                    i += 1
                    continue
                prefix = ''
                while i < len(fmt) and chr(fmt[i]) in '0123456789*<!>':
                    prefix += chr(fmt[i])
                    if fmt[i] == 42:
                        count += 1
                    i += 1
                if i == len(fmt) or chr(fmt[i]) not in 'bcdelxpstf':
                    raise FormatError('Unsupported inline formatting command')
                conversions.append(dict(kind=chr(fmt[i]), prefix=prefix))
                count += 1
                i += 1
            end = stop+1+2*count
            if end > len(code):
                raise FormatError('Inline operands outside initialized code')
            records.append(dict(service=fix['base'], call_offset=at-1,
                                format_hex=fmt.hex(), conversions=conversions,
                                operand_sites=list(range(stop+1, end, 2))))
    return records


def audit(binary, dependency_directory=None):
    raw = Path(binary).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ELSA_SHA256:
        raise FormatError('Input is not the pinned ELSA X 1.05 executable')
    module = inventory(raw)
    dependencies, providers = {}, {}
    if dependency_directory:
        directory = Path(dependency_directory)
        for leaf in ('65816.SYS', '65816.OVL', '65816A.OVL', 'EXT816.OVL'):
            path = directory/leaf
            item = inventory(path.read_bytes())
            dependencies[leaf] = item
            by_number = {b['number']: b for b in item['blocks']}
            for export in item['exports']:
                providers.setdefault(export['name'], []).append(dict(
                    file=leaf, memory_index=by_number[export['block']]['memory_index']
                    if export['block'] else 0))
            if leaf in ('65816.OVL', '65816A.OVL'):
                payload = path.read_bytes()
                for name in DRIVER_SYMBOLS:
                    position = payload.find(name.encode().ljust(8, b' '))
                    if position < 0:
                        raise FormatError('Documented driver symbol absent: '+name)
                    providers.setdefault(name, []).append(dict(
                        file=leaf, memory_index=3, registration='runtime S_ADD table',
                        name_file_offset=position,
                        contract='SDX 4.51 Programming Guide 19.1.4 and 19.1.5; not an FFFC export'))
    imports = []
    indexes = {}
    for name in module['imports']:
        candidates = providers.get(name, [])
        kinds = {p['memory_index'] for p in candidates}
        if len(kinds) > 1:
            raise FormatError('Inconsistent native dependency export: '+name)
        # The remaining names are the original cartridge's low-memory data.
        index = next(iter(kinds)) if kinds else 0
        if not candidates and name not in ('COMTAB', 'ERRNO', 'FILE_P'):
            if dependency_directory:
                raise FormatError('Unresolved dependency: '+name)
            index = 3
        indexes[name] = index
        sites = [s for f in module['fixups'] if f['base'] == name for s in f['sites']]
        imports.append(dict(name=name, memory_index=index, providers=candidates,
                            references=len(sites), sites=sites))
    widths = validate_widths(module, indexes)
    code_block = next(b for b in module['blocks'] if b['number'] == 1)
    code = raw[code_block['payload_offset']:code_block['payload_offset']+code_block['loaded_bytes']]
    # Exact instruction operands, reviewed from the pinned bootstrap. These
    # checks are not a complete reachable-instruction or self-modification audit.
    reviewed = [
        (0x46, 'f400002b', 'PEA low block base; PLD selects the private direct page'),
        (0x6f2, 'a20f057a9a5a', 'LDX low block + $050F; preserve Y while TXS selects its native stack'),
        (0x11f7, 'a9feffa2ffff', 'Largest-free-block query in 32-bit AX'),
        (0x5fa, '8de106', 'Bootstrap writes the two MVN bank operands at block+$06E1'),
        (0x1201, '30288d05908e0790a0000022000000',
         'Store the query result without changing AX; request that entire block through H_MALLOC'),
        (0x1d82, '8fd40000ad759f8fd60000e22022000000afd40000',
         'Floating-point conversion writes/reads physical bank-zero FR0 around H_IFP32'),
    ]
    for offset, expected, _ in reviewed:
        if code[offset:offset+len(bytes.fromhex(expected))] != bytes.fromhex(expected):
            raise FormatError(f'Reviewed bootstrap preimage changed at {offset:#x}')
    return dict(format='exec816-elsax105-input-audit-v1', status='input-and-abi-inventory-complete',
                execution_admitted=False, full_instruction_audit=False,
                module=module, imports=imports, fixup_width_counts=widths,
                dependencies=dependencies, dependency_inventory_present=bool(dependencies),
                inline_formats=formatter_records(code, module['fixups']),
                upstream=dict(url='https://drac030.krap.pl/elsax105.arc',
                              archive_sha256=ELSA_ARCHIVE_SHA256),
                reviewed_bootstrap=[dict(offset=o, bytes_hex=e, observation=t) for o,e,t in reviewed],
                memory=dict(initialized_upper_bytes=24320, upper_bss_bytes=16513,
                            allocated_upper_bytes=40833, declared_bank_zero_bytes=1296,
                            direct_page_bytes=256, scratch_bytes=16, native_stack_bytes=1024,
                            total_declared_bytes=42129,
                            additional_dynamic_memory='Queries and requests the largest free upper block',
                            reservation_delta_this_audit=dict(fixed=0, per_task=0, idle=0),
                            port_budget='Not established; guards, alignment, IRQ/NMI headroom and Task stack reuse require measurement'),
                limitations=['No native execution admission or production loader changes',
                             'Serialized fixup sites are not proof of reachable instructions',
                             'Complete control-flow, computed dispatch, SMC and interrupt/cancellation audits remain required'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--dependencies', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.binary, args.dependencies)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'], ':', len(result['imports']), 'imports;', result['fixup_width_counts'], 'fixup widths')
