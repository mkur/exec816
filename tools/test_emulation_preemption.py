#!/usr/bin/env python3
"""Bounded E=1 guest / E=0 NMI experiment on the pinned AltirraOS ROM."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import time

from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator, run_to

PIN_PATH = ROOT / 'toolchain/altirra-shell-paced.json'
PIN = json.loads(PIN_PATH.read_text())
SOURCE = ROOT / 'probes/emulation-preemption'


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    prefix = out / 'probe'
    subprocess.run(['ca65', '-l', str(prefix.with_suffix('.lst')),
                    '-o', str(prefix.with_suffix('.o')), str(SOURCE / 'probe.s')],
                   check=True, timeout=30)
    subprocess.run(['ld65', '-C', str(SOURCE / 'probe.cfg'),
                    '-o', str(prefix.with_suffix('.bin')),
                    '-Ln', str(prefix.with_suffix('.lbl')), str(prefix.with_suffix('.o'))],
                   check=True, timeout=30)
    labels = {}
    for line in prefix.with_suffix('.lbl').read_text().splitlines():
        _, address, label = line.split()
        labels[label.lstrip('.')] = int(address, 16)
    raw = prefix.with_suffix('.bin').read_bytes()
    require(len(raw) <= 0x1100, 'Probe exceeds reserved payload capacity')
    xex = prefix.with_suffix('.xex')
    xex.write_bytes(struct.pack('<HHH', 0xffff, 0x3000, 0x3000+len(raw)-1)
                    +raw+struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    return xex, labels


def execute(out, xex, labels):
    rom = ROOT / 'build/firmware/altirraos-816.rom'
    bridge_dir = ROOT / 'build/shell-paced-bridge'
    require(sha256(rom) == PIN['rom']['sha256'], 'ROM hash differs from pin')
    require(sha256(bridge_dir / 'AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Emulator hash differs from pin')
    with emulator(bridge_dir, rom, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.boot(str(xex))
        run_to(b, labels['start'])
        machine = verify_machine(b, rom, PIN)
        regs = b.regs()
        for key, value in dict(mode='65C816', clock_multiplier=8, shadow_rom=True).items():
            require(regs[key] == value, 'Wrong CPU configuration: '+key)
        b.bp_set(labels['done'])
        # Negative control: execute the guest for several actual frames with
        # NMI disabled. Host writes only NMIEN, never a CPU mode/PC/register.
        frame = b.eval_expr('@frame')
        b.resume()
        deadline = time.monotonic()+10
        while b.eval_expr('@frame')-frame < 4:
            require(time.monotonic() < deadline, 'Guest did not run four frames')
            time.sleep(.02)
        b.pause()
        pc = b.eval_expr('@xpc')
        # PAUSE can stop inside JMP after its operand fetch, before PC changes.
        require(labels['guest_loop'] <= pc <= labels['guest_return'],
                f'Guest missed upper-bank loop: PC=${pc:06x}, regs={b.regs()}, '
                f'state={b.memdump(0x2000, 32).hex()}')
        control = b.memdump(0x2000, 32)
        require(control[0x10:0x14] == bytes(4), 'Native work advanced without NMI')
        require(b.memdump(0x2400, 2) == bytes(2), 'Worker ran without NMI')
        require(control[0x14:0x16] == bytes([0x69, 0x96]),
                'E=1 wrap / E=0 linear addressing control differs')
        require(int(b.regs()['P'].lstrip('$'), 16) & 4, 'Guest SEI was lost')
        b.poke(0xd40e, 0x40)
        run_to(b, labels['done'], frame_limit=100, timeout=15)
        state = b.memdump(0x2000, 32)
        log = b.memdump(0x2600, 65*16)
        page = b.memdump(0x0100, 256)
        (out / 'state.bin').write_bytes(state)
        (out / 'contexts.bin').write_bytes(log)
        (out / 'page-one.bin').write_bytes(page)
        word = lambda offset: int.from_bytes(state[offset:offset+2], 'little')
        require(state[0x16] == 0xff, 'Probe did not complete')
        require(word(0x10) == 64, 'Wrong native worker count')
        require(word(0x12) >= 1 and word(0x18) == 1, 'Nested native NMI did not restore domain')
        require(b.memdump(0x2400, 2) == struct.pack('<H', 64*7), 'Native DP progress differs')
        expected = (struct.pack('<5H', 0xabcd, 0x5a, 0xa6, 0x01ed, 0x2200)
                    +bytes([3, 1, 0xed])+struct.pack('<H', labels['guest_loop'] & 0xffff)+b'\0')
        for index in range(65):
            actual = log[index*16:(index+1)*16]
            require(actual == expected,
                    f'Guest context {index}: {actual.hex()}, expected {expected.hex()}')
        expected_page = bytearray([0xa5]*256)
        # Six bytes pushed by hardware + ROM, followed by two live guest bytes.
        expected_page[0xe8:0xf0] = (bytes([0xa6, 0x5a, 0xcd, 0xed])
                                  +struct.pack('<H', labels['guest_loop'] & 0xffff)
                                  +bytes([0x34, 0x12]))
        require(page == expected_page, 'Guest page-one bytes were not restored exactly')
        require(b.memdump(0x2300, 256) == page, 'Guest stack shadow differs')
        for address in (0x21f0, 0x2500, 0x4700, 0x47f0, 0x4800):
            require(b.memdump(address, 16) == bytes([0xa5])*16,
                    f'Domain guard changed at ${address:04x}')
        return dict(status='pass', machine=machine, negative_control_frames=4,
                    guest_entries=65, guest_restorations=64, native_work_counter=448,
                    native_nmis=word(0x12), native_domain_restored=True,
                    guest_context=dict(a=0xabcd, x=0x5a, y=0xa6, s=0x01ed, d=0x2200,
                                       dbr=3, pbr=2, e=1, stacked_p=0xed),
                    indexed_dp=dict(emulation=0x69, native=0x96),
                    page_one_restored_bytes=256, guards='pass')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/emulation-preemption')
    args = parser.parse_args()
    out = args.output.resolve()
    started = time.monotonic()
    xex, labels = build(out)
    result = execute(out, xex, labels)
    result.update(scope='Standalone assembly CPU/ROM development experiment; no Exec Tasks or SDX binary',
                  pin=str(PIN_PATH.relative_to(ROOT)), rom_sha256=PIN['rom']['sha256'],
                  emulator_sha256=PIN['emulator']['sha256'], xex_sha256=sha256(xex),
                  inputs={str(p.relative_to(ROOT)): sha256(p)
                          for p in [SOURCE / 'probe.s', SOURCE / 'probe.cfg', Path(__file__)]},
                  seconds=round(time.monotonic()-started, 3),
                  production_bank_zero_delta=dict(fixed=0, per_task=0))
    (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
