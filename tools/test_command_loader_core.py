#!/usr/bin/env python3
"""Focused emitted loader copies/readers with independent byte and state oracles."""
import argparse
import json
import io
import zipfile
import struct
from pathlib import Path

from banked_test_memory import read
from library_paths import read_source
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
COPY_SOURCE, COPY_OUTPUT, COPY_FORWARD = 0x280001, 0x300001, 0x220001
READ_SOURCE, READ_CASES = 0x28ffed, 0x290100
BAD_FORMAT = json.loads((ROOT/'abi/program.json').read_text())['errors']['BAD_FORMAT']
PREVIOUS_ERROR = 77


def reader_cases():
    rows = []
    for width in (2, 4):
        for address, start, limit, error, name in [
            (READ_SOURCE, 0, 8, 0, 'zero'),
            (READ_SOURCE+8, 0, 8, 0, 'maximum'),
            (READ_SOURCE+16, 1, 1+width, 0, 'unaligned-exact-end'),
            (READ_SOURCE+16, 1, 12, 0, 'nonzero-position'),
            (0x28fffd, 0, 8, 0, 'bank-crossing-three'),
            (0x28fffe, 0, 8, 0, 'bank-crossing-two'),
            (0x28ffff, 0, 8, 0, 'bank-crossing-one'),
            (READ_SOURCE+16, 9, 8, 0, 'past-limit'),
            (READ_SOURCE+16, 0xfffffffe, 8, 0, 'addition-wrap'),
            (READ_SOURCE+16, 0xffffffff, 0xffffffff, 0, 'maximum-empty'),
            (READ_SOURCE+16, 1, 12, PREVIOUS_ERROR, 'sticky-error'),
            (READ_SOURCE+16, 0xfffffffe, 8, PREVIOUS_ERROR, 'sticky-past-limit'),
        ]:
            rows.append(dict(width=width, address=address, at=start, limit=limit, error=error, name=name))
        for available in range(width):
            rows.append(dict(width=width, address=READ_SOURCE+16, at=1,
                limit=1+available, error=0, name='short-'+str(available)))
    return rows


def reader_expected(payload, address, at, limit, width, error):
    """The retained contract consumes available bytes and zero-extends failures."""
    if error:
        return 0, at, error
    available = min(width, max(0, limit-at))
    begin = address-READ_SOURCE+at
    raw = payload[begin:begin+available] if available else b''
    require(len(raw) == available, 'Reader fixture extent exceeds source')
    return int.from_bytes(raw, 'little'), at+available, BAD_FORMAT if available < width else 0


def copies(out):
    cases = [(0, 0), (1, 1), (2, 0), (17, 3), (65534, 65533),
             (65535, 1), (65536, 65535), (65537, 65534), (131072, 1)]
    length = max(count+offset for count, offset in cases)
    payload = bytes((i*17+(i>>8)*7+(i>>16)*31+3)&255 for i in range(length))
    guarded = b'\xa5'+payload+b'\xa6'
    expected, initial, calls, rows = bytearray(), bytearray(), [], []
    for index, (count, offset) in enumerate(cases):
        start = COPY_OUTPUT+len(expected)
        expected += b'\xd3'+payload[offset:offset+count]+b'\xd4'
        initial += b'\xd3'+b'\x5a'*count+b'\xd4'
        calls.append(f'  progress={index}\n  PROGRAMPLACE.Copy(BYTE POINTER(ADDRESS(${start+1:x})),\n'
                     f'      BYTE POINTER(ADDRESS(${COPY_SOURCE+offset:x})),{f"LONGCARD(CARD({count}))" if count < 65536 else f"LONGCARD({count})"})')
        rows.append(dict(bytes=count, source=COPY_SOURCE+offset, destination=start+1))
    # The loader can place a section on either side of its staged source.
    forward = b'\xd3'+payload[1:131073]+b'\xd4'
    calls.append(f'  progress={len(rows)}\n  PROGRAMPLACE.Copy(BYTE POINTER(ADDRESS(${COPY_FORWARD+1:x})),\n'
                 f'      BYTE POINTER(ADDRESS(${COPY_SOURCE+1:x})),LONGCARD(131072))')
    rows.append(dict(bytes=131072, source=COPY_SOURCE+1, destination=COPY_FORWARD+1))
    include = out/'loader-copy-cases.inc'
    include.write_text('PROC CopyCases()\n\n'+'\n'.join(calls)+'\n\nRETURN\n')
    (out/'probe.act').write_text(read_source(ROOT/'tests/programs/loader_copy.act', {include.name:include}))
    return [(COPY_SOURCE-1, guarded), (COPY_OUTPUT, initial),
            (COPY_FORWARD, b'\xd3'+b'\x5a'*131072+b'\xd4')], dict(cases=rows,
        expected=bytes(expected), source=guarded, forward=forward)


def readers(out):
    payload = bytes(8)+bytes([255])*8+bytes.fromhex('123456789abcdef0012389ab55aa7f80')+bytes([0xa5])*16
    rows = reader_cases()
    raw = b''.join(struct.pack('<B3sIIH', r['width'], r['address'].to_bytes(3, 'little'),
                              r['at'], r['limit'], r['error']) for r in rows)
    include = out/'loader-reader-cases.inc'
    include.write_text(f'CONST CASE_COUNT={len(rows)}\nCONST CASE_BASE=${READ_CASES:x}\n')
    (out/'probe.act').write_text(read_source(ROOT/'tests/programs/loader_readers.act', {include.name:include}))
    return [(READ_SOURCE, payload), (READ_CASES-1, b'\xa7'+raw+b'\xa8')], dict(cases=rows, payload=payload, input=raw)


def run(out, suite, mode):
    out.mkdir(parents=True, exist_ok=True)
    segments, expected = copies(out) if suite == 'copy' else readers(out)
    program = build(compiler(ROOT/'build/actionc', release=True), out/'probe.act', out,
        optimize=mode == 'opt', tasks=True, task_capacity=8, console=False, image_data=segments)
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(bridge, program, timeout=180, frame_limit=9000)
        except Exception:
            print('Fixture stopped:', dict(finished=data(bridge, program['image'], 'finished'),
                progress=data(bridge, program['image'], 'progress', True) if suite == 'copy' else None,
                registers=bridge.regs()), flush=True)
            raise
        ownership(bridge, program, out)
        require(data(bridge, program['image'], 'finished') == [1], 'Loader core fixture incomplete')
        if suite == 'copy':
            # A paused save-state exposes linear RAM without running guest helpers
            # or issuing one debugger RPC for every word of these large spans.
            snapshot = zipfile.ZipFile(io.BytesIO(bridge.state_save(inline=True)['data']))
            memory = snapshot.read('high-memory.bin')
            require(len(memory) == PIN['machine']['high_banks']*65536, 'Wrong linear RAM extent')
            for address, wanted in ((COPY_SOURCE-1, expected['source']), (COPY_OUTPUT, expected['expected']),
                                    (COPY_FORWARD, expected['forward'])):
                actual = memory[address-65536:address-65536+len(wanted)]
                require(actual[:16] == read(bridge, address, 16, out) and
                        actual[-16:] == read(bridge, address+len(wanted)-16, 16, out), 'Snapshot address mapping differs')
                require(actual == wanted, 'Copy bytes/source/guards differ')
        else:
            require(data(bridge, program['image'], 'caseBytes', True) == [14] and
                    data(bridge, program['image'], 'sampleBytes', True) == [34], 'Reader fixture record layout changed')
            symbol = next(s for s in program['image']['data'] if '_SAMPLES_' in s['name'])
            observed = read(bridge, symbol['address'], symbol['size'], out)
            require(len(observed) == len(expected['cases'])*34, 'Wrong sample extent')
            for i, case in enumerate(expected['cases']):
                before, pointer, at, limit, error, middle, value, first_at, first_error, again, after = struct.unpack_from('<H3sxIIHHIIHIH', observed, i*34)
                value_expected, first_at_expected, first_error_expected = reader_expected(expected['payload'],
                    case['address'], case['at'], case['limit'], case['width'], case['error'])
                again_expected, at_expected, error_expected = reader_expected(expected['payload'],
                    case['address'], first_at_expected, case['limit'], case['width'], first_error_expected)
                require((before, middle, after) == (0xcafe, 0xf00d, 0xbabe), 'Reader record guard changed')
                require(int.from_bytes(pointer, 'little') == case['address'] and limit == case['limit'], 'Reader changed source/limit')
                require((value, first_at, first_error, again, at, error) ==
                    (value_expected, first_at_expected, first_error_expected, again_expected, at_expected, error_expected),
                    f'Reader state/result differs: {i} {case}')
            require(read(bridge, READ_SOURCE, len(expected['payload']), out) == expected['payload'], 'Reader modified source')
            require(read(bridge, READ_CASES-1, len(expected['input'])+2, out) == b'\xa7'+expected['input']+b'\xa8', 'Reader changed input/guards')
    return dict(status='pass', tier='development', suite=suite, mode=mode,
        cases=expected['cases'], runtime=runtime, machine=machine, build=program['build'],
        inputs={p:sha256(ROOT/p) for p in ('tools/test_command_loader_core.py',
            'tests/programs/loader_copy.act', 'tests/programs/loader_readers.act',
            'lib/dos/programplace.act', 'lib/dos/o65read.act')},
        bank_zero_delta=dict(fixed=0, per_task=0, idle=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('copy', 'readers'), required=True)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(status='running')
    try:
        result = run(args.output.resolve(), args.suite, args.case)
        print(f'Loader {args.suite} {args.case}: {len(result["cases"])} cases passed', flush=True)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
