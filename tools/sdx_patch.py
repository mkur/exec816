"""Transactional host oracle for the audited SDX patch loader.

This prepares private bank images; it never admits an executable to Exec.
All manifests are currently patch-probe-only. Runtime selection uses size and
CRC32; host builds additionally require the pinned SHA-256. Never edit the
source SDX file or relocate the replacements a second time.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zlib

from sdx_file import FormatError, parse, place


class PatchError(FormatError):
    pass


@dataclass(frozen=True)
class PreparedModule:
    image: bytes
    layout: dict
    record: dict


def manifests(directory):
    return [json.loads(p.read_text()) for p in sorted(Path(directory).glob('*.json'))]


def selectors(catalog):
    """Validate the complete selector set, including unused companion modules."""
    found, ids = {}, set()
    for manifest in catalog:
        if manifest['schema_version'] != 1 or manifest['personality_abi'] != 1:
            raise PatchError('Unsupported patch manifest ABI')
        if manifest['id'] in ids or manifest['revision'] < 1:
            raise PatchError('Duplicate manifest ID or invalid revision')
        ids.add(manifest['id'])
        for module in manifest['modules']:
            if not 8 <= module['bytes'] <= 65536:
                raise PatchError('Invalid module size')
            for key, length in (('crc32', 8), ('sha256', 64)):
                if len(module[key]) != length or any(c not in '0123456789abcdef' for c in module[key]):
                    raise PatchError('Invalid '+key)
            key = module['bytes'], int(module['crc32'], 16)
            if key in found:
                raise PatchError('Ambiguous size/CRC32 selector')
            found[key] = manifest, module
    return found


def select(raw, catalog, *, verify_sha=True):
    pair = selectors(catalog).get((len(raw), zlib.crc32(raw)))
    if pair is None:
        raise PatchError('Unsupported module size/CRC32')
    if verify_sha and hashlib.sha256(raw).hexdigest() != pair[1]['sha256']:
        raise PatchError('Host SHA-256 pin differs')
    return pair


def validate_patches(program, module):
    """Check original bytes, whole-word intersections and replacement fixups."""
    blocks = {b.number: b for b in program.blocks}
    occupied, ids = set(), set()
    validated = []
    for patch in module['patches']:
        if patch['id'] in ids:
            raise PatchError('Duplicate patch ID')
        ids.add(patch['id'])
        block, offset = patch['block'], patch['offset']
        expected, replacement = bytes.fromhex(patch['expected']), bytes.fromhex(patch['replacement'])
        if (block not in blocks or not expected or offset < 0
                or offset+len(expected) > len(blocks[block].data)
                or len(expected) != len(replacement)):
            raise PatchError('Patch outside initialized block or changes its size')
        if blocks[block].data[offset:offset+len(expected)] != expected:
            raise PatchError('Original patch preimage differs: '+patch['id'])
        span = {(block, i) for i in range(offset, offset+len(expected))}
        if occupied & span:
            raise PatchError('Overlapping patches')
        occupied |= span
        actual = []
        for fixup in program.fixups:
            for target, at in fixup.sites:
                if (target, at) in span or (target, at+1) in span:
                    if (target, at) not in span or (target, at+1) not in span:
                        raise PatchError('Patch splits a relocation word')
                    actual.append(dict(base=fixup.base, offset=at))
        if actual != patch['intersections']:
            raise PatchError('Undeclared relocation/import intersection')
        touched = set()
        for fixup in patch['fixups']:
            kind, at = fixup['kind'], fixup['offset']
            if kind not in ('block16', 'symbol16', 'relative8', 'direct_page16'):
                raise PatchError('Unknown replacement fixup kind')
            width = 1 if kind == 'relative8' else 2
            sites = set(range(at, at+width))
            if at < 0 or at+width > len(replacement) or sites & touched:
                raise PatchError('Replacement fixup overlaps or exceeds patch')
            if any(replacement[i] for i in sites):
                raise PatchError('Replacement fixup needs zero placeholders')
            touched |= sites
            if kind in ('block16', 'relative8'):
                target = blocks.get(fixup['block'])
                if target is None or not 0 <= fixup['addend'] < target.size:
                    raise PatchError('Replacement target outside block')
            elif kind == 'direct_page16':
                if not 0 <= fixup['addend'] < 255:
                    raise PatchError('Direct-page pointer outside page')
            elif fixup['symbol'] not in program.imports:
                raise PatchError('Replacement refers to undeclared import')
        validated.append((patch, expected, replacement))
    return validated


def apply(program, module, original, layout, symbols, direct_page=0):
    """Apply only after relocation; failure never exposes a partial result."""
    patches = validate_patches(program, module)
    blocks = {b.number: b for b in program.blocks}
    addresses = layout['blocks']
    work, records = bytearray(original), []
    for patch, expected, replacement in patches:
        offset = patch['offset']
        at = addresses[patch['block']]+offset
        relocated = bytearray(expected)
        for fix in patch['intersections']:
            base = fix['base']
            delta = (addresses[base]-blocks[base].offset if isinstance(base, int)
                     else symbols[base])
            pos = fix['offset']-offset
            value = int.from_bytes(relocated[pos:pos+2], 'little')+delta
            if not 0 <= value <= 65535:
                raise PatchError('Relocated preimage outside bank')
            relocated[pos:pos+2] = value.to_bytes(2, 'little')
        if work[at:at+len(relocated)] != relocated:
            raise PatchError('Relocated patch preimage differs: '+patch['id'])
        code = bytearray(replacement)
        for fix in patch['fixups']:
            kind, pos = fix['kind'], fix['offset']
            if kind == 'direct_page16':
                if not 0 <= direct_page <= 0xff00 or direct_page & 255:
                    raise PatchError('Invalid direct-page placement')
                target=direct_page+fix['addend']
            else:
                target = (symbols[fix['symbol']] if kind == 'symbol16'
                          else addresses[fix['block']]+fix['addend'])
            if kind == 'relative8':
                distance = target-(at+pos+1)
                if not -128 <= distance <= 127:
                    raise PatchError('Replacement branch out of range')
                code[pos] = distance & 255
            else:
                if not 0 <= target <= 65535:
                    raise PatchError('Replacement address outside bank')
                code[pos:pos+2] = target.to_bytes(2, 'little')
        work[at:at+len(code)] = code
        records.append(dict(id=patch['id'], address=at, before=relocated.hex(), after=code.hex()))
    return bytes(work), records


def prepare(raw, catalog, start, end, symbols, *, verify_sha=True):
    manifest, module = select(raw, catalog, verify_sha=verify_sha)
    program = parse(raw)
    validate_patches(program, module)
    original, layout = place(program, start, end, symbols)
    image, patches = apply(program, module, original, layout, symbols)
    entry = module['entry_export']
    if entry is not None and entry not in layout['exports']:
        raise PatchError('Missing entry export')
    return PreparedModule(image, layout, dict(
        manifest=manifest['id'], revision=manifest['revision'], module=module['file'],
        execution_status=manifest['execution_status'], bytes=len(raw),
        crc32=f'{zlib.crc32(raw):08x}', original_sha256=hashlib.sha256(raw).hexdigest(),
        image_sha256=hashlib.sha256(image).hexdigest(), patches=patches))
