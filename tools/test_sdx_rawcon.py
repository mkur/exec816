#!/usr/bin/env python3
"""Focused emitted binding/cell checks through the production guest bridge."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, verify_machine, require
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def run(out, mode, group, phase=0):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'tests/programs/sdx_rawcon.act'
    if group == 'binding':
        source = ROOT / 'tests/programs/sdx_service_shape.act'
    elif mode == 'raw' or group == 'transitions':
        small = out / 'rawcon.act'
        small.write_text(source.read_text().replace('FOR value=0 TO 255 DO',
                                                   'FOR value=0 TO 7 DO'))
        source = small
    program = build(compiler(ROOT / 'build/actionc', release=True), source, out,
                    optimize=mode == 'opt', tasks=True, task_capacity=12,
                    console=False, console_test=True, sdx=True, sio_enabled=False,
                    sdx_stack_probe=phase)
    with emulator(ROOT / 'build/shell-paced-bridge',
                  ROOT / 'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, program, timeout=180, frame_limit=9000)
        except Exception:
            print('Checks:', data(b, program['image'], 'checks'), flush=True)
            raise
        ownership(b, program, out)
        checks = int.from_bytes(bytes(data(b, program['image'], 'checks')), 'little')
        state = json.loads((ROOT / 'abi/sdx.json').read_text())['runtime']['state']
        rom_nmis = int.from_bytes(b.memdump(state['rom_nmis'], 2), 'little')
        deferred = int.from_bytes(b.memdump(0x28780e, 2), 'little')
        if phase in (10,11,12):
            require(rom_nmis > 0, 'No real NMI interrupted the fast cell transition')
        elif phase in (9,13):
            require(deferred > 0, 'No real NMI interrupted the complete-frame handoff')
        elif phase == 8:
            require(runtime['native_nmi_count'] > 0, 'No real NMI interrupted binding publication')
    return dict(status='pass', tier='development', qualification=False,
                case=mode, group=group, phase=phase, rom_nmis=rom_nmis, deferred_nmis=deferred,
                checks=checks, runtime=runtime,
                machine=machine, build=program['build'],
                bank_zero_delta=dict(fixed=0, root_kernel=0,
                                     per_public_task=[0] * 12, idle=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('binding', 'cells', 'transitions'), required=True)
    parser.add_argument('--case', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', type=int, choices=range(8,14), default=0)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        if args.group == 'transitions' and not args.phase:
            result = dict(status='pass', tier='development', qualification=False,
                          cases=[run(out / str(phase), args.case, args.group, phase)
                                 for phase in range(8,14)])
        else:
            result = run(out, args.case, args.group, args.phase)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('RAWCON', args.group, args.case, result.get('checks', 'transition'),
          'checks passed', flush=True)
