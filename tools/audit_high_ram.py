#!/usr/bin/env python3
"""Development audit of bank-zero $9000-$BC1F on a pinned, cartridge-free demo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

import adapter_state as adapter
from native_program import ROOT, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_boot_diagnostics import reach
from test_demo import run as demo_run
from test_of816 import check_loading_complete, check_loading_paused, check_boot_guards

BASE, END = 0x9000, 0xbc20
BRIDGE = ROOT/'build/mouse-bridge'
ROM = ROOT/'build/firmware/altirraos-816.rom'


def pattern():
    return b''.join((offset ^ 0x5aa5).to_bytes(2, 'little')
                    for offset in range(0, END-BASE, 2))


def memory_state(bridge):
    return dict(memtop=bridge.peek16(0x2e5), memlo=bridge.peek16(0x2e7),
                appmhi=bridge.peek16(0x0e), savmsc=bridge.peek16(0x58),
                display_list=bridge.peek16(0x230), ramtop=bridge.peek(0x6a)[0],
                portb=bridge.peek(0xd301)[0])


def cpu_probe(out, pin):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'probes/os-boundary/high-ram.s'
    subprocess.run(['ca65', '-l', str(out/'probe.lst'), '-o', str(out/'probe.o'),
                    str(source)], check=True, timeout=30)
    subprocess.run(['ld65', '-C', str(ROOT/'probes/os-boundary/probe.cfg'),
                    '-o', str(out/'probe.bin'), '-Ln', str(out/'probe.lbl'),
                    str(out/'probe.o')], check=True, timeout=30)
    labels = {name.lstrip('.'):int(at, 16) for _, at, name in
              (line.split() for line in (out/'probe.lbl').read_text().splitlines())}
    payload = (out/'probe.bin').read_bytes()
    xex = out/'probe.xex'
    xex.write_bytes(struct.pack('<HHH', 0xffff, 0x3000, 0x3000+len(payload)-1)
                    + payload + struct.pack('<HHH', 0x2e0, 0x2e1, labels['start']))
    with emulator(BRIDGE, ROM, out, pin=pin) as bridge:
        machine = verify_machine(bridge, ROM, pin)
        bridge.boot(str(xex))
        reach(bridge, labels['start'])
        before = memory_state(bridge)
        display_list = bridge.memdump(0xbc20, 32)
        bridge.bp_clear_all()
        reach(bridge, labels['done'], timeout=30)
        state = bridge.memdump(0x2000, 8)
        require(state[:2] == b'\xff\xff', 'CPU high-RAM probe failed: '+state.hex())
        require(state[2:4] == b'\x01\x00', 'Native high D/S probe did not complete')
        require(state[4:6] == b'\x01\x00' and (state[7]-state[6]) & 255 == 120,
                'ROM CIO/VBI did not complete')
        require(bridge.memdump(BASE, END-BASE) == pattern(), 'ROM damaged high RAM')
        require(bridge.memdump(0xbc20, 32) == display_list, 'Probe damaged OS display list')
        bridge.screenshot(str(out/'rom.png'))
        return dict(status='pass', machine=machine, before=before,
                    after=memory_state(bridge), result_bytes=state.hex(),
                    xex_sha256=sha256(xex), canary_sha256=hashlib.sha256(pattern()).hexdigest(),
                    cpu_patterns=['offset XOR $A55A', 'offset XOR $5AA5'],
                    native_dp=0xb000, native_stack_top=0xbbef,
                    private_domain_interrupts='masked', rom_vbi_ticks=120,
                    rom_cio='COP $00 / CIOV / IOCB0 PUT CHARACTERS')


class HostedAudit:
    interrupt_marker = 'native_nmi'

    def __init__(self, bundle):
        self.bundle = bundle
        self.checkpoints = []
        self.commands = []
        self.completed = False

    def check(self, bridge, name):
        actual = bridge.memdump(BASE, END-BASE)
        expected = pattern()
        different = [BASE+i for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
        require(not different, name+' damaged high RAM: '+str([hex(i) for i in different[:16]]))
        state = memory_state(bridge)
        require(state['portb'] & 2, name+' enabled BASIC ROM')
        require(state['memtop'] == END-1 and state['savmsc'] == 0xbc40,
                name+' changed the OS screen allocation')
        self.checkpoints.append(dict(name=name, frame=bridge.eval_expr('@frame'),
                                     intact_bytes=len(actual), memory=state))
        print('High RAM intact:', name, flush=True)

    def bootstrap(self, bridge, program):
        boot = json.loads((self.bundle/'of816/of816.json').read_text())
        bridge.boot(str(self.bundle/'of816/Exec-of816.xex'))
        reach(bridge, program['labels']['loader_of_begin'])
        # Debugger initialization for the unchanged packaged image. The separate
        # CPU probe establishes real CPU read/write and native D/S addressing.
        bridge.memload(BASE, pattern())
        self.check(bridge, 'loader-before-OF816')
        bridge.bp_clear_all()
        reach(bridge, boot['labels']['of_start'])
        check_loading_paused(bridge, boot, program)
        self.check(bridge, 'OF816-start')
        bridge.bp_clear_all()
        bridge._cmd_ok('KEY ALL up')
        reach(bridge, boot['labels']['of_autoboot'])
        bridge.bp_clear_all()
        start = bridge.eval_expr('@frame')
        reach(bridge, boot['labels']['of_handoff'])
        self.autoboot_frames = bridge.eval_expr('@frame')-start
        require(249 <= self.autoboot_frames <= 251, 'Changed five-second autoboot')
        check_boot_guards(bridge, boot['layout'])
        settings = check_loading_paused(bridge, boot, program)
        self.check(bridge, 'OF816-handoff')
        bridge.bp_clear_all()
        reach(bridge, program['labels']['loader_start'])
        check_loading_complete(bridge, boot, program, settings)
        self.check(bridge, 'payload-loaded')
        bridge.bp_clear_all()
        reach(bridge, program['labels']['start'])
        self.check(bridge, 'native-entry')
        bridge.bp_clear_all()

        original = bridge.memdump

        def capture_done(address, size):
            data = original(address, size)
            if (address == adapter.STATE and size == 64 and not self.completed
                    and bridge.eval_expr('@xpc') == program['labels']['done']):
                self.check(bridge, 'after-EXIT')
                self.completed = True
            return data

        bridge.memdump = capture_done

    def exercise(self, s):
        from desktop_menu_check import Menus
        from desktop_mouse import schedule

        def move(x, y):
            address = lambda name:next(d['address'] for d in s.p['image']['data']
                                      if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            old = [s.number(address(name), 2) for name in ('cursorX', 'cursorY')]
            x, y = schedule(s.b, s.p, old, (x, y))
            s.saved['pointer'] = (x, y)
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (address('cursorX'), x, address('cursorY'), y))
            s.frames(3)

        def click(x, y):
            move(x, y)
            s.b._cmd_ok('MOUSE AT 2000 0 0 1')
            s.frames(12)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0')
            s.frames(30)

        Menus(s, click, move).select('Shell')
        # Verbose boot intentionally updates E:. Its completed screen, before
        # commands and shutdown, is the restoration baseline for this audit.
        s.saved['screenBytes'] = s.b.memdump(s.saved['screen'], 960)
        self.check(s.b, 'desktop-and-shell-ready')
        for text, expected in (
                ('CAT SYS:STORY.TXT', None),
                ('CD WORK:', None),
                ('ECHO abc >AUDIT.TXT', None),
                ('MD5 AUDIT.TXT', b'MD5 (AUDIT.TXT)'),
                ('ARC', b'filename is given.'),
                ('FBCI HELLO.BAS AUDIT.COM', b'Compiled AUDIT.COM'),
                ('AUDIT.COM', b'HELLO BASIC'),
                ('FBC CALC.BAS AUDITFP.COM', b'Compiled AUDITFP.COM'),
                ('AUDITFP.COM', b'3.75'),
                ('C:HELLO', b'Hello from disk!')):
            s.command(text, expected)
            self.commands.append(text)
            self.check(s.b, text)
        s.frames(120)
        self.check(s.b, 'idle-VBI')
        s.saved['integration'] = dict(high_ram_audit=True, commands=self.commands)
        s.save_screen(self.bundle/'boot-smoke.png')
        for char in 'EXIT':
            s.press(char)
        s.b._cmd_ok('KEY RETURN down')
        s.b.bp_clear_all()


def run(bundle, output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    for pool in manifest['kernel']['memory']['task_pools']:
        spans=((pool['dp'],pool['dp']+256),
               (pool['stack_base']-16,pool['stack_base']+pool['stack_bytes']+16))
        require(all(high<=BASE or low>=END for low,high in spans),
                'This canary audit requires a pre-layout demo with unused high RAM')
    pin = manifest['pin']
    report = dict(status='running', tier='development', scope='no cartridge, fixed OS text screen',
                  pin=pin, bundle_manifest_sha256=sha256(bundle/'demo-manifest.json'),
                  actual_rom_sha256=sha256(ROM), actual_emulator_sha256=sha256(BRIDGE/'AltirraBridgeServer'),
                  inputs={name:sha256(ROOT/name) for name in (
                      'tools/audit_high_ram.py', 'probes/os-boundary/high-ram.s',
                      'tools/test_demo.py', 'platform/altirraos/memory-4m.json',
                      'platform/altirraos/hosted.s', 'platform/altirraos/boot-worker.s',
                      'platform/altirraos/sdx-rom-shadow.s', 'platform/altirraos/vbxe.c',
                      'platform/altirraos/cartridge.s')},
                  candidate=dict(start=BASE, end_exclusive=END, bytes=END-BASE,
                                 whole_page_bytes=0x2c00, whole_page_end_exclusive=0xbc00),
                  bank_zero_reservation_delta=dict(fixed=0, root=0, kernel=0, per_task=0, idle=0))
    try:
        require(sha256(ROM) == pin['rom']['sha256'], 'Unpinned audit ROM')
        require(sha256(BRIDGE/'AltirraBridgeServer') == pin['mouse_input']['tooling']['sha256'],
                'Unpinned audit emulator')
        report['cpu'] = cpu_probe(output/'cpu', pin)
        # Preserve the previous delivery and all its evidence/output files.
        copied = output/'bundle'
        require(not copied.exists(), 'Use a fresh output directory')
        shutil.copytree(bundle, copied)
        hosted = HostedAudit(copied)
        report['hosted'] = demo_run(copied, boot_smoke=True, bootstrap=hosted.bootstrap,
                                    integration=hosted, boot_verbose=True)
        require(hosted.completed, 'Missing shutdown canary check')
        report.update(status='pass', checkpoints=hosted.checkpoints,
                      autoboot_frames=hosted.autoboot_frames,
                      listing_sha256=sha256(ROOT/'build/firmware/altirraos-816.lst'))
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle.resolve(), args.output.resolve())
