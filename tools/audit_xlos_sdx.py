#!/usr/bin/env python3
"""Bounded current SDX firmware acceptance without ROM or jump injection."""
import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import struct
import subprocess

from generate_sdx_firmware import identify
from sdx_firmware_stack import support_bound
from native_program import ROOT, execute, read_build, require, sha256
from os_boundary import decode, emulator, run_to
from test_bootable_atr import wait_at
from test_boot_diagnostics import os_text
import test_sdx_runtime as component

PIN_PATH = ROOT / 'toolchain/altirra-gem-vdi.json'
PIN = json.loads(PIN_PATH.read_text())
BRIDGE = ROOT / 'build/mouse-bridge'
SOURCE = ROOT / 'probes/xlos-sdx/boundary.s'
ROMS = {
    '2899b04db54bbdef833ce8a203b3cd55c83c8ed78c1feaa158bf7dc13d4f9da5': '2.48 F',
    'd539c4acaec2350d0b9d42f73c242446712ffcbd8b636dce587cd00679f7b097': '2.49 F',
}


def native_case(rom, out, case, flags):
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ca65', '-D', f'CASE={case}', '-D', f'FLAGS={flags}',
                    '-o', str(out/'probe.o'), str(SOURCE)], check=True)
    subprocess.run(['ld65', '-C', str(ROOT/'probes/os-boundary/probe.cfg'),
                    '-o', str(out/'probe.bin'), '-Ln', str(out/'probe.lbl'),
                    str(out/'probe.o')], check=True)
    labels = {s.split()[2].lstrip('.'): int(s.split()[1], 16)
              for s in (out/'probe.lbl').read_text().splitlines()}
    raw = (out/'probe.bin').read_bytes()
    xex = out/'probe.xex'
    xex.write_bytes(struct.pack('<HHH', 65535, 0x3000, 0x3000+len(raw)-1)
                    + raw + struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    with emulator(BRIDGE, rom, out, pin=PIN) as b:
        b.config('exeloadmode', 'diskboot')
        b.boot(str(xex))
        b.bp_set(labels['start'])
        run_to(b, labels['start'])
        clock_before = b.peek(0x14)[0]
        b.bp_clear_all()
        b.bp_set(labels['done'])
        run_to(b, labels['done'], frame_limit=120)
        state = decode(b.memdump(0x2000, 64))
        clock_after = b.peek(0x14)[0]
        require(state['completion'] == 255, 'Incomplete native probe')
        require((state['s'], state['d'], state['dbr'], state['e']) ==
                (0x47ef, 0x2200, 0x12, 0), 'Native domain changed')
        require(b.memdump(0x21f0, 0x120) == b'\xa5'*0x120,
                'Private DP or guard changed')
        for at in (0x4700, 0x4800):
            require(b.memdump(at, 16) == b'\xa5'*16, 'Stack guard changed')
        if case == 0:
            require(clock_after != clock_before, 'No OS VBI clock progress')
            expected_xy = (0x34, 0x78) if flags & 0x10 else (0x1234, 0x5678)
            require((state['a'], state['x'], state['y'], state['p']) ==
                    (0xabcd, *expected_xy, flags), 'Interrupted registers changed')
        else:
            require(b.peek(0x2020)[0] == 0x5a and
                    (state['x'], state['y']) == (0x34, 0x78),
                    'COP $00 target or returned registers differ')
    return dict(status='pass', case='vbi' if case == 0 else 'cop0',
                flags=flags, state=state, clock_before=clock_before,
                clock_after=clock_after, guards_intact=True,
                xex_sha256=sha256(xex))


@contextmanager
def diskboot(*args, **kwargs):
    with emulator(*args, **kwargs) as b:
        b.config('exeloadmode', 'diskboot')
        yield b


def component_cases(rom, out, pin):
    component.SOURCE, component.ROM = ROOT/'probes/sdx-runtime', rom
    component.BRIDGE, component.PIN, component.emulator = BRIDGE, pin, diskboot
    return [component.execute(out/str(phase), 2, 0x2200, 0xe9, 0xabcd, phase)
            for phase in range(5)]


def hosted_case(rom, out, bundle):
    p = read_build(bundle)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=True)
    disk = out/'exec816.atr'
    shutil.copyfile(bundle/'exec816.atr', disk)
    cart = bundle/'cartridge/Exec-of816-atarimax-8mbit-new.car'
    # Break before the bank-zero JSL. A low-word breakpoint cannot stop at the
    # upper-bank callee merely by adding an @xpc condition.
    call = b'\x22'+p['labels']['sdx_probe_install'].to_bytes(3, 'little')
    code = (bundle/'hosted.bin').read_bytes()
    require(code.count(call) == 1, 'Changed install call site')
    before_install = 0x1600+code.index(call)
    result = dict(cart_sha256=sha256(cart),
                  xex_sha256=sha256(p['xex']))
    with emulator(BRIDGE, rom, out, pin=PIN) as b:
        for k, v in manifest['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        b.mount(0, str(disk))
        b.boot(str(cart))
        wait_at(b, before_install, (p['labels']['done'],), 90)
        result['native_init_reached'] = True
        wait_at(b, p['labels']['sdx_probe_installed'], (p['labels']['done'],), 30)
        result['install_result'] = int(b.regs()['A'].lstrip('$'), 16)
        require(result['install_result'] == 0, 'Firmware admission failed')
        require(b.peek16(0x281000) == identify(rom.read_bytes())['id'], 'Wrong ROM profile')
        marker = p['labels']['native_nmi']
        wait_at(b, marker, (p['labels']['done'],), 30)
        start = b.eval_expr('@frame')
        wait_at(b, marker, (p['labels']['done'],), 30,
                condition=f'@frame>={start+120}')
        result['live_tasks'] = b.peek(p['build']['task_storage']['LIVE'])[0]
        result['observed_vbi_intervals'] = b.eval_expr('@frame')-start
        b.screenshot(str(out/'screen.png'))
    result['status'] = 'pass'
    return result


def resident_case(rom, out, source):
    """Replay an explicitly selected emitted stack fixture, recording its inputs."""
    shutil.copytree(source, out, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('cart', '*.png', '*.altstate2'))
    p = read_build(out)
    result = dict(xex_sha256=sha256(p['xex']),
                  fixture_sha256=sha256(out/'resident-stack.act'),
                  compiler_revision=p['build']['revision'],
                  exec_build=p['build']['exec_build'])
    require(p['build']['optimize'], 'Use the optimized emitted fixture')
    with emulator(BRIDGE, rom, out, pin=PIN) as b:
        b.config('exeloadmode', 'diskboot')

        result['runtime'], _ = execute(b, p, timeout=30, frame_limit=1500)
        from test_cooperative import data
        result['checks'] = data(b, p['image'], 'checks', True)
    result['status'] = 'pass'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, action='append', required=True)
    parser.add_argument('--bundle', type=Path, help='Optional matching built demo with cartridge')
    parser.add_argument('--resident-build', type=Path, help='Optional built optimized ROM/stack fixture')
    parser.add_argument('--output', type=Path, default=ROOT/'build/xlos-sdx-audit-replay')
    args = parser.parse_args()
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Unpinned emulator')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', qualification=False,
                  scope='Native ROM boundaries, standalone P2 routing, optional diagnostic startup; no SDX application qualification',
                  pin=str(PIN_PATH.relative_to(ROOT)), pin_sha256=sha256(PIN_PATH),
                  emulator_sha256=PIN['emulator']['sha256'], roms=[],
                  reserved_bank_zero_delta=dict(fixed=0, root_kernel=0,
                                                per_public_task=[0]*12, idle=0),
                  inputs={str(p.relative_to(ROOT)): sha256(p) for p in
                          (Path(__file__), SOURCE, ROOT/'probes/os-boundary/probe.cfg',
                           ROOT/'probes/sdx-runtime/probe.s', ROOT/'probes/sdx-runtime/probe.cfg',
                           ROOT/'tools/test_sdx_runtime.py', ROOT/'platform/altirraos/sdx-rom-shadow.s',
                           ROOT/'platform/altirraos/sdx-runtime-probe.s', ROOT/'platform/altirraos/hosted.s',
                           ROOT/'platform/altirraos/sdx-firmware.json', ROOT/'tools/sdx_firmware_stack.py',
                           ROOT/'platform/altirraos/generated/sdx-firmware.inc')})
    try:
        for rom in args.rom:
            rom = rom.resolve()
            digest = sha256(rom)
            require(digest in ROMS, 'Unknown XLOS image: pin and audit its entry paths first')
            pin = copy.deepcopy(PIN)
            pin['rom'] = dict(name='XLOS '+ROMS[digest], bytes=16384, sha256=digest)
            record = dict(version=ROMS[digest], sha256=digest, native=[], component=[])
            report['roms'].append(record)
            folder = out/ROMS[digest].replace(' ', '-')
            record['stack_bound'] = support_bound(rom)
            for case, flags in [(0, 0xcb|width|mask) for width in (0, 16, 32, 48)
                                for mask in (0, 4)]+[(1, 0)]:
                record['native'].append(native_case(rom, folder/f'native-{case}-{flags:02x}', case, flags))
            record['component'] = component_cases(rom, folder/'component', pin)
            if args.bundle:
                record['hosted'] = hosted_case(rom, folder/'hosted', args.bundle.resolve())
            if args.resident_build:
                record['resident'] = resident_case(rom, folder/'resident',
                                                   args.resident_build.resolve())
            print('Audited XLOS', ROMS[digest], flush=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
