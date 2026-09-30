#!/usr/bin/env python3
"""Bounded emitted-code ReadArgs cases with independent buffers and canaries."""
import argparse
import json
from pathlib import Path

from library_paths import read_source
from banked_test_memory import read as far_read
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine, read_build
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def cases():
    vectors = []

    def add(name, text=b'', template=b'FILE', values=(), error=0, slots=8, capacity=256, flags=0):
        vectors.append(dict(name=name, text=text, template=template, values=values,
                            error=error, slots=slots, capacity=capacity, flags=flags))

    add('optional-missing')
    add('whitespace', b' \t  \t')
    add('empty-template', template=b'', slots=0, capacity=0, flags=3)
    add('empty-template-spaces', b' \t', template=b'', slots=0, capacity=0, flags=3)
    add('empty-template-extra', b'x', template=b'', slots=0, capacity=0, flags=3, error=118)
    add('one', b'FILE.TXT', values=(b'FILE.TXT',))
    add('byte-values', b'\x80\xff', values=(b'\x80\xff',))
    add('larger-storage', b'x', values=(b'x',), capacity=258)
    add('tabs', b'\tfirst \tsecond\t', b'FROM/A,TO/A', (b'first', b'second'))
    add('optional-second', b'first', b'FROM/A,TO', (b'first', None))
    add('required-missing', error=116, template=b'FILE/A')
    add('required-second', b'first', b'FROM,TO/A', error=116)
    add('required-lowercase', b'x', b'file/a', (b'x',))
    add('extra', b'one two', error=118)
    add('quoted', b'"A B"', values=(b'A B',))
    add('empty-present', b'""', b'FILE/A', (b'',), capacity=1)
    add('empty-two', b'"" ""', b'A,B', (b'', b''), capacity=2)
    add('asterisk-quote', b'"A**B*"C"', values=(b'A*B"C',))
    add('literal-backslash', b'"A\\B"', values=(b'A\\B',))
    add('unquoted-asterisk', b'A*B', values=(b'A*B',))
    add('quoted-tab', b'"A\tB"', values=(b'A\tB',))
    add('punctuation-data', b'A|B;C>D', values=(b'A|B;C>D',))
    add('unterminated', b'"bad', error=119)
    add('dangling-escape', b'"bad*', error=119)
    add('escaped-final-quote', b'"bad*"', error=119)
    add('unsupported-escape', b'"bad*x"', error=311)
    add('embedded-quote', b'a"b"', error=311)
    add('suffix-after-quote', b'"a"b', error=311)
    add('exact-storage', b'one two', b'A,B', (b'one', b'two'), capacity=8)
    add('short-storage', b'one two', b'A,B', error=303, capacity=7)
    add('no-terminator-space', b'a', error=303, capacity=1)
    add('no-storage', b'a', error=303, capacity=0, flags=2)
    add('zero-storage-optional', capacity=0, flags=2)
    add('short-slots', b'a', b'A,B', error=303, slots=1)
    add('max-text', b'x'*255, values=(b'x'*255,))
    add('max-text-short-storage', b'x'*255, error=303, capacity=255)
    add('oversize-text', b'x'*256, error=120)
    add('max-template', b'x', b'A'*253+b'/A', (b'x',))
    add('oversize-template', template=b'A'*256, error=114)
    add('eight-fields', b'1 2 3 4 5 6 7 8', b'A,B,C,D,E,F,G,H/A',
        tuple(bytes([v]) for v in range(49, 57)))
    add('eighth-required', b'1 2 3 4 5 6 7', b'A,B,C,D,E,F,G,H/A', error=116)
    for template in (b'A/N', b'A/K', b'A/M', b'A/S', b'A/F', b'A/A/A', b'A/Ax',
                     b'A=B', b'A B', b',A', b'A,', b'A,,B', b'/A', b'A/', b'1A',
                     b'A,B,C,D,E,F,G,H,I', b'A/?'):
        add('bad-template-'+template.decode(), b'x', template, error=114)
    add('underscore-label', b'x', b'_file2', (b'x',))
    add('template-before-arguments', b'"bad', b'A/N', error=114)
    add('null-template', flags=8, error=114)
    add('null-source', flags=4, error=311)
    add('null-slots', flags=1, error=115)
    add('null-storage', flags=2, error=115)
    add('invalid-slot-capacity', slots=9, error=115)
    return vectors


def run(out, mode, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    vectors = cases()
    blob = bytearray()
    calls = []
    for c in vectors:
        source = len(blob)
        blob.extend(c['text']+b'\0')
        template = len(blob)
        blob.extend(c['template']+b'\0')
        calls.append(f'  Probe({source},{template},{c["slots"]},{c["capacity"]},{c["flags"]})')
    (out/'read-args-cases.inc').write_text(f'CONST CASE_COUNT={len(vectors)}\n')
    (out/'read-args-calls.inc').write_text('PROC Cases()\n'+'\n'.join(calls)+'\nRETURN\n')
    source = out/'read_args.act'
    source.write_text(read_source(ROOT/'tests/programs/read_args.act'))
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc'), source, out, optimize=mode=='opt',
              banked=True, console=False, image_data=[(0xe0000, bytes(blob)), (0xd0000, bytes(292*len(vectors)))])
    require(p['build']['source_sha256'] == sha256(source), 'Stale parser fixture')
    require(any(s['address'] == 0xe0000 and bytes(s['bytes']) == bytes(blob) for s in p['image']['segments']), 'Stale parser vectors')
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        for name, value in PIN['configuration'].items():
            b.config(name, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=90, frame_limit=4500)
        require(data(b, p['image'], 'finished') == [1], 'Missing parser completion')
        require(data(b, p['image'], 'caseIndex', True) == [len(vectors)], 'Missing parser cases')
        stride = int.from_bytes(bytes(data(b, p['image'], 'rowBytes')), 'little')
        require(stride == 292, 'Packed address array layout')
        location = 0xd0000
        rows = far_read(b, location, stride*len(vectors), out)
        for i, c in enumerate(vectors):
            row = rows[i*stride:(i+1)*stride]
            require(int.from_bytes(row[:2], 'little') == c['error'], 'Parser error: '+c['name'])
            slots = [int.from_bytes(row[2+j*3:5+j*3], 'little') for j in range(10)]
            storage = row[32:292]
            valid_slots = c['slots'] <= 8 and not c['flags'] & 1
            expected = [0xabcdef]*10
            if valid_slots:
                expected[1:1+c['slots']] = [0]*c['slots']
            used = 0
            if not c['error']:
                for j, value in enumerate(c['values']):
                    if value is not None:
                        expected[j+1] = location+i*stride+33+used
                        require(storage[1+used:2+used+len(value)] == value+b'\0', 'Decoded value: '+c['name'])
                        used += len(value)+1
                require(storage[1+used:] == b'\xa5'*(259-used), 'Unused storage: '+c['name'])
            require(slots == expected, f'Result slots/canaries: {c["name"]}: {slots} != {expected}')
            require(storage[0] == 0xa5 and storage[1+c['capacity']:] == b'\xa5'*(259-c['capacity']),
                    'Storage bounds: '+c['name'])
        require(far_read(b, 0xe0000, len(blob), out) == bytes(blob), 'Source/template changed')
    routines = [r for r in p['image']['routines'] if r['name'].startswith('M_DOSARGS_')]
    return dict(status='pass', tier='development', mode=mode, cases=[c['name'] for c in vectors],
                build=p['build'], runtime=runtime, machine=machine, pin=PIN, routines=routines,
                code_bytes=sum(r['size'] for r in routines), bank_zero_delta=dict(fixed=0, per_task=0),
                source_inputs={str(path.relative_to(ROOT)): sha256(path) for path in
                               (ROOT/'lib/dos/dosargs.act', ROOT/'tests/programs/read_args.act', Path(__file__))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.case, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('ReadArgs checks passed:', args.case, len(result['cases']))
