#!/usr/bin/env python3
"""Bounded standard boot milestones and terminal startup fault checks."""
import argparse
import copy
import json
import time
from pathlib import Path

import adapter_state as adapter
from build_cartridge import build as cartridge
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_boot_diagnostics import os_text, reach
from generate_sio_adapter import ABI as SIO

MILESTONES = ('VBI/IRQ       =OK', 'CONSOLE WORKER=OK',
              'CONSOLE       =OK', 'SHELL         =LAUNCHED')
CASES = ('verbose', 'quiet', 'brightness', 'admission', 'fault-before-console',
         'fault-after-claim', 'reset-required', 'normal-return', 'post-startup', 'xlos')


def inject_fault(bridge, at, target, code, corrupt=False):
    """Replace the paused entry with a terminal transfer, never a new call."""
    # Stop IRQ/NMI before the deliberate invalid S/D test. Production finish
    # must replace these registers before pushing any diagnostic return frame.
    body = bytes.fromhex('78 c2 30 a9 00 00 8f 0e d4 00')
    if corrupt:
        body += bytes.fromhex('a9 ff 7f 1b a9 00 00 5b')
    body += b'\xa9'+code.to_bytes(2, 'little')
    body += b'\x5c'+target.to_bytes(3, 'little')
    bridge.memload(at, body)


def rendezvous(bridge, program, condition):
    bridge.bp_clear_all()
    at = program['labels']['native_cop']
    reach_condition = f'(@xpc=${at:x})&({condition})'
    from os_boundary import run_to
    bridge.bp_set(at, condition=reach_condition)
    run_to(bridge, at, timeout=30, frame_limit=1800, condition=reach_condition)


def guards(bridge, program):
    memory = program['build']['memory']
    locations = [0x100, adapter.KERNEL_STACK_BASE-16,
                 adapter.KERNEL_STACK_CEILING+1]
    for pool in memory['task_pools']:
        locations.extend((pool['stack_base']-16,
                          pool['stack_base']+pool.get('stack_bytes', 1536)))
    for at in locations:
        require(bridge.memdump(at, 16) == b'\xa5'*16,
                f'Startup crossed a stack guard at ${at:04x}')


def run(bundle, output, bridge_dir, xlos=None, selected=None):
    bundle, output = bundle.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    program = read_build(bundle)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    require(not manifest.get('bitmap'), 'This runner requires the standard console')
    cartridge(bundle/'of816/Exec-of816.xex', output/'cartridge')
    cart = output/'cartridge/Exec-of816-atarimax-8mbit-new.car'
    memory = program['build']['memory']
    state = memory['adapter_state']
    console = memory['console_storage']
    from generate_console import constants
    c = constants()
    claimed = console['PRESENTATION']+c['PRESENTATION_CLAIMED']
    normal_rom = ROOT/'build/firmware/altirraos-816.rom'
    records = []
    result = dict(status='running', tier='development', qualification=False,
                  source=program['build']['exec_build'],
                  xex_sha256=sha256(bundle/'of816/Exec-of816.xex'),
                  bridge_sha256=sha256(bridge_dir/'AltirraBridgeServer'), cases=records)
    try:
        for name in CASES:
            if selected and name not in selected:
                continue
            if name == 'xlos' and xlos is None:
                continue
            folder = output/name
            rom = xlos if name == 'xlos' else normal_rom
            pin = copy.deepcopy(manifest['pin'])
            record = dict(name=name, status='running', rom_sha256=sha256(rom), pin=pin)
            records.append(record)
            print(name, 'booting', flush=True)
            with emulator(bridge_dir, rom, folder, pin) as b:
                if name != 'xlos':
                    record['machine'] = verify_machine(b, rom, pin)
                for key, value in manifest['configuration'].items():
                    b.config(key, str(value).lower() if isinstance(value, bool) else value)
                work = folder/'work.atr'
                work.write_bytes((bundle/'work.atr').read_bytes())
                b.mount(0, str(bundle/'system.atr'))
                b.mount(7, str(work))
                b.boot(str(cart))
                reach(b, program['labels']['start'], timeout=30)
                old_vectors = b.memdump(0x256, 9)
                old_vbi = b.memdump(0x222, 2)
                verbose = name in ('verbose', 'brightness', 'xlos')
                b.poke(memory['boot_config']['address']+7, int(verbose))
                b.bp_clear_all()
                reach(b, program['labels']['task_start'], timeout=30)
                abort = b.memdump(program['labels']['heap_fault'], 5)
                require(abort[:3] == bytes.fromhex('a3 04 4c'),
                        'Heap Abort no longer transfers directly to native finish')
                finish = int.from_bytes(abort[3:], 'little')
                if name == 'brightness':
                    b.poke(0x4e, 0xf6)
                if name == 'admission':
                    b.poke(0x57, 1)
                if name == 'fault-before-console':
                    inject_fault(b, program['labels']['task_start'],
                                 finish, 0xff97, True)
                if name == 'normal-return':
                    inject_fault(b, program['labels']['task_start'],
                                 finish, 0)
                if name in ('fault-after-claim', 'reset-required'):
                    rendezvous(b, program,
                               f'(db(${claimed:x})=1)&(db(${state["BOOT_PHASE"]:x})=1)')
                    if name == 'reset-required':
                        # Force the existing unsafe-bus park; it must keep the
                        # original fault code without reclaiming live storage.
                        b.poke(program['build']['task_storage']['BASE']+
                               SIO['state_offset']+SIO['fields']['SD_OFFLINE'], 1)
                    inject_fault(b, program['labels']['native_cop'],
                                 finish, 0xff97, True)
                b.bp_clear_all()
                terminal = name in ('admission', 'fault-before-console',
                                    'fault-after-claim', 'reset-required', 'normal-return')
                if terminal:
                    reach(b, program['labels']['done'], timeout=30)
                    expected = 0 if name == 'normal-return' else (
                        0xff95 if name == 'admission' else 0xff97)
                    status = 0xff93 if name == 'reset-required' else expected
                    require(b.peek16(state['STATUS']) == status, 'Wrong terminal status')
                    require(b.peek16(state['BOOT_CAUSE']) == expected, 'Original cause lost')
                    if name == 'reset-required':
                        require(int(b.regs()['P'].lstrip('$'), 16) & 4,
                                'Unsafe-bus park enabled IRQs')
                        require(int(b.antic()['NMIEN'].lstrip('$'), 16) == 0 and
                                b.peek16(0x2e7) == 0x9000,
                                'Unsafe-bus park resumed OS interrupts or released RAM')
                    else:
                        require(b.memdump(0x256, 9) == old_vectors and
                                b.memdump(0x222, 2) == old_vbi,
                                'Safe shutdown did not restore OS vectors')
                    text = os_text(b)
                    if name == 'normal-return':
                        require('System halted:' not in text, 'Successful return reported failure')
                    else:
                        require(f'System halted: ${expected:04X}' in text,
                                'Silent startup fault: '+text)
                    require(all(m not in text for m in MILESTONES), 'Quiet failure printed milestones')
                    guards(b, program)
                    before = b.memdump(b.peek16(state['BOOT_SCREEN'])+920, 40)
                    b.bp_clear_all()
                    b.resume()
                    time.sleep(.1)
                    b.pause()
                    require(b.memdump(b.peek16(state['BOOT_SCREEN'])+920, 40) == before,
                            'Shutdown or rendering erased the fatal line')
                else:
                    b.resume()
                    deadline = time.monotonic()+30
                    text = ''
                    while time.monotonic() < deadline:
                        b.pause()
                        text = os_text(b)
                        if text.rstrip().endswith('>'):
                            break
                        require(b.peek16(state['STATUS']) == 0xffff, 'Stopped before prompt: '+text)
                        b.resume()
                        time.sleep(.05)
                    require(text.rstrip().endswith('>'), 'No shell prompt: '+text)
                    require(b.peek(state['BOOT_PHASE'])[0] == 0, 'Startup phase remained active')
                    if verbose:
                        positions = [text.find(m) for m in MILESTONES]
                        require(all(p >= 0 for p in positions) and positions == sorted(positions),
                                'Missing or unordered milestones: '+text)
                        require(all(text.count(m) == 1 for m in MILESTONES), 'Duplicate milestone')
                        require(all(m in text.splitlines() for m in MILESTONES),
                                'Milestone indentation changed across console handoff: '+text)
                    else:
                        require(all(m not in text for m in MILESTONES), 'Quiet boot printed milestones')
                    guards(b, program)
                    if name == 'post-startup':
                        b.bp_clear_all()
                        reach(b, program['labels']['native_nmi'], timeout=30)
                        inject_fault(b, program['labels']['native_nmi'],
                                     finish, 0xff97)
                        b.bp_clear_all()
                        reach(b, program['labels']['done'], timeout=30)
                        require('System halted:' not in os_text(b),
                                'Post-startup fault was mislabeled as startup failure')
                record.update(status='pass', screen=os_text(b),
                              status_word=b.peek16(state['STATUS']),
                              first_cause=b.peek16(state['BOOT_CAUSE']))
                b.screenshot(str(folder/'screen.png'))
            print(name, 'passed', flush=True)
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, default=ROOT/'build/shell-paced-bridge')
    parser.add_argument('--xlos-rom', type=Path)
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    run(args.bundle, args.output, args.bridge, args.xlos_rom, args.case)
