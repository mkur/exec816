#!/usr/bin/env python3
"""Bounded emitted kernel identity, ROM classification and diagnostic failures."""
import argparse
import copy
import json
from pathlib import Path
import re
import struct
import zlib

import adapter_state as adapter
from generate_memory import PROFILE
from generate_sdx_firmware import catalog, identify
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_boot_diagnostics import os_text
from test_boot_milestones import inject_fault
from test_bootable_atr import wait_at

PIN_PATH = ROOT/'toolchain/altirra-gem-vdi.json'
PIN = json.loads(PIN_PATH.read_text())
BRIDGE = ROOT/'build/mouse-bridge'
ROMS = {
    'altirra': ROOT/'build/firmware/altirraos-816.rom',
    '248': ROOT/'build/xlos-sdx-audit/firmware/xlos-20251207/XLOS816F.ROM',
    '249': ROOT/'build/xlos-sdx-audit/firmware/xlos-20261007/XLOS816F.ROM',
}
CASES = ('altirra', '248', '249', 'quiet', 'fallback', 'fallback-quiet',
         'vector-mismatch', 'bottom', 'mapping', 'state', 'fault')


def call_site(p, name):
    code = (p['output']/'hosted.bin').read_bytes()
    call = b'\x22'+p['labels'][name].to_bytes(3, 'little')
    require(code.count(call) == 1, 'Changed resident call site: '+name)
    return p['labels']['start']+code.index(call)


def profile_table(p):
    """Locate immutable catalog data without exporting a production test ABI."""
    raw = (p['output']/'hosted.bin.sdx').read_bytes()
    pattern = b''.join(struct.pack('<HIHH', item['id'], int(item['visible_crc32'], 16),
                                   item['emulation_nmi'], item['emulation_irq'])
                       for item in catalog()['profiles'])
    require(raw.count(pattern) == 1, 'Changed firmware comparison table')
    config = (p['output']/'hosted-generated.cfg').read_text()
    base = int(re.search(r'SDXWORK: start=\$([0-9a-f]+)', config)[1], 16)
    return base+raw.index(pattern)


def capture_scanout(bridge, address, path):
    """Test-only BRA hold: let ANTIC finish frames before the next boot stage."""
    original = bridge.memdump(address, 2)
    registers = bridge.regs()
    screen = os_text(bridge)
    target = bridge.eval_expr('@frame')+3
    try:
        # BRA preserves registers/flags. IRQ remains masked as at this startup
        # boundary; ordinary VBI runs, with no application/console entry yet.
        bridge.memload(address, b'\x80\xfe')
        wait_at(bridge, address, timeout=10, condition=f'@frame>={target}')
        bridge.screenshot(str(path))
        require(os_text(bridge) == screen, 'Scanout hold changed diagnostic text')
        after = bridge.regs()
        for key in ('A', 'X', 'Y', 'S', 'P', 'D', 'DBR', 'E'):
            if key in registers:
                require(after[key] == registers[key], 'Scanout hold changed '+key)
    finally:
        bridge.memload(address, original)
        bridge.bp_clear_all()


def run(out, selected=None, replay=False):
    out.mkdir(parents=True, exist_ok=True)
    if replay:
        p = read_build(out/'probe')
    else:
        memory = json.loads(PROFILE.read_text())
        memory['image_data_bytes'] = 4352
        profile = out/'probe-memory.json'
        profile.write_text(json.dumps(memory, indent=2)+'\n')
        p = build(compiler(ROOT/'build/actionc', release=True),
                  ROOT/'tests/programs/boot_rom_diagnostics.act', out/'probe',
                  tasks=True, task_capacity=12, console=False,
                  console_deferred=True, sdx=True, memory_profile=profile)
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Changed pinned emulator')
    before_install = call_site(p, 'sdx_probe_install')
    before_report = call_site(p, 'boot_rom_diagnostics')
    table = profile_table(p)
    title = p['build']['exec_build']['strings']['banner'].strip()
    records = []
    report = dict(status='running', tier='development', qualification=False,
                  source=p['build']['exec_build'], xex_sha256=sha256(p['xex']),
                  pin_sha256=sha256(PIN_PATH), emulator_sha256=PIN['emulator']['sha256'],
                  cases=records, reserved_bank_zero_delta=dict(
                      fixed=0, root_kernel=0, per_public_task=[0]*12, idle=0))
    try:
        for name in selected or CASES:
            rom = ROMS[name if name in ROMS else '249' if name in
                       ('quiet', 'fallback', 'fallback-quiet', 'vector-mismatch') else 'altirra']
            profile = identify(rom.read_bytes())
            pin = copy.deepcopy(PIN)
            pin['rom'] = {k:profile[k] for k in ('name', 'bytes', 'sha256')}
            folder = out/name
            record = dict(name=name, firmware=profile, status='running')
            records.append(record)
            print(name, 'booting', flush=True)
            verbose = name not in ('quiet', 'fallback-quiet', 'mapping', 'state', 'fault')
            expected = 0xff93 if name in ('mapping', 'state') else 0xf731 if name == 'fault' else 0
            with emulator(BRIDGE, rom, folder, pin=pin) as b:
                b.config('exeloadmode', 'diskboot')
                record['machine'] = verify_machine(b, rom, pin)

                def prepare(bridge):
                    if name == 'bottom':
                        screen = bridge.peek16(0x58)
                        bridge.poke(0x54, 23)
                        bridge.memload(0x55, bytes([0, 0]))
                        bridge.memload(0x5e, (screen+920).to_bytes(2, 'little'))
                        bridge.poke(0x2f0, 1)
                        bridge.memload(0x52, bytes([2, 30]))
                    wait_at(bridge, before_install, (p['labels']['done'],), 30)
                    require(title in os_text(bridge), 'Identity missing before ROM installation')
                    if name.startswith('fallback'):
                        # Fault injection changes only the private comparison table;
                        # the running ROM and installed shadow remain original bytes.
                        for index in range(len(catalog()['profiles'])):
                            at = table+index*10+2
                            value = bridge.peek16(at)^1
                            bridge.memload(at, value.to_bytes(2, 'little'))
                        record['injection'] = 'Private catalog CRC mismatch'
                    elif name == 'vector-mismatch':
                        at = table+(profile['id']-1)*10+6
                        bridge.memload(at, (bridge.peek16(at)^1).to_bytes(2, 'little'))
                        record['injection'] = 'Private catalog vector mismatch'
                    elif name == 'mapping':
                        bridge.poke(0xd303, bridge.peek(0xd303)[0] & ~4)
                    elif name == 'state':
                        bridge.poke(0x287800, 1)
                    wait_at(bridge, before_report, (p['labels']['done'],), 30)
                    before = bridge.regs()
                    iocb = bridge.memdump(0x340, 16)
                    margins = bridge.memdump(0x52, 2)
                    wait_at(bridge, before_report+4, (p['labels']['done'],), 30)
                    after = bridge.regs()
                    for key in ('A', 'X', 'Y', 'S', 'P', 'D', 'DBR', 'E'):
                        if key in before:
                            require(after[key] == before[key], 'Reporter changed '+key)
                    require(bridge.memdump(0x340, 16) == iocb, 'Reporter changed IOCB0')
                    require(bridge.memdump(0x52, 2) == margins, 'Reporter changed margins')
                    text = os_text(bridge)
                    require(title in text, 'ROM diagnostics scrolled away the identity')
                    record.update(context_before=before, context_after=after,
                                  admission_screen=text)
                    if name == 'bottom':
                        require(margins == bytes([2, 30]), 'Early identity changed margins')
                    if name in ('mapping', 'state'):
                        cause = 1 if name == 'mapping' else 3
                        require('ROM CRC32     =UNAVAILABLE' in text and
                                'ROM PROFILE   =UNAVAILABLE' in text, 'Stale CRC/profile on failure')
                        reason = 'MAPPING' if name == 'mapping' else 'ALREADY INSTALLED'
                        require(f'SDX ROM       =${cause:04X} {reason}' in text,
                                'Missing installation failure detail')
                        if name == 'mapping':
                            require('PIA PBCTL     =' in text and 'PIA PORTB     =' in text,
                                    'Missing mapping registers')
                    elif verbose or name == 'fallback-quiet':
                        require('ROM CRC32     =$'+profile['visible_crc32'].upper() in text,
                                'Incorrect full ROM checksum')
                        fallback = name.startswith('fallback') or name == 'vector-mismatch'
                        label = 'XLOS (assumed)' if fallback else profile['display_name']
                        require('ROM PROFILE   ='+label in text and 'SDX ROM       =OK' in text,
                                'Incorrect firmware classification')
                        if fallback:
                            for label, lo, hi in (('ROM C000-CFFF=', 0, 0x1000),
                                                  ('ROM D800-DFFF=', 0x1800, 0x2000),
                                                  ('ROM E000-FFFF=', 0x2000, 0x4000)):
                                value = zlib.crc32(rom.read_bytes()[lo:hi])
                                require(label[:-1].ljust(14)+'=$'+f'{value:08X}' in text,
                                        'Incorrect section checksum: '+label)
                            for label, key in (('ROM NMI       =', 'emulation_nmi'),
                                               ('ROM IRQ       =', 'emulation_irq')):
                                require(label+f'${profile[key]:04X}' in text,
                                        'Incorrect captured vector')
                    else:
                        require('ROM CRC32' not in text, 'Quiet success printed ROM inventory')
                    if name == 'fault':
                        at = p['labels']['heap_fault']
                        finish = int.from_bytes(bridge.memdump(at+3, 2), 'little')
                        inject_fault(bridge, p['labels']['task_start'], finish, 0xf731, True)
                    bridge.bp_clear_all()

                runtime, _ = execute(b, p, expected_status=expected, before_run=prepare,
                                     boot_verbose=verbose, timeout=45, frame_limit=2400)
                text = os_text(b)
                if name in ('mapping', 'state', 'fault'):
                    cause = 1 if name == 'mapping' else 3 if name == 'state' else 0xf731
                    require(f'System halted: ${cause:04X}' in text, 'Original cause lost')
                    require(b.peek16(adapter.BOOT_CAUSE) == cause, 'Saved first cause differs')
                else:
                    require('System halted:' not in text, 'Normal return reported a halt')
                    if verbose or name == 'fallback-quiet':
                        require('VBI/IRQ       =OK' in text if verbose else 'VBI/IRQ' not in text,
                                'Incorrect success milestone verbosity')
                if name in ('mapping', 'state', 'fault'):
                    capture_scanout(b, p['labels']['done'], folder/'diagnostics.png')
                    record['scanout_hold'] = 'Test-only BRA for three ANTIC frames after terminal reporting'
                else:
                    b.screenshot(str(folder/'diagnostics.png'))
                record.update(status='pass', runtime=runtime, final_screen=text)
            print(name, 'passed', flush=True)
        report['status'] = 'pass'
    finally:
        report['observer_sha256'] = sha256(Path(__file__))
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=CASES, action='append')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.case, args.replay)
