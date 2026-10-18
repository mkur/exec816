#!/usr/bin/env python3
"""P2 early IRQ/NMI routing on pinned AltirraOS; no SDX Task admission yet."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time

from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator, run_to

PIN_PATH = ROOT/'toolchain/altirra-shell-paced.json'
PIN = json.loads(PIN_PATH.read_text())
SOURCE = ROOT/'probes/sdx-runtime'
ROM = ROOT/'build/firmware/altirraos-816.rom'
BRIDGE = ROOT/'build/shell-paced-bridge'


def build(out, bank, dp, flags, accumulator, phase):
    out.mkdir(parents=True, exist_ok=True)
    definitions = dict(GUEST_BANK=bank, GUEST_DP=dp, GUEST_FLAGS=flags,
                       ACCUMULATOR=accumulator, PHASE=phase)
    subprocess.run(['ca65', '-I', str(ROOT/'platform/altirraos'),
                    *[a for k, v in definitions.items() for a in ('-D', f'{k}={v}')],
                    '-l', str(out/'probe.lst'), '-o', str(out/'probe.o'),
                    str(SOURCE/'probe.s')], check=True, timeout=30)
    subprocess.run(['ld65', '-D', f'GUEST_ORIGIN={bank*65536+0x3000}',
                    '-C', str(SOURCE/'probe.cfg'), '-o', str(out/'probe.bin'),
                    '-Ln', str(out/'probe.lbl'), str(out/'probe.o')], check=True, timeout=30)
    labels = {}
    for line in (out/'probe.lbl').read_text().splitlines():
        _, address, name = line.split()
        labels[name.lstrip('.')] = int(address, 16)
    raw = (out/'probe.bin').read_bytes()
    require(len(raw) <= 0x1100, 'Probe payload overlaps ROM staging')
    xex = out/'probe.xex'
    xex.write_bytes(struct.pack('<HHH', 65535, 0x3000, 0x3000+len(raw)-1)+raw
                    +struct.pack('<HH', 0x5000, 0x8fff)+ROM.read_bytes()
                    +struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    return xex, labels


def execute(out, bank, dp, flags, accumulator, phase):
    require(sha256(ROM) == PIN['rom']['sha256'], 'ROM hash differs from pin')
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Emulator hash differs from pin')
    xex, labels = build(out, bank, dp, flags, accumulator, phase)
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.boot(str(xex))
        run_to(b, labels['start'])
        machine = verify_machine(b, ROM, PIN)
        b.bp_set(labels['installed'])
        b.bp_set(labels['done'])
        run_to(b, labels['installed'])
        portb = b.memdump(0xd301, 1)[0]
        require(portb & 1 == 0, 'ROM mapping was not replaced')
        effective = bytearray(ROM.read_bytes())
        effective[0x3ffa:0x3ffc] = labels['emulation_nmi'].to_bytes(2, 'little')
        effective[0x3ffe:0x4000] = labels['emulation_irq'].to_bytes(2, 'little')
        require(b.memdump(0xc000, 0x1000) == effective[:0x1000], 'Low ROM shadow differs')
        require(b.memdump(0xd800, 0x2800) == effective[0x1800:], 'High ROM shadow differs')
        start_clock = int.from_bytes(b.memdump(0x12, 3), 'big')
        b.bp_clear_all()
        b.bp_set(labels['done'])
        try:
            run_to(b, labels['done'], frame_limit=120, timeout=20)
        except Exception:
            print('Runtime state:', b.memdump(0x2000, 32).hex(), 'CPU:', b.regs(), flush=True)
            raise
        state = b.memdump(0x2000, 32)
        log = b.memdump(0x2600, 32*16)
        (out/'state.bin').write_bytes(state)
        (out/'contexts.bin').write_bytes(log)
        word = lambda offset: int.from_bytes(state[offset:offset+2], 'little')
        require(word(12) == 255, f'Probe failed: {state.hex()}')
        require(word(6) == 32, 'Wrong retired VBI count')
        require(word(8) > 0 if not flags & 4 else word(8) == 0, 'IRQ masking/progress differs')
        require(not phase or word(10) > 0, 'Injected native NMI did not defer')
        end_clock = int.from_bytes(b.memdump(0x12, 3), 'big')
        require((end_clock-start_clock) % (1 << 24) >= 32, 'Normal OS clock did not advance')
        expected_registers = bytes([bank])+struct.pack('<4H', dp, 0xa6, 0x5a, accumulator)
        loop_frames = 0
        for i in range(32):
            record = log[i*16:(i+1)*16]
            require(record[:9] == expected_registers, f'Context {i} registers differ: {record.hex()}')
            pc = int.from_bytes(record[11:13], 'little')
            if pc == labels['guest_loop'] & 0xffff:
                require(record[10] == flags, f'Context {i} status differs: {record.hex()}')
                require(record[13:15] == bytes.fromhex('e001'), 'Guest stack drifted')
                loop_frames += 1
            else:
                require(labels['guest_return'] & 0xffff <= pc < labels['guest_end'] & 0xffff,
                        f'Unexpected guest PC: {pc:04x}')
        require(loop_frames > 20, 'Too few steady guest frames')
        for address in (dp-16, dp+256, 0x23f0, 0x2500, 0x46f0, 0x4800):
            require(b.memdump(address, 16) == bytes([0xa5])*16,
                    f'Domain guard changed at ${address:04x}')
        require(b.memdump(dp, 256) == bytes([0xa5])*256, 'Guest DP was corrupted')
        require(b.memdump(bank*65536+0xd40f, 1) == b'\xff', 'Guest I/O alias was accessed')
        require(b.memdump(0xd301, 1) == state[19:20], 'PORTB was not restored')
        require(b.memdump(0xc000, 0x1000) == ROM.read_bytes()[:0x1000], 'ROM not restored')
        require(b.memdump(0xd800, 0x2800) == ROM.read_bytes()[0x1800:], 'ROM vectors not restored')
        # Inspect underlying RAM only after all test IRQ/NMI have been stopped.
        b.poke(0xd301, portb)
        low, high = b.memdump(0xc000, 0x1000), b.memdump(0xd800, 0x2800)
        b.poke(0xd301, state[19])
        require(low == b''.join(struct.pack('<H', i ^ 0x5aa5) for i in range(0, 0x1000, 2)),
                'Low RAM under ROM was not restored')
        require(high == b''.join(struct.pack('<H', i ^ 0xa55a) for i in range(0, 0x2800, 2)),
                'High RAM under ROM was not restored')
        return dict(status='pass', machine=machine, guest_bank=bank, guest_dp=dp,
                    flags=flags, accumulator=accumulator, phase=phase,
                    vbis=word(6), timer_irqs=word(8), deferred_native_nmis=word(10),
                    os_clock_ticks=(end_clock-start_clock) % (1 << 24),
                    steady_guest_frames=loop_frames, rom_and_underlay_restored=True,
                    effective_rom_sha256=hashlib.sha256(effective).hexdigest(),
                    vector_patches=[dict(address=address, expected=ROM.read_bytes()[address-0xc000:address-0xc000+2].hex(),
                                         replacement=effective[address-0xc000:address-0xc000+2].hex())
                                    for address in (0xfffa, 0xfffe)],
                    shadow_code_bytes=labels['sdx_rom_end']-labels['sdx_rom_install'],
                    xex_sha256=sha256(xex))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/sdx-runtime')
    parser.add_argument('--phase', type=int, choices=range(5), default=0)
    parser.add_argument('--bank', type=int, choices=(2, 3), default=2)
    parser.add_argument('--masked', action='store_true')
    args = parser.parse_args()
    started = time.monotonic()
    out = args.output.resolve()
    result = dict(status='running')
    try:
        result = execute(out, args.bank, 0x2200 if args.bank == 2 else 0x2100,
                         0xed if args.masked else 0xe9,
                         0xabcd if args.bank == 2 else 0x1265, args.phase)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        result.update(tier='development', scope='Standalone P2 early IRQ/NMI and ROM-shadow component; no Exec Tasks or SDX application',
                      pin=str(PIN_PATH.relative_to(ROOT)), rom_sha256=PIN['rom']['sha256'],
                      emulator_sha256=PIN['emulator']['sha256'],
                      production_bank_zero_delta=dict(fixed=0, per_task=0),
                      seconds=round(time.monotonic()-started, 3),
                      inputs={str(p.relative_to(ROOT)): sha256(p) for p in
                              (SOURCE/'probe.s', SOURCE/'probe.cfg', Path(__file__),
                               ROOT/'platform/altirraos/sdx-rom-shadow.s')})
        out.mkdir(parents=True, exist_ok=True)
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('status', 'vbis', 'timer_irqs', 'deferred_native_nmis', 'seconds')}))


if __name__ == '__main__':
    main()
