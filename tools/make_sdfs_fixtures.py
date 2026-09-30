#!/usr/bin/env python3
"""Independent SDFS fixtures, explicit mutations, and original SDX CIO readback."""
import hashlib
import json
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
import sdfs_reference as reference
from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN

FIXTURES = ROOT/'tests/fixtures/sdfs'
CAR_URL = 'https://sdx.atari8.info/sdx_files/4.50/SDX450_maxflash1.car'
CAR_SHA = '17fa6167b6de7997cceb67b8ab261c0c24eff5d9d8eeb4417a0644a87a9674c0'


class Media:
    """Field-addressing helper for documented fixture mutations, not the oracle."""
    def __init__(self, raw):
        self.raw = bytearray(raw)
        self.size = struct.unpack_from('<H', raw, 4)[0]

    def at(self, sector):
        return 16+(sector-1)*128 if sector <= 3 else 400+(sector-4)*self.size

    def word(self, offset):
        return struct.unpack_from('<H', self.raw, offset)[0]

    def put(self, offset, value):
        struct.pack_into('<H', self.raw, offset, value)

    def chain(self, start):
        pages, data = [], []
        while start:
            if start in pages: raise ValueError('Cyclic fixture map')
            pages.append(start)
            at = self.at(start)
            data += [self.word(i) for i in range(at+4, at+self.size, 2)]
            start = self.word(at)
        return pages, data

    def entry(self, directory, name):
        _, sectors = self.chain(directory)
        contents = b''.join(self.raw[self.at(n):self.at(n)+self.size] for n in sectors if n)
        key = b''.join(part.encode().ljust(width, b' ') for part, width in zip((name.split('.')+[''])[:2], (8, 3)))
        length = int.from_bytes(contents[3:6], 'little')
        for pos in range(23, length, 23):
            row = contents[pos:pos+23]
            if row[6:17] == key:
                # Return physical locations even when a record straddles sectors.
                return [self.at(sectors[i//self.size])+i%self.size for i in range(pos, pos+23)]
        raise ValueError('Missing mutation entry: '+name)

    def row(self, positions):
        return bytes(self.raw[i] for i in positions)


def damaged(raw, case):
    """Return a disposable malformed derivative and its exact changed offsets."""
    media = Media(raw); root = media.word(25)
    row = media.row(media.entry(root, 'LARGE.BIN')); large = int.from_bytes(row[1:3], 'little')
    if case == 'revision': media.raw[48] = 0x11
    elif case == 'geometry': media.raw[47] = 1
    elif case == 'root_reserved': media.put(25, 1)
    elif case == 'map_cycle': media.put(media.at(large), large)
    elif case == 'map_backlink': media.put(media.at(large)+2, large)
    elif case == 'map_short': media.put(media.at(large), 0)
    elif case == 'data_reserved': media.put(media.at(large)+4, 1)
    elif case == 'sparse_directory': media.put(media.at(root)+4, 0)
    elif case == 'directory_length': media.raw[media.at(media.word(media.at(root)+4))+3] = 1
    elif case == 'open_for_write': media.raw[media.entry(root, 'BINARY.BIN')[0]] |= 0x80
    else: raise ValueError('Unknown SDFS damage case: '+case)
    changes = [dict(offset=i, before=a, after=b) for i, (a, b) in enumerate(zip(raw, media.raw)) if a != b]
    require(bool(changes), 'Ineffective fixture mutation')
    return bytes(media.raw), changes


DAMAGE_CASES = ('revision', 'geometry', 'root_reserved', 'map_cycle', 'map_backlink',
                'map_short', 'data_reserved', 'sparse_directory', 'directory_length', 'open_for_write')


def pattern(size, seed=0, zero=False):
    return bytes(size) if zero else bytes((i & 255)^seed for i in range(size))


def jobs():
    return [dict(name='EMPTY', size=0, seed=0),
            dict(name='BINARY.BIN', size=777, seed=0x53),
            dict(name='LARGE.BIN', size=70003, seed=0x81),
            dict(name='SPARSE.BIN', size=1024, seed=0, zero=True),
            dict(name='TOOLS/SUB/TEXT.TXT', size=259, seed=0x22),
            dict(name='MANY/F000.BIN', size=1, seed=0),
            dict(name='MANY/F255.BIN', size=4, seed=255),
            dict(name='MANY/F299.BIN', size=4, seed=43)]


def verifier(output):
    table, names = ['table:'], []
    for index, job in enumerate(jobs()):
        table += [f'.word name{index}', '.byte '+','.join(map(str, [job['size']&255, (job['size']>>8)&255, job['size']>>16, job['seed'], int(job.get('zero', False))]))]
        names += [f'name{index}: .byte "D1:{job["name"].replace("/", ">")}",0']
    (output/'verify-jobs.inc').write_text('\n'.join(table+['.word 0']+names)+'\n')
    (output/'verify.cfg').write_text('MEMORY { RAM: start=$6000,size=$3000,file=%O; } SEGMENTS { CODE: load=RAM,type=ro; }\n')
    subprocess.run(['ca65', '-I', str(output), '-o', str(output/'verify.o'), str(FIXTURES/'verify.s')], check=True)
    subprocess.run(['ld65', '-C', str(output/'verify.cfg'), '-o', str(output/'verify.bin'), '-Ln', str(output/'verify.lbl'), str(output/'verify.o')], check=True)
    labels = {s.split()[2].lstrip('.'): int(s.split()[1], 16) for s in (output/'verify.lbl').read_text().splitlines()}
    raw = (output/'verify.bin').read_bytes()
    return struct.pack('<HHH', 65535, 0x6000, 0x6000+len(raw)-1)+raw+struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']), labels


def original_readback(image, labels, output):
    car = ROOT/'build/development/spartados-s1/SDX450_maxflash1.car'
    if not car.exists():
        car.parent.mkdir(parents=True, exist_ok=True)
        car.write_bytes(urllib.request.urlopen(CAR_URL, timeout=30).read())
    require(sha256(car) == CAR_SHA, 'Unpinned original SDX cartridge')
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        b.config('siopatch', 'on'); b.config('diskemu', 'fastest')
        b.config('accuratedisk', 'false'); b.config('burstio', 'true')
        b.mount(0, str(image)); b.bp_set(labels['done']); b.bp_set(labels['failed']); b.boot(str(car))
        b.resume(); deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            regs = b.regs(); pc = int(regs['PC'].lstrip('$'), 16)
            if pc in (labels['done'], labels['failed']): break
            time.sleep(.05)
        b.pause()
        (output/'screen.png').write_bytes(b.screenshot())
        (output/'screen.bin').write_bytes(b.memdump(b.peek16(88), 960))
        result = b.peek(labels['result'])[0]; job = b.peek(labels['job_index'])[0]
        sparse_status = b.peek(labels['sparse_status'])[0]
        require(pc == labels['done'] and result == 1, f'SDX readback failed: PC={pc:04x}, status={result}, Y={regs["Y"]}, job={job}')
        require(sparse_status == 135, 'Original SDX did not observe the sparse gap')
    return dict(status='pass', machine=machine, overrides=dict(siopatch='on', diskemu='fastest', accuratedisk=False, burstio=True),
                cartridge_sha256=CAR_SHA, cartridge_url=CAR_URL, verifier_sha256=sha256(output.parent/'verify.bin'),
                sparse_gap_status=sparse_status, jobs=jobs())


def produce(output, original=True):
    output.mkdir(parents=True, exist_ok=True)
    payload, labels = verifier(output)
    records = []
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)/'source'; source.mkdir()
        expected = {j['name']: pattern(j['size'], j['seed'], j.get('zero', False)) for j in jobs()}
        expected.update({f'MANY/F{i:03}.BIN': pattern(i%4+1, i&255) for i in range(300)})
        expected.update({'READBACK.COM': payload, 'AUTOEXEC.BAT': b'D1:READBACK.COM\x9b', 'CONFIG.SYS': b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b'})
        for name, data in expected.items():
            path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        for size in (128, 256):
            base = output/f'base-{size}.atr'
            reference.make(base, source, 2000, size)
            media = Media(base.read_bytes()); root = media.word(25)
            # Fragment LARGE by reversing the physical placement of its data.
            row = media.row(media.entry(root, 'LARGE.BIN'))
            pages, sectors = media.chain(int.from_bytes(row[1:3], 'little'))
            sectors = [n for n in sectors if n]
            data = [bytes(media.raw[media.at(n):media.at(n)+size]) for n in sectors]
            for sector, raw in zip(reversed(sectors), data): media.raw[media.at(sector):media.at(sector)+size] = raw
            for index, sector in enumerate(reversed(sectors)):
                media.put(media.at(pages[index//((size-4)//2)])+4+2*(index%((size-4)//2)), sector)
            # A sparse hole occupies no sector. Release it in the allocation bitmap.
            row = media.row(media.entry(root, 'SPARSE.BIN')); page = int.from_bytes(row[1:3], 'little')
            hole = media.word(media.at(page)+6); media.put(media.at(page)+6, 0)
            bitmap = media.word(32); at = media.at(bitmap+hole//(size*8))+(hole//8)%size
            media.raw[at] |= 0x80 >> (hole&7)
            media.put(29, media.word(29)+1)
            for revision in (0x20, 0x21):
                variant = Media(media.raw); variant.raw[48] = revision
                if revision == 0x20: variant.raw[49:54] = bytes(5)
                name = f'sdfs-{revision:02x}-{size}.atr'; image = FIXTURES/name
                image.write_bytes(variant.raw)
                hashes = reference.verify(image, expected, Path(temp)/name)
                evidence = original_readback(image, labels, output/name) if original else None
                records.append(dict(image=name, sha256=sha256(image), sector_bytes=size, sectors=2000,
                                    revision=revision, files=hashes, original_readback=evidence,
                                    mutations={case: damaged(variant.raw, case)[1] for case in DAMAGE_CASES}))
                print('SDFS fixture:', name, 'verified', flush=True)
    record = dict(source_sha256=reference.FILES, producer_sha256=sha256(reference.reference()), fixtures=records)
    record['producer_inputs'] = json.loads((ROOT/'build/sdfs-reference/inputs.json').read_text())
    record['original_system_pin'] = PIN
    record['original_emulator_sha256'] = sha256(ROOT/'build/altirra-sio-multi/AltirraBridgeServer')
    record['verifier_source_sha256'] = sha256(FIXTURES/'verify.s')
    (FIXTURES/'reference.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, default=ROOT/'build/development/spartados-s1')
    args = parser.parse_args(); produce(args.output.resolve())
