#!/usr/bin/env python3
"""Record native DOS mutation semantics without using the Exec816 writer."""
import argparse
import hashlib
import json
import struct
import time
import urllib.request
from pathlib import Path

from native_program import ROOT, command, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from mydos_producer import boot_disk, blank, ORIGINAL_SHA256
from make_sdfs_fixtures import CAR_URL, CAR_SHA
from filesystem_audit import Audit
import sdfs_reference


def assemble(out, format, count):
    initial = bytes(i & 255 for i in range(300))
    tail = bytes(i ^ 0x96 for i in range(37))
    patch = bytes(i ^ 0x63 for i in range(17))
    expected = {'EMPTY': b'', 'CREATE.BIN': initial, 'APPEND.BIN': initial + tail,
                'UPDATE.BIN': patch + initial[17:], 'TRUNC.BIN': patch,
                'RENAMED.BIN': tail}
    code, literals = [], []

    def literal(data):
        name = 'literal' + str(len(literals))
        literals.append(name + ': .byte ' + ','.join(map(str, data or b'\0')))
        return name

    def name(value):
        label = literal(value.encode() + b'\0')
        code.extend([f'lda #<{label}', 'sta IOCB+4', f'lda #>{label}', 'sta IOCB+5'])

    def special(value, operation, aux=0, aux2=0):
        name(value)
        code.extend([f'lda #{operation}', 'sta IOCB+2', f'lda #{aux}', 'sta IOCB+10',
                     f'lda #{aux2}', 'sta IOCB+11', 'jsr call'])

    def write(value, data, mode=8):
        special('D2:' + value, 3, mode)
        if data:
            label = literal(data)
            code.extend([f'lda #<{label}', 'sta IOCB+4', f'lda #>{label}', 'sta IOCB+5',
                         f'lda #{len(data) & 255}', 'sta IOCB+8', f'lda #{len(data) >> 8}',
                         'sta IOCB+9', 'lda #11', 'sta IOCB+2', 'jsr call'])
        code.extend(['jsr close'])

    if format == 'mydos':
        special('D2:', 254, count & 255, (count >> 8) | 128)
    for file in ('CREATE.BIN', 'APPEND.BIN', 'UPDATE.BIN', 'TRUNC.BIN'):
        write(file, initial)
    write('EMPTY', b'')
    write('APPEND.BIN', tail, 9)
    write('UPDATE.BIN', patch, 12)
    write('TRUNC.BIN', patch)
    write('OLD.BIN', tail)
    special('D2:OLD.BIN,RENAMED.BIN', 32)
    write('DELETE.BIN', initial)
    special('D2:DELETE.BIN', 33)
    mkdir, rmdir = (34, 33) if format == 'mydos' else (42, 43)
    special('D2:EMPTYDIR', mkdir)
    special('D2:EMPTYDIR', rmdir)
    special('D2:SUB', mkdir)
    separator = ':' if format == 'mydos' else '>'
    write('SUB' + separator + 'CHILD.BIN', patch)
    expected['SUB/CHILD.BIN'] = patch
    for file, data in expected.items():
        special('D2:' + file.replace('/', separator), 3, 4)
        if data:
            label = literal(data)
            code.extend(['lda #<buffer', 'sta IOCB+4', 'lda #>buffer', 'sta IOCB+5',
                         f'lda #{len(data) & 255}', 'sta IOCB+8', f'lda #{len(data) >> 8}',
                         'sta IOCB+9', 'lda #7', 'sta IOCB+2', 'jsr call',
                         f'lda #<{label}', 'sta expected', f'lda #>{label}', 'sta expected+1',
                         f'lda #{len(data) & 255}', 'sta remaining', f'lda #{len(data) >> 8}',
                         'sta remaining+1', 'jsr verify'])
        code.append('jsr close')
    source = '''.setcpu "6502"
.segment "CODE"
.export start,done,failed,result,phase
CIO=$e456
IOCB=$350
expected=$80
actual=$82
remaining=$84
start:
 cld
 cli
 lda #0
 sta phase
 sta result
BODY
 lda #1
 sta result
done: jmp done
close:
 lda #12
 sta IOCB+2
call:
 inc phase
 ldx #$10
 jsr CIO
 tya
 bmi failed
 rts
failed:
 sty result
 jmp failed
verify:
 lda #<buffer
 sta actual
 lda #>buffer
 sta actual+1
 ldy #0
check:
 lda (actual),y
 cmp (expected),y
 beq equal
 ldy #$ff
 jmp failed
equal:
 inc actual
 bne :+
 inc actual+1
:
 inc expected
 bne :+
 inc expected+1
:
 lda remaining
 bne :+
 dec remaining+1
:
 dec remaining
 lda remaining
 ora remaining+1
 bne check
 rts
result: .byte 0
phase: .byte 0
LITERALS
buffer=$9000
'''.replace('BODY', '\n'.join(code)).replace('LITERALS', '\n'.join(literals))
    (out/'native.s').write_text(source)
    (out/'native.cfg').write_text('MEMORY { RAM: start=$6000,size=$3000,file=%O; } SEGMENTS { CODE: load=RAM,type=ro; }\n')
    command(['ca65', '-o', out/'native.o', out/'native.s'])
    command(['ld65', '-C', out/'native.cfg', '-o', out/'native.bin', '-Ln', out/'native.lbl', out/'native.o'])
    labels = {s.split()[2].lstrip('.'): int(s.split()[1], 16) for s in (out/'native.lbl').read_text().splitlines()}
    binary = (out/'native.bin').read_bytes()
    payload = struct.pack('<HHH', 65535, 0x6000, 0x6000 + len(binary) - 1) + binary
    payload += struct.pack('<HHH', 0x2e0, 0x2e1, labels['start'])
    return payload, labels, expected


def produce(out, format, size):
    out.mkdir(parents=True, exist_ok=True)
    count = 720 if size == 128 else 2000
    payload, labels, expected = assemble(out, format, count)
    boot, target = out/'boot.atr', out/'volume.atr'
    if format == 'mydos':
        boot_disk(boot, payload)
        blank(target, size, count)
        launch = boot
    else:
        car = out.parent/'SDX450_maxflash1.car'
        if not car.exists():
            car.write_bytes(urllib.request.urlopen(CAR_URL, timeout=30).read())
        require(sha256(car) == CAR_SHA, 'Unpinned SDX cartridge')
        tree = out/'boot-source'
        tree.mkdir(exist_ok=True)
        (tree/'NATIVE.COM').write_bytes(payload)
        (tree/'AUTOEXEC.BAT').write_bytes(b'D1:NATIVE.COM\x9b')
        (tree/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
        empty = out/'empty'
        empty.mkdir(exist_ok=True)
        sdfs_reference.make(boot, tree, 720, 128)
        sdfs_reference.make(target, empty, count, size)
        launch = car
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        bridge.config('siopatch', 'on')
        bridge.config('diskemu', 'fastest')
        bridge.config('accuratedisk', 'false')
        bridge.config('burstio', 'true')
        if format == 'sdfs':
            bridge.mount(0, str(boot))
        bridge.mount(1, str(target))
        bridge.bp_set(labels['done'])
        bridge.bp_set(labels['failed'])
        bridge.boot(str(launch))
        bridge.resume()
        deadline = time.monotonic() + 180
        pc = 0
        while time.monotonic() < deadline:
            regs = bridge.regs()
            pc = int(regs['PC'].lstrip('$'), 16)
            if pc in (labels['done'], labels['failed']):
                break
            time.sleep(.05)
        bridge.pause()
        result, phase = bridge.peek(labels['result'])[0], bridge.peek(labels['phase'])[0]
        require(pc == labels['done'] and result == 1,
                f'Native mutation failed: format={format}, PC={pc:04x}, result={result}, phase={phase}, Y={regs["Y"]}')
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=1')
    audit = Audit(target.read_bytes())
    counts = getattr(audit, format)()
    require(audit.files == expected, 'Native persisted bytes differ from job data')
    result = dict(status='pass', format=format, sector_bytes=size, counts=counts,
                  producer_sha256=ORIGINAL_SHA256 if format == 'mydos' else CAR_SHA,
                  media_sha256=sha256(target), verifier_sha256=sha256(out/'native.bin'),
                  machine=machine, emulator_sha256=sha256(ROOT/'build/altirra-sio-multi/AltirraBridgeServer'),
                  overrides=dict(siopatch='on', diskemu='fastest', accuratedisk=False, burstio=True),
                  files={p: hashlib.sha256(b).hexdigest() for p, b in expected.items()})
    (out/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--size', type=int, choices=(128, 256), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.output.resolve(), args.format, args.size), indent=2))
