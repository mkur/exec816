#!/usr/bin/env python3
"""Execute compiler/assembly limit probes without crossing physical stack bounds."""
import argparse
import adapter_state as adapter
import json
from pathlib import Path

from native_program import ROOT, build, compiler, execute, require, verify_machine
from os_boundary import emulator, run_to
from test_hosted import global_word
from native_abi import FIELDS


def run(toolchain, out, checked_only=False):
    cases = []
    config = json.loads((ROOT/'config/kernel.json').read_text())
    config['stack_checks'] = False
    config_path = out/'kernel-off.json'
    config_path.write_text(json.dumps(config)+'\n')
    with emulator(ROOT/'build/altirra-irq-bridge', ROOT/'build/firmware/altirraos-816.rom', out) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom')
        for optimize in (False, True):
            for checks in ((True,) if checked_only else (True, False)):
                dest = out/f'{"opt" if optimize else "raw"}-{"on" if checks else "off"}'
                program = build(toolchain, ROOT/'tests/programs/stack_checks.act', dest,
                                optimize=optimize, kernel_config=config_path,
                                stack_checks=True if checks else None)
                require(program['build']['stack_checks'] == checks, 'Build setting differs')
                work = next(r for r in program['image']['routines'] if '_WORK_' in r['name'])
                require(work['fixed_frame'] > 0, 'Compiler probe must reserve a checked frame')
                for target in ('compiler', 'assembly'):
                    observation = {}
                    def inject(b):
                        address = program['labels']['console_write'] if target == 'assembly' else next(
                            r['address'] for r in program['image']['routines'] if '_WORK_' in r['name'])
                        b.bp_set(address)
                        run_to(b, address)
                        b.bp_clear_all()
                        floor_at = adapter.TASK0_DP + FIELDS["stack_floor"]["offset"]
                        floor = b.peek16(floor_at)
                        stack_low = int(b.regs()['S'].lstrip('$'),16)
                        observation.update(entry_s_low=stack_low, original_floor=floor, injected_floor=adapter.TASK0_STACK_CEILING)
                        # Raise only the logical floor. Physical stack/interrupt
                        # space remains ample for the unchecked bounded program.
                        b.poke16(floor_at, adapter.TASK0_STACK_CEILING)
                        stop = program['labels']['stack_overflow' if checks else 'native_return']
                        b.bp_set(stop)
                        run_to(b, stop)
                        observation['stopped_at'] = stop
                        # Restore the injected domain before ordinary post-run
                        # domain verification; never alter stack/canary bytes.
                        b.poke(floor_at, floor&255); b.poke(floor_at+1, floor>>8)
                        b.bp_clear_all()
                    runtime, _ = execute(bridge, program, expected_status=1 if checks else 0, before_run=inject)
                    if checks:
                        require(adapter.TASK0_STACK_FLOOR <= runtime['fault_s'] < adapter.TASK0_STACK_CEILING and
                                runtime['fault_s'] & 255 == observation['entry_s_low'], f'Fault changed entry S: {target}, {runtime}, {observation}')
                    else:
                        require(global_word(bridge, program['image'], 'result') == 42, 'Unchecked call result differs')
                        require(global_word(bridge, program['image'], 'status') == 1, 'Unchecked assembly result differs')
                    cases.append(dict(mode='opt' if optimize else 'raw', stack_checks=checks, target=target,
                                      runtime=runtime, injection=observation, image_sha256=program['build']['image_sha256']))
        # The natural recursion fault must still stop before physical guards.
        for optimize in (False, True):
            program = build(toolchain, ROOT/'tests/programs/stack_fault.act', out/f'recursion-{optimize}', optimize=optimize)
            runtime, _ = execute(bridge, program, expected_status=1)
            require(adapter.TASK0_STACK_FLOOR <= runtime['fault_s'] < adapter.TASK0_STACK_FLOOR+256 and runtime['fault_required'] > 0, 'Recursion fault outside stack floor')
            cases.append(dict(mode='opt' if optimize else 'raw', stack_checks=True, target='recursion', runtime=runtime))
    return dict(status='pass', machine=machine, cases=cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--output', type=Path, default=ROOT/'build/stack-checks/probes')
    parser.add_argument('--checked-only', action='store_true', help='Run guard-enabled cases and recursion faults only')
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    result = run(compiler(args.compiler_dir), out, args.checked_only)
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Stack checks passed:', len(result['cases']), 'emitted-code cases')
