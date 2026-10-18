#!/usr/bin/env python3
"""Reproducible MD5 personality development checks; groups report their scope."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time
import urllib.request

from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator
from sdfs_reference import extract, make
from sdx_file import parse, place
from sdx_patch import manifests, select, validate_patches

AUDIT = ROOT/'docs/plans/spartados-personality-inputs.json'
PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def inputs(directory, nomarch):
    directory.mkdir(parents=True, exist_ok=True)
    audit = json.loads(AUDIT.read_text())
    app = next(a for a in audit['applications'] if a['id'] == 'md5')
    for source_id, leaf in [('toolkit-450', 'toolkit.atr'),
                            ('cartridge-450', 'SDX450_maxflash1.car')]:
        source = next(s for s in audit['sources'] if s['id'] == source_id)
        path = directory/leaf
        if not path.exists():
            path.write_bytes(urllib.request.urlopen(source['url'], timeout=30).read())
        require(sha256(path) == source['sha256'], 'Changed SDX distribution: '+leaf)
    archive = directory/'MD5.ARC'
    if not archive.exists():
        extract(directory/'toolkit.atr', directory/'toolkit')
        archive.write_bytes((directory/'toolkit'/app['archive']['path']).read_bytes())
    require(sha256(archive) == app['archive']['sha256'], 'Changed MD5 archive')
    for name in ('MD5.COM', 'MD5.MAN'):
        path = directory/name
        if not path.exists():
            path.write_bytes(subprocess.run([str(nomarch), '-p', str(archive), name.lower()],
                                            check=True, capture_output=True).stdout)
    require(sha256(directory/'MD5.COM') == app['modules'][0]['sha256'], 'Changed MD5 executable')
    return {p.name: dict(sha256=sha256(p), bytes=p.stat().st_size)
            for p in directory.iterdir() if p.is_file()}


def fixtures():
    return {'EMPTY.BIN': b'', 'ABC.BIN': b'abc',
            'BIG.BIN': bytes((i*37+i//251) & 255 for i in range(65537))}


def reference(out, input_dir, patched=False):
    source = out/'source'
    source.mkdir(parents=True, exist_ok=True)
    data = fixtures()
    for name, raw in data.items():
        (source/name).write_bytes(raw)
    good = b'900150983cd24fb0d6963f7d28e17f72  ABC.BIN\n'
    (source/'GOOD.MD5').write_bytes(good)
    (source/'BAD.MD5').write_bytes(good.replace(b'90015098', b'00015098'))
    binary = (input_dir/'MD5.COM').read_bytes()
    if patched:
        # Only the non-relocatable one-byte MD5 patch is written to this
        # disposable SDX control disk. The downloaded original stays intact.
        _, module = select(binary, manifests(ROOT/'compat/sdx'))
        program = parse(binary)
        changes = validate_patches(program, module)
        require(binary[8:8+len(program.blocks[0].data)] == program.blocks[0].data,
                'MD5 first-block file layout changed')
        changed = bytearray(binary)
        for patch, expected, replacement in changes:
            require(patch['block'] == 1 and not patch['intersections'] and not patch['fixups'],
                    'Reference mutation needs a non-relocatable block-one patch')
            at = 8+patch['offset']
            changed[at:at+len(expected)] = replacement
        binary = bytes(changed)
    (source/'MD5.COM').write_bytes(binary)
    # Loaded after MD5 returns, so the stop program never occupies its buffers.
    (source/'STOP.COM').write_bytes(struct.pack('<HHH', 65535, 0x6000, 0x6002)
                                   +b'\x4c\x00\x60'+struct.pack('<HHH', 0x2e0, 0x2e1, 0x6000))
    commands = ['MD5 EMPTY.BIN >>EMPTY.OUT', 'MD5 ABC.BIN >>ABC.OUT',
                'MD5 ABC.BIN EMPTY.BIN >>MULTI.OUT', 'MD5 /C GOOD.MD5 >>GOOD.OUT',
                'MD5 /C BAD.MD5 >>BAD.OUT', 'MD5 ABSENT.BIN >>MISSING.OUT',
                'MD5 BIG.BIN >>BIG.OUT', 'STOP.COM']
    (source/'AUTOEXEC.BAT').write_bytes(b'\x9b'.join(c.encode('ascii') for c in commands)+b'\x9b')
    (source/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
    media = out/'reference.atr'
    make(media, source, 2048, 256, 'MD5REF')
    before = sha256(media)
    with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.config('diskemu', 'fastest')
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        b.mount(0, str(media))
        b.bp_set(0x6000)
        b.boot(str(input_dir/'SDX450_maxflash1.car'))
        b.resume()
        deadline = time.monotonic()+120
        while time.monotonic() < deadline:
            regs = b.regs()
            if int(regs['PC'].lstrip('$'), 16) == 0x6000:
                break
            time.sleep(.05)
        else:
            b.pause()
            (out/'screen.png').write_bytes(b.screenshot())
            raise RuntimeError('Original SDX batch timed out: '+str(regs))
        b.pause()
        (out/'screen.png').write_bytes(b.screenshot())
        # Dirty images flush on the host idle timer; eject is not itself a flush.
        time.sleep(3)
        b.regs()
        b._cmd_ok('EJECT drive=0')
    extract(media, out/'readback')
    outputs = {p.name: p.read_bytes() for p in (out/'readback').glob('*.OUT')}
    digests = {}
    for leaf in ('EMPTY', 'ABC', 'BIG'):
        expected = hashlib.md5(data[leaf+'.BIN']).hexdigest()
        raw = outputs[leaf+'.OUT']
        found = re.findall(rb'= ([0-9A-Fa-f]{32})', raw)
        require([x.decode().lower() for x in found] == [expected], 'Original digest differs: '+leaf)
        digests[leaf] = expected
    require(len(re.findall(rb'= [0-9A-Fa-f]{32}', outputs['MULTI.OUT'])) == 2, 'Missing multiple-file result')
    # BAD is inverse ATASCII, including in redirected output. Preserve those
    # bytes: stripping bit 7 globally would also change the ATASCII EOL.
    require(outputs['GOOD.OUT'] == b'ABC.BIN: OK\x9b'
            and outputs['BAD.OUT'] == b'ABC.BIN: \xc2\xc1\xc4\x9b',
            'Verification control failed')
    return dict(status='pass', scope='SDX control; no Exec guest execution or captured command exit codes',
                sei_patched=patched, executable_sha256=hashlib.sha256(binary).hexdigest(),
                machine=machine, pin=PIN, media_before_sha256=before, media_after_sha256=sha256(media),
                commands=commands, outputs={n: dict(hex=v.hex(), text=v.replace(b'\x9b', b'\n').decode('latin1'))
                                           for n, v in outputs.items()}, digests=digests)


def inspect(out, input_dir):
    program = parse((input_dir/'MD5.COM').read_bytes())
    expected = json.loads(AUDIT.read_text())['applications'][0]['modules'][0]
    require(list(program.imports) == expected['imports'], 'MD5 imports changed')
    symbols = {name: 0xf000+i*16 for i, name in enumerate(program.imports)}
    symbols.update(COMTAB=0xe000, FILE_P=0x761)
    memory, layout = place(program, 0x2000, 0x8000, symbols)
    (out/'image.bin').write_bytes(memory)
    return dict(status='pass', scope='SDX record/placement inspection only; instruction audit incomplete',
                layout=layout, symbols=symbols, blocks=[vars(b) | {'data': b.data.hex()} for b in program.blocks],
                fixups=[vars(f) for f in program.fixups], exports=[vars(e) for e in program.exports])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('inputs', 'reference', 'reference-patched', 'inspect'), required=True)
    parser.add_argument('--inputs', type=Path, default=ROOT/'build/sdx-md5/inputs')
    parser.add_argument('--nomarch', type=Path, default=ROOT/'build/research/s2-vbxe/nomarch-1.4/nomarch')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running', group=args.group)
    try:
        pinned = inputs(args.inputs.resolve(), args.nomarch.resolve())
        result = {'inputs': lambda: dict(status='pass'),
                  'reference': lambda: reference(out, args.inputs.resolve()),
                  'reference-patched': lambda: reference(out, args.inputs.resolve(), patched=True),
                  'inspect': lambda: inspect(out, args.inputs.resolve())}[args.group]()
        result.update(group=args.group, inputs=pinned, bank_zero_delta=dict(fixed=0, per_task=0))
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(args.group, result['status'], flush=True)
