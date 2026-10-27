#!/usr/bin/env python3
"""Emitted ATR reader negotiation with real FujiNet starting at either speed."""
import argparse
import copy
import json
from pathlib import Path
import struct

from build_boot_fast import segment
from build_bootable_atr import build as disk
from fujinet_pc_peer import FujiNetPC
from generate_sdx_firmware import identify
from native_program import ROOT, require, sha256
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import boot_environment

ROMS = {
    'altirra': ROOT/'build/firmware/altirraos-816.rom',
    '248': ROOT/'build/xlos-sdx-audit/firmware/xlos-20251207/XLOS816F.ROM',
    '249': ROOT/'build/xlos-sdx-audit/firmware/xlos-20261007/XLOS816F.ROM',
}
CASES = {
    'altirra-standard': ('altirra', 19200, 'auto'),
    'altirra-fast': ('altirra', 57600, 'auto'),
    'xlos248-natural': ('248', None, 'auto'),
    'xlos249-natural': ('249', None, 'auto'),
    'xlos249-standard': ('249', 19200, 'auto'),
    'xlos249-fast': ('249', 57600, 'auto'),
    'standard-policy-fast': ('altirra', 57600, 'standard'),
}


def peripheral_speed(bridge, labels, at, peer, speed):
    """Use the real emitted engine/firmware query, never forge endpoint state."""
    if peer.peripheral_baud == speed:
        return False
    require(peer.peripheral_baud in (19200, 57600), 'Unexpected initial peer speed')
    original = bridge.memdump(at, 3)
    scratch = bridge.memdump(0x6000, 6)
    # This fixture's payload starts at $6400; $6000 is disposable test scratch.
    # Tail-JMP from the paused entry keeps its page-one caller frame intact.
    bridge.memload(0x6000, b'\x20'+struct.pack('<H', labels['bo_transfer'])+
                   b'\x4c'+struct.pack('<H', at))
    bridge.memload(0x0300, bytes([0x31, 1, 0x3f, 0x40])+
                   struct.pack('<H', labels['boot_reply'])+bytes([3, 0, 1, 0, 0, 0]))
    bridge.poke(labels['bo_divisor'], 8 if peer.peripheral_baud == 57600 else 40)
    bridge.memload(at, b'\x4c\x00\x60')
    wait_at(bridge, 0x6003, (labels['reader_failed'],), 15)
    require(bridge.eval_expr('@y') & 255 == 1 and peer.peripheral_baud == speed,
            'Preparation query did not establish requested peer speed')
    bridge.memload(at, original)
    wait_at(bridge, at, (labels['reader_failed'],), 15)
    bridge.memload(0x6000, scratch)
    # Reader image initialization assumes divisor 40 regardless of ROM speed.
    bridge.poke(labels['bo_divisor'], 40)
    return True


def run(output, bundle, firmware, selected=None):
    output.mkdir(parents=True, exist_ok=True)
    monitor = json.loads((bundle/'of816/of816.json').read_text())
    original_pin, binary, _ = boot_environment(monitor)
    cases = []
    report = dict(status='running', tier='development', qualification=False,
                  observer_sha256=sha256(Path(__file__)),
                  emulator_sha256=sha256(binary/'AltirraBridgeServer'),
                  firmware_sha256=sha256(firmware), cases=cases,
                  source_inputs={p:sha256(ROOT/p) for p in (
                      'platform/altirraos/boot-sio-policy.inc',
                      'platform/altirraos/boot-sio.inc',
                      'platform/altirraos/disk-boot-reader.s')})
    try:
        for name in selected or CASES:
            family, initial, policy = CASES[name]
            folder = output/name
            folder.mkdir(parents=True, exist_ok=True)
            source = folder/'source'
            source.mkdir(exist_ok=True)
            xex = folder/'probe.xex'
            payload = bytes(range(256))*16
            xex.write_bytes(b'\xff\xff'+segment(0x6400, payload)+
                            segment(0x6200, b'\x4c\x00\x62')+
                            segment(0x2e0, struct.pack('<H', 0x6200)))
            media = folder/'probe.atr'
            build = disk(media, source, xex, folder/'reader', boot_sio=policy)
            labels = build['reader']['disk-boot-reader.s']['labels']
            entry = labels['reader_start']
            # CLD; JSR platform preparation; JSR speed selection. No test ABI.
            raw = (folder/'reader/disk-boot-reader.bin').read_bytes()
            offset = entry-0x4000
            require(raw[offset] == 0xd8 and raw[offset+1] == raw[offset+4] == 0x20,
                    'Changed reader startup sequence')
            at = entry+4
            rom = ROMS[family]
            profile = identify(rom.read_bytes())
            pin = copy.deepcopy(original_pin)
            pin['rom'] = {k:profile[k] for k in ('name', 'bytes', 'sha256')}
            item = dict(name=name, status='running', policy=policy, firmware=profile)
            cases.append(item)
            print(name, 'booting', flush=True)
            with FujiNetPC(folder/'peer', media, firmware, readonly=True, hsio_index=8) as peer:
                with emulator(binary, rom, folder/'emulator', pin=pin) as bridge:
                    for key, value in [('siopatch','off'), ('burstio','false'), ('fastboot','false')]:
                        bridge.config(key, value)
                    bridge.device_set('custom', path=str(peer.script), hotreload=False, allowunsafe=True)
                    item.update(machine=bridge.config(), machine_pin=pin['machine'])
                    bridge.cold_reset()
                    wait_at(bridge, at, (labels['reader_failed'],), 90)
                    item['rom_handoff_baud'] = peer.peripheral_baud
                    item['preparation_query'] = peripheral_speed(bridge, labels, at, peer, initial) if initial else False
                    item['initial_baud'] = peer.peripheral_baud
                    vectors = bridge.memdump(0x20a, 6)
                    mask = bridge.peek(0x10)
                    critic = bridge.peek(0x42)
                    clock = bridge.peek(0x14)
                    start = len(peer.commands)
                    wait_at(bridge, labels['xex_start'], (labels['reader_failed'],), 30)
                    divisor = bridge.peek(labels['bo_divisor'])[0]
                    item['selected_divisor'] = divisor
                    require(divisor == (8 if policy == 'auto' else 40),
                            f'{name}: selected divisor {divisor}, expected high speed after synchronization')
                    wait_at(bridge, 0x6200, (labels['reader_failed'],), 60)
                    require(bridge.memdump(0x6400, len(payload)) == payload, 'Payload changed')
                    require(bridge.memdump(0x20a, 6) == vectors and bridge.peek(0x10) == mask and
                            bridge.peek(0x42) == critic, 'Serial ownership was not restored')
                    require(bridge.peek(0x14) != clock, 'ROM VBI did not run')
                    for key in ('reader_guard_low', 'reader_guard_high'):
                        require(bridge.memdump(labels[key], 16) == b'\xa5'*16, 'Reader guard changed')
                    item.update(frame=bridge.eval_expr('@frame'), guards='intact', vectors_restored=True)
            require(peer.error is None, str(peer.error))
            relay = json.loads((folder/'peer/relay.json').read_text())
            bulk = [c for c in relay['commands'][start:] if c['device'] == 0x31 and c['command'] == 0x52]
            baud = 57600 if policy == 'auto' else 19200
            require(bulk and all(c['host_baud'] == c['peripheral_baud'] == baud and
                                not c['rate_mismatch'] for c in bulk), 'Bulk rate mismatch/fallback hidden')
            item.update(status='pass', bulk_reads=len(bulk), bulk_baud=baud, relay=relay)
            print(name, 'passed:', item['initial_baud'], '->', baud, flush=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=ROOT/'build/rom-diagnostics/demo')
    parser.add_argument('--fujinet-pc', type=Path, default=Path.home()/'atari/fujinet-firmware/build/fujinet')
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    run(args.output.resolve(), args.bundle.resolve(), args.fujinet_pc.resolve(), args.case)
