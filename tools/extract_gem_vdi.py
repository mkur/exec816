"""Reproduce the selected GEM sources, then apply the hosted adaptation patch."""
import json
from pathlib import Path
import shutil

from gem_vdi_inputs import source_inputs
from native_program import ROOT, command, require, sha256

PORT = ROOT/'ports/gem4xe'


def operation_checks(abi):
    lines = ['/* Generated from abi/gem-vdi.json. */',
             'uint16_t GemVdiValidate(uint16_t op, uint16_t sub, uint16_t pairs,',
             '                       uint16_t words, const int16_t *points, const int16_t *ints)',
             '{', '    uint16_t i;',
             '    if ((pairs && !points) || (words && !ints) ||',
             '        (uint32_t)points > 0xffffffUL || (uint32_t)ints > 0xffffffUL)',
             '        return 2;', '    switch (op) {']
    for op in abi['vdi_operations']:
        p, n = op['point_pairs'], op['int_words']
        lines += [f'    case {op["opcode"]}:',
                  f'        if (sub != {op["subopcode"]} || pairs < {p[0]} || pairs > {p[1]} ||',
                  f'            words < {n[0]} || words > {n[1]}) return 1;']
        if 'int_values' in op:
            lines += [f'        if (ints[{i}] != {v}) return 1;' for i,v in enumerate(op['int_values'])]
        if 'value_range' in op:
            low, high = op['value_range']
            lines += [f'        if (ints[0] < {low} || ints[0] > {high}) return 1;']
        if 'glyph_range' in op:
            low, high = op['glyph_range']
            lines += [f'        for (i = 0; i < words; ++i)',
                      f'            if (ints[i] < {low} || ints[i] > {high}) return 1;']
        lines += ['        return 0;']
    return '\n'.join(lines+['    default: return 1;', '    }', '}', ''])


def extract(output, upstream=None):
    output = Path(output).resolve()
    upstream = Path(upstream or ROOT/'build/gem-vdi/upstream')
    sources = source_inputs(upstream)
    selection = json.loads((PORT/'selection.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    selected = {}
    for name, spec in selection['outputs'].items():
        require(spec['source'] in sources, 'Unpinned extraction input')
        path = output/name
        require(path.resolve().is_relative_to(output), 'Extraction path escapes output')
        payload = (upstream/spec['source']).read_bytes()
        if 'ranges' in spec:
            lines = payload.decode().replace('\r\n', '\n').splitlines(keepends=True)
            previous = 0
            for first, last in spec['ranges']:
                require(previous < first <= last <= len(lines), 'Invalid/overlapping source selection')
                previous = last
            payload = '\n'.join(''.join(lines[a-1:b]) for a,b in spec['ranges']).encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        selected[name] = sha256(path)
    patch = PORT/'patches/0001-hosted-storage-and-subset.patch'
    command(['patch', '-p1', '-F', '0', '-t', '-i', patch], cwd=output)
    for path in sorted((PORT/'hosted').iterdir()):
        if path.is_file():
            shutil.copyfile(path, output/'src'/path.name)
    (output/'src/operation-checks.inc').write_text(operation_checks(
        json.loads((ROOT/'abi/gem-vdi.json').read_text())))
    record = dict(upstream=sources, selection_sha256=sha256(PORT/'selection.json'),
                  patch_sha256=sha256(patch), selected=selected,
                  adapted={p.relative_to(output).as_posix():sha256(p)
                           for p in sorted(output.rglob('*')) if p.is_file() and
                           p.name != 'extraction.json' and p.suffix not in ('.orig', '.rej')})
    (output/'extraction.json').write_text(json.dumps(record, indent=2)+'\n')
    return record
