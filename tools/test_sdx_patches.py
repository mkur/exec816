#!/usr/bin/env python3
"""Execute native CRC32 and the patched ARC inline helper on pinned Altirra.

Development tests only: this fixture owns its page one and disables interrupts.
It does not admit SDX commands through Exec's scheduler or DOS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time
import zlib

from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sdx_file import parse, place
from sdx_patch import manifests, prepare
from sio_transaction_trace import BASE_HZ

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
SOURCE = ROOT/'probes/sdx-patches/probe.s'


def build(out, native_bank, guest_bank):
    out.mkdir(parents=True, exist_ok=True)
    cfg = out/'probe.cfg'
    cfg.write_text(f'''MEMORY {{
 RAM: start=$3000, size=$1000, file=%O, fill=yes;
 NATIVE: start=${native_bank:02x}6000, size=$1000, file=%O, fill=yes;
 GUEST: start=${guest_bank:02x}f000, size=$400, file=%O;
}}
SEGMENTS {{
 CODE: load=RAM, type=ro;
 NATIVE: load=NATIVE, type=ro;
 GUEST: load=GUEST, type=ro;
}}
''')
    subprocess.run(['ca65', '-I', str(ROOT/'platform/altirraos'),
                    '-I', str(ROOT/'platform/altirraos/generated'),
                    '-D', f'NATIVE_BANK={native_bank}', '-D', f'GUEST_BANK={guest_bank}',
                    '-l', str(out/'probe.lst'), '-o', str(out/'probe.o'), str(SOURCE)],
                   check=True, timeout=30)
    subprocess.run(['ld65', '-C', str(cfg), '-o', str(out/'probe.bin'),
                    '-Ln', str(out/'probe.lbl'), str(out/'probe.o')], check=True, timeout=30)
    labels = {}
    for line in (out/'probe.lbl').read_text().splitlines():
        _, address, label = line.split()
        labels[label.lstrip('.')] = int(address, 16)
    raw = (out/'probe.bin').read_bytes()
    xex = out/'probe.xex'
    xex.write_bytes(struct.pack('<HHH', 65535, 0x3000, 0x3000+len(raw)-1)+raw
                    +struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    return xex, labels


def crc32_bitwise(raw, state=0xffffffff):
    for byte in raw:
        state ^= byte
        for _ in range(8):
            state = (state >> 1) ^ (0xedb88320 if state & 1 else 0)
    return state


def module_files(md5, arc):
    return {'MD5.COM': md5/'MD5.COM', **{n: arc/n for n in
            ('ARC.COM', 'ARCLST.OVL', 'ARCEXT.OVL', 'ARCADD.OVL')}}


def assembly_check(out, module, layout, patched):
    """Assemble the maintained source independently of its manifest bytes."""
    at = layout['blocks'][1]+module['patches'][0]['offset']
    count = layout['blocks'][2]+4294
    source = out/'inline.s'
    source.write_text(f'.segment "CODE"\nARC_COUNT=${count:04x}\n'
                      '.include "arc-inline.s"\n')
    cfg = out/'inline.cfg'
    cfg.write_text(f'MEMORY {{ RAM: start=${at:04x}, size=38, file=%O; }}\n'
                   'SEGMENTS { CODE: load=RAM, type=ro; }\n')
    subprocess.run(['ca65', '-I', str(ROOT/'compat/sdx'), '-o', str(out/'inline.o'), str(source)],
                   check=True, timeout=30)
    subprocess.run(['ld65', '-C', str(cfg), '-o', str(out/'inline.bin'), str(out/'inline.o')],
                   check=True, timeout=30)
    require((out/'inline.bin').read_bytes() == patched[at:at+38], 'ARC source/manifest mismatch')


def execute(out, xex, labels, native_bank, guest_bank, files):
    rom, bridge = ROOT/'build/firmware/altirraos-816.rom', ROOT/'build/shell-paced-bridge'
    require(sha256(rom) == PIN['rom']['sha256'], 'ROM pin differs')
    require(sha256(bridge/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Emulator pin differs')
    catalog = manifests(ROOT/'compat/sdx')
    vectors = [('empty', b''), ('check', b'123456789'), ('all-bytes', bytes(range(256))),
               ('bank-crossing', bytes((i*37+i//251)&255 for i in range(65535)))]
    vectors += [(name, path.read_bytes()) for name, path in files.items()]
    crc_records, arc_records = [], []
    with emulator(bridge, rom, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.boot(str(xex))
        run_to(b, labels['start'])
        machine = verify_machine(b, rom, PIN)
        b.bp_set(labels['done'])
        run_to(b, labels['done'])
        # Every call starts at the same bank-zero rendezvous with native D/S.
        def invoke():
            begin = b.eval_expr('@clk') & 0xffffffff
            run_to(b, labels['done'], frame_limit=300, timeout=15)
            return ((b.eval_expr('@clk')-begin) & 0xffffffff)

        for name, raw in vectors:
            state = crc32_bitwise(raw)
            require(state ^ 0xffffffff == zlib.crc32(raw), 'Independent CRC oracle differs')
            source = 0x08fff0
            b.memload(source, raw)
            b.memload(0x2400, bytes([0xa5])*256)
            b.memload(0x2480, source.to_bytes(3, 'little'))
            b.memload(0x2484, bytes([255])*4)
            b.poke16(0x2000, len(raw))
            b.poke16(0x202e, 0)
            ticks = invoke()
            scratch = b.memdump(0x2400, 256)
            expected = bytearray([0xa5]*256)
            expected[0x80:0x83] = (source+len(raw)).to_bytes(3, 'little')
            expected[0x84:0x88] = state.to_bytes(4, 'little')
            require(scratch == expected, 'CRC result, pointer or scratch guard differs: '+name)
            require(b.memdump(0x2002, 7) == bytes.fromhex('efbe0024ef5f03'),
                    'CRC did not preserve Y/D/S/DBR')
            crc_records.append(dict(name=name, bytes=len(raw), crc32=f'{state^0xffffffff:08x}',
                                    elapsed_base_cycles=ticks, elapsed_ms=ticks/BASE_HZ*1000))
            # A zero-length update and uneven split must produce the same CRC.
            b.memload(0x2480, source.to_bytes(3, 'little'))
            b.memload(0x2484, bytes([255])*4)
            split = min(13, len(raw))
            for length in (split, 0, len(raw)-split):
                b.poke16(0x2000, length)
                invoke()
            require(b.memdump(0x2484, 4) == state.to_bytes(4, 'little'), 'CRC split update differs')

        raw = files['ARC.COM'].read_bytes()
        program = parse(raw)
        module = next(m for c in catalog for m in c['modules'] if m['file'] == 'ARC.COM')
        symbols = {name: 0xe000+i*16 for i, name in enumerate(program.imports)}
        arguments = bytes.fromhex('19324b647d96')
        for base in (0x2000, 0x4100):
            prepared = prepare(raw, catalog, base, 0x8000, symbols)
            assembly_check(out, module, prepared.layout, prepared.image)
            original, layout = place(program, base, 0x8000, symbols)
            helper = base+0x5ed
            for stack in (0x1ef, 0x1bf, 0x17f):
                for patched in (False, True):
                    image = prepared.image if patched else original
                    b.memload((guest_bank << 16)+base, image[base:layout['end']])
                    b.memload((guest_bank << 16)+0xf201, helper.to_bytes(2, 'little'))
                    call = b'\x20\x00\xf2'+arguments+b'\x4c\x00\xf3'
                    b.memload((guest_bank << 16)+0x7ffc, call)
                    # The original is the independent register/stack oracle;
                    # D=DBR=0 and a bank-zero copy of the inline literals.
                    dp, dbr = ((0x2200 if base == 0x2000 else 0x2300), guest_bank) if patched else (0, 0)
                    b.memload(0x7fff, arguments)
                    b.memload(dp+0xef, bytes([0xa5])*9)
                    b.memload((guest_bank << 16)+0xef, bytes([0x5a])*9)
                    b.memload(0x100, bytes([0xa5])*256)
                    b.memload(0x2010, bytes(16))
                    b.poke16(0x2002, stack)
                    b.poke16(0x2004, dp)
                    b.poke(0x2008, dbr)
                    b.poke16(0x202e, 1)
                    invoke()
                    state = b.memdump(0x2010, 24)
                    # C=0, V=1 from $7F+carry, N=0/Z=1, I=1, M/X=1.
                    expected = bytes([arguments[0], (stack-4)&255, 0, 0x76, (stack-2)&255])
                    require(state[:5] == expected, f'ARC state differs: {base:x}/{stack:x}/{patched}: {state.hex()}')
                    require(state[6:8] == bytes([(stack-2)&255, 0xab]), 'ARC hidden B or outer return differs')
                    require(b.memdump(dp+0xf0, 6) == arguments, 'ARC argument ordering differs')
                    require(b.memdump(dp+0xfe, 2) == b'\xfe\x7f', 'ARC old return pointer differs')
                    require(b.memdump((guest_bank << 16)+0xef, 9) == bytes([0x5a])*9,
                            'ARC wrote upper-bank low-page aliases')
                    count_bank = guest_bank if patched else 0
                    require(b.memdump((count_bank << 16)+layout['blocks'][2]+4294, 1) == b'\x06',
                            'ARC count storage differs')
                    arc_records.append(dict(placement=base, stack=stack, patched=patched,
                                            dp=dp, dbr=dbr, state=state[:8].hex()))
    return dict(status='pass', tier='development', machine=machine, crc=crc_records, arc=arc_records,
                native_bank=native_bank, guest_bank=guest_bank,
                crc_code_bytes=labels['sdx_crc32_end']-labels['sdx_crc32_update'],
                crc_table_bytes=labels['sdx_crc32_table_end']-labels['sdx_crc32_table'],
                xex_sha256=sha256(xex), production_bank_zero_delta=dict(fixed=0, per_task=0),
                scope='Isolated emitted CRC32 and ARC helper; IRQ/NMI disabled; no Exec Process admission')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/sdx-patches')
    parser.add_argument('--md5', type=Path, default=ROOT/'build/sdx-inputs/md5')
    parser.add_argument('--arc', type=Path, default=ROOT/'build/sdx-inputs/arc')
    parser.add_argument('--banks', type=int, nargs=2, default=(2, 3), metavar=('NATIVE', 'GUEST'))
    args = parser.parse_args()
    out = args.output.resolve()
    xex, labels = build(out, *args.banks)
    files = module_files(args.md5, args.arc)
    # Host pin verification is mandatory before any downloaded bytes execute.
    catalog = manifests(ROOT/'compat/sdx')
    from sdx_patch import select
    for path in files.values():
        select(path.read_bytes(), catalog)
    report = dict(status='running')
    started = time.monotonic()
    try:
        report = execute(out, xex, labels, *args.banks, files)
        report.update(seconds=round(time.monotonic()-started, 3), pin=PIN,
                      inputs={name: sha256(path) for name, path in files.items()},
                      sources={name: sha256(ROOT/name) for name in (
                          'abi/sdx.json','tools/generate_sdx.py','tools/sdx_file.py',
                          'tools/sdx_patch.py','tools/test_sdx_patches.py',
                          'compat/sdx/md5-450.json','compat/sdx/arc-450.json',
                          'compat/sdx/arc-inline.s','probes/sdx-patches/probe.s',
                          'platform/altirraos/sdx-crc32.s',
                          'platform/altirraos/generated/sdx.inc',
                          'platform/altirraos/generated/sdx-crc32-table.inc')})
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print('SDX patch probes:', report['status'], flush=True)


if __name__ == '__main__':
    main()
