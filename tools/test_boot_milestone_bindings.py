#!/usr/bin/env python3
"""Small raw/optimized Action! boot diagnostic argument/result regression."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from native_program import ROOT, build, compiler, execute, read_build, require, verify_machine
from os_boundary import emulator
from test_boot_diagnostics import os_text, reach


def run(output, mode, replay=False):
    p = read_build(output) if replay else build(
        compiler(ROOT/'build/actionc'), ROOT/'tests/programs/boot_milestones.act',
        output, optimize=mode == 'opt', tasks=True)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom = ROOT/'build/firmware/altirraos-816.rom'
    cases = []
    for name in ('quiet', 'worker-bottom'):
        with emulator(ROOT/'build/shell-paced-bridge', rom, output/name, pin) as b:
            machine = verify_machine(b, rom, pin)
            saved = {}

            def prepare(bridge):
                # This small fixture has no automatic console boot. Supply the
                # resident-startup snapshot after native initialization clears state.
                reach(bridge, p['labels']['task_start'], timeout=30)
                bridge.bp_clear_all()
                bridge.memload(adapter.BOOT_SCREEN, bridge.memdump(0x58, 2))
                bridge.memload(adapter.BOOT_LIST, bridge.memdump(0x230, 2))
                bridge.poke(adapter.BOOT_DMA, bridge.peek(0x22f)[0])
                bridge.poke(adapter.BOOT_PHASE, 1)
                if name == 'worker-bottom':
                    screen = bridge.peek16(0x58)
                    pattern = b''.join(bytes([row+1])*40 for row in range(24))
                    bridge.memload(screen, pattern)
                    bridge.poke(0x54, 23)
                    bridge.memload(0x55, bytes([2, 0]))
                    bridge.memload(0x5e, (screen+922).to_bytes(2, 'little'))
                    bridge.poke(0x5d, 24)
                    bridge.poke(0x2f0, 1)
                    saved.update(screen=screen, first_row=pattern[40:80],
                                 iocb=bridge.memdump(0x340, 16))

            runtime, _ = execute(b, p, before_run=prepare, expected_status=0xc219,
                                 boot_verbose=name == 'worker-bottom')
            text = os_text(b)
            require('System halted: $C219' in text, 'Halt CARD argument was lost: '+text)
            if name == 'quiet':
                require('CONSOLE WORKER=' not in text, 'Quiet mode forced a success event')
            else:
                require(text.splitlines()[22].startswith('CONSOLE WORKER=OK'),
                        'Worker milestone was not scrolled into row 22: '+text)
                require(b.memdump(saved['screen'], 40) == saved['first_row'],
                        'Direct boot append scrolled the wrong screen rows')
                require(b.memdump(0x340, 16) == saved['iocb'], 'Direct append changed IOCB0')
            require(b.peek16(adapter.BOOT_CAUSE) == 0xc219, 'First cause differs from Halt argument')
            require(b.peek(adapter.BOOT_PHASE)[0] == 3, 'Terminal reporting did not complete')
            cases.append(dict(name=name, runtime=runtime, screen=text))
    return dict(status='pass', tier='development', mode=mode, qualification=False,
                machine=machine, build=p['build'], cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = run(args.output.resolve(), args.mode, args.replay)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Boot milestone bindings passed', args.mode, flush=True)
