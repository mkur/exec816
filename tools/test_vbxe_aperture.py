#!/usr/bin/env python3
"""Development coverage for the reserved, currently unmapped VBXE aperture."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from native_program import ROOT, build, compiler, execute, platform_files, require, sha256, verify_machine
from os_boundary import emulator
from test_memory_relocation import stop_at
from test_task_capacity import check_case

PIN = json.loads((ROOT/'toolchain/altirra-signals-1m.json').read_text())
PATTERN = bytes((i*37+(i >> 8)+0x53) & 255 for i in range(4096))


def seed(bridge, program):
    bridge.bp_clear_all()
    bridge.boot(str(program['xex']))
    # First INITAD has not yet consumed any payload; all following staging
    # records, adoption, Task startup and shutdown must leave this RAM intact.
    stop_at(bridge, program['labels']['loader_init'])
    bridge.memload(0x8000, PATTERN)
    stop_at(bridge, program['labels']['loader_start'])
    check(bridge)
    stop_at(bridge, program['labels']['start'])


def check(bridge):
    require(bridge.memdump(0x8000, len(PATTERN)) == PATTERN,
            'Reserved VBXE aperture changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--bridge-dir', type=Path, default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/vbxe-aperture')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir, args.rom)
    report = dict(tier='development', status='running', pin=PIN, cases=[],
                  scope='Unmapped aperture RAM; all Task slots, IRQ, VBI, guards and OS restoration',
                  inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                          (Path(__file__), ROOT/'tools/test_task_capacity.py',
                           ROOT/'tools/banked_test_memory.py', ROOT/'tools/bridge_memory.py')})
    try:
        # Four Tasks exercise the default fixed pools. Eight exercises the
        # relocated worker and idle; the last case forces an NMI stack boundary.
        for capacity, mode, checkpoint, flags in ((4,'opt',0,0x100), (8,'raw',0,0x100),
                                                  (8,'opt',0,0xc9), (8,'opt',3,0x100)):
            name = f'{capacity}-{mode}-nmi{checkpoint}-flags{flags:x}'
            print('Running '+name+'...', flush=True)
            program = build(toolchain, ROOT/'tests/programs/signals_capacity.act', output/name,
                tasks=True, optimize=mode == 'opt', task_capacity=capacity,
                probe_nmi=checkpoint, probe_flags=flags,
                image_data=[(0x5ffe0,bytes([0xa5])*4096),(0x68000,bytes(4096)),(0x6a000,bytes(96))])
            with emulator(args.bridge_dir.resolve(), args.rom.resolve(), output/name, pin=PIN) as bridge:
                machine = verify_machine(bridge, args.rom, PIN)
                seed(bridge, program)

                def startup(b):
                    stop_at(b, program['labels']['startup_complete'])
                    check(b)
                    c = program['build']['memory']['constants']
                    require(b.peek(c['RETIRED']) == b'\1', 'Manifest still live at startup completion')
                    b.memload(c['MANIFEST'], bytes([0xd3])*c['MANIFEST_CAPACITY'])

                runtime, _ = execute(bridge, program, preloaded=True, before_run=startup,
                                     frame_limit=6000, timeout=180)
                observed = check_case(bridge, program, runtime,
                                      SimpleNamespace(capacity=capacity, burst=None, flags=flags))
                check(bridge)
                c = program['build']['memory']['constants']
                require(bridge.memdump(c['MANIFEST'], c['MANIFEST_CAPACITY']) ==
                        bytes([0xd3])*c['MANIFEST_CAPACITY'], 'Retired manifest changed')
                require(runtime['idle_runs'] > 0 and runtime['vbi_dispatches'] > 0,
                        'Idle or VBI dispatch not exercised')
                report['cases'].append(dict(name=name, status='pass', build=program['build'],
                    runtime=runtime, machine=machine, observed=observed, aperture_intact=True,
                    retired_manifest_intact=True,
                    diagnostic_bank_zero_delta=128 if flags != 0x100 else 0))
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('VBXE aperture development checks passed')


if __name__ == '__main__':
    main()
