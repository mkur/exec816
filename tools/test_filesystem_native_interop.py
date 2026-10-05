#!/usr/bin/env python3
"""Reopen Exec-written files through pinned native DOS CIO and check CRC/EOF."""
import argparse
import json
import shutil
import struct
import time
import urllib.request
import zlib
from pathlib import Path

from native_program import ROOT, command, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from mydos_producer import boot_disk, ORIGINAL_SHA256
from make_sdfs_fixtures import CAR_URL, CAR_SHA
from filesystem_audit import Audit
import sdfs_reference


def assemble(out, filesystem, files, mutate):
    code, literals = [], []

    def literal(raw):
        label = 'literal' + str(len(literals))
        literals.append(label + ': .byte ' + ','.join(map(str, raw)))
        return label

    def open_file(name, mode):
        separator = ':' if filesystem == 'mydos' else '>'
        label = literal(('D2:' + name.replace('/', separator)).encode() + b'\0')
        code.extend([f'lda #<{label}', 'sta IOCB+4', f'lda #>{label}', 'sta IOCB+5',
                     f'lda #{mode}', 'sta IOCB+10', 'lda #0', 'sta IOCB+11',
                     'lda #3', 'sta IOCB+2', 'jsr call'])

    def verify(name, content, number):
        open_file(name, 4)
        for i in range(3):
            code.extend([f'lda #{(len(content) >> (8*i)) & 255}', f'sta remaining+{i}'])
        code.extend(['jsr readfile'])
        crc = zlib.crc32(content)
        for i in range(4):
            code.extend([f'lda crc+{i}', 'eor #255', f'cmp #{(crc >> (8*i)) & 255}',
                         f'beq check{number}_{i}', 'jmp failed', f'check{number}_{i}:'])
        code.extend(['jsr close'])

    for number, (name, content) in enumerate(files.items()):
        verify(name, content, number)
    expected = dict(files)
    if mutate:
        patch, tail = b'NATIVE!', b'\x00\x9b\xffEND'
        for mode, payload in ((12, patch), (9, tail)):
            open_file('WRENAMED.BIN', mode)
            label = literal(payload)
            code.extend([f'lda #<{label}', 'sta IOCB+4', f'lda #>{label}', 'sta IOCB+5',
                         f'lda #{len(payload)}', 'sta IOCB+8', 'lda #0', 'sta IOCB+9',
                         'lda #11', 'sta IOCB+2', 'jsr call', 'jsr close'])
        expected['WRENAMED.BIN'] = patch + files['WRENAMED.BIN'][len(patch):] + tail
        verify('WRENAMED.BIN', expected['WRENAMED.BIN'], len(files))
    source = '''.setcpu "6502"
.segment "CODE"
.export start,done,failed,result,phase
CIO=$e456
IOCB=$350
crc=$80
remaining=$84
chunk=$87
count=$89
actual=$8b
buffer=$9000
start:
 cld
 cli
 lda #0
 sta result
 sta phase
BODY
 lda #1
 sta result
done: jmp done
failed: jmp failed
call:
 inc phase
 ldx #$10
 jsr CIO
 tya
 bpl okay
 sta result
 jmp failed
okay: rts
close:
 lda #12
 sta IOCB+2
 jmp call
readfile:
 lda #255
 sta crc
 sta crc+1
 sta crc+2
 sta crc+3
again:
 lda remaining
 ora remaining+1
 ora remaining+2
 bne more
 jmp eof
more:
 lda #0
 sta chunk
 lda #1
 sta chunk+1
 lda remaining+1
 ora remaining+2
 bne get
 sta chunk+1
 lda remaining
 sta chunk
get:
 lda #<buffer
 sta IOCB+4
 sta actual
 lda #>buffer
 sta IOCB+5
 sta actual+1
 lda chunk
 sta IOCB+8
 sta count
 lda chunk+1
 sta IOCB+9
 sta count+1
 lda #7
 sta IOCB+2
 jsr call
scan:
 ldy #0
 lda (actual),y
 eor crc
 sta crc
 ldx #8
crcbit:
 lsr crc+3
 ror crc+2
 ror crc+1
 ror crc
 bcc advance
 lda crc
 eor #$20
 sta crc
 lda crc+1
 eor #$83
 sta crc+1
 lda crc+2
 eor #$b8
 sta crc+2
 lda crc+3
 eor #$ed
 sta crc+3
advance:
 dex
 bne crcbit
 inc actual
 bne decrement
 inc actual+1
decrement:
 lda count
 bne low
 dec count+1
low:
 dec count
 lda count
 ora count+1
 bne scan
 sec
 lda remaining
 sbc chunk
 sta remaining
 lda remaining+1
 sbc chunk+1
 sta remaining+1
 lda remaining+2
 sbc #0
 sta remaining+2
 jmp again
eof:
 lda #<buffer
 sta IOCB+4
 lda #>buffer
 sta IOCB+5
 lda #1
 sta IOCB+8
 lda #0
 sta IOCB+9
 lda #7
 sta IOCB+2
 ldx #$10
 jsr CIO
 cpy #136
 beq finished
 jmp failed
finished: rts
result: .byte 0
phase: .byte 0
LITERALS
'''.replace('BODY', '\n'.join(code)).replace('LITERALS', '\n'.join(literals))
    (out/'native.s').write_text(source)
    (out/'native.cfg').write_text('MEMORY { RAM: start=$6000,size=$3000,file=%O; } SEGMENTS { CODE: load=RAM,type=ro; }\n')
    command(['ca65', '-o', out/'native.o', out/'native.s'])
    command(['ld65', '-C', out/'native.cfg', '-o', out/'native.bin', '-Ln', out/'native.lbl', out/'native.o'])
    labels = {s.split()[2].lstrip('.'): int(s.split()[1], 16)
              for s in (out/'native.lbl').read_text().splitlines()}
    binary = (out/'native.bin').read_bytes()
    payload = struct.pack('<HHH', 65535, 0x6000, 0x6000 + len(binary) - 1) + binary
    payload += struct.pack('<HHH', 0x2e0, 0x2e1, labels['start'])
    return payload, labels, expected


def run(out, filesystem, image, mutate):
    out.mkdir(parents=True, exist_ok=True)
    source = Audit(image.read_bytes())
    getattr(source, filesystem)()
    payload, labels, expected = assemble(out, filesystem, source.files, mutate)
    boot, target = out/'boot.atr', out/'volume.atr'
    shutil.copyfile(image, target)
    if filesystem == 'mydos':
        boot_disk(boot, payload)
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
        sdfs_reference.make(boot, tree, 720, 128)
        launch = car
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        for key, value in dict(siopatch='on', diskemu='fastest', accuratedisk='false', burstio='true').items():
            bridge.config(key, value)
        if filesystem == 'sdfs':
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
                f'Native readback failed: {filesystem}, PC={pc:04x}, result={result}, phase={phase}, Y={regs["Y"]}')
        time.sleep(3)
        bridge.regs()
        bridge._cmd_ok('EJECT drive=1')
    audit = Audit(target.read_bytes())
    counts = getattr(audit, filesystem)()
    require(audit.files == expected, 'Native update differs from independently expected bytes')
    return dict(status='pass', filesystem=filesystem, sector_bytes=audit.image.size,
                source_sha256=sha256(image), media_sha256=sha256(target), allocation=counts,
                native_sha256=ORIGINAL_SHA256 if filesystem == 'mydos' else CAR_SHA,
                verifier_sha256=sha256(out/'native.bin'), machine=machine, native_update=mutate,
                overrides=dict(siopatch='on', diskemu='fastest', accuratedisk=False, burstio=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--mutate', action='store_true', help='Also overwrite and append through native DOS')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.filesystem, args.image.resolve(), args.mutate)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Native DOS interoperability passed', args.filesystem)
