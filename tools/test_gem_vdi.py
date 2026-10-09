#!/usr/bin/env python3
"""Run a hosted GEM development slice: G0 identity, G1 C or G2 service."""
import argparse
import copy
import json
from stack_budget import current_task_memory
from pathlib import Path

from gem_vdi_inputs import local_inputs, source_inputs
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())


def case_pin(case):
    pin = copy.deepcopy(PIN)
    if case == 'absent':
        pin['machine']['addons'] = 'off'
        pin['devices'] = []
    elif case == 'unsupported':
        pin['devices'][0]['settings']['version'] = 124
        pin['devices'][0]['readback'][0]['bytes'][1] = 0x24
    elif case != 'present':
        raise ValueError('Unknown VBXE case: '+case)
    return pin


def run(output, mode):
    output.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', slice='G0', mode=mode, cases=[],
                  scope='Read-only identity detection; no mapping, drawing or GEM C execution')
    try:
        report['local_inputs'] = local_inputs()
        report['source_inputs'] = source_inputs(ROOT/'build/gem-vdi/upstream')
        bridge_dir = ROOT/'build/shell-paced-bridge'
        rom = ROOT/'build/firmware/altirraos-816.rom'
        require(sha256(bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Wrong emulator')
        require(sha256(rom) == PIN['rom']['sha256'], 'Wrong ROM')
        report['emulator_sources'] = {}
        for name, digest in PIN['source_sha256'].items():
            require(sha256(ROOT/'build/altirra-irq-fix'/name) == digest, 'Changed emulator source: '+name)
            report['emulator_sources'][name] = digest
        program = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/gem_vdi_probe.act',
                        output/'program', optimize=mode == 'opt', tasks=True,
                        task_capacity=8, console=False)
        report['build'] = program['build']
        before = current_task_memory()
        for key in ('bank_zero_budget', 'task_pools', 'runtime_reservations', 'phase_reservations'):
            require(program['build']['memory'][key] == before[key], 'G0 changed '+key)
        report['baseline_budget'] = before['bank_zero_budget']
        report['bank_zero_delta'] = dict(fixed=0, per_task=[0]*8, private_idle=0)
        for case in ('present', 'absent', 'unsupported'):
            pin = case_pin(case)
            folder = output/case
            selected = dict(program, output=folder)
            with emulator(bridge_dir, rom, folder, pin=pin) as bridge:
                machine = verify_machine(bridge, rom, pin)
                # The normal profile must still reject any graphics add-on.
                if case != 'absent':
                    try:
                        verify_machine(bridge, rom, case_pin('absent'))
                    except RuntimeError:
                        pass
                    else:
                        raise RuntimeError('Default machine verification accepted VBXE')
                saved = {}
                sentinel = bytes((i*37+11) & 255 for i in range(4096))

                def before_run(b):
                    b.memload(0x8000, sentinel)
                    saved['display_list'] = b.memdump(0x230, 2)
                    saved['dma_shadow'] = b.memdump(0x22f, 1)
                    if case != 'absent':
                        saved['memac'] = b.memdump(0xd65e, 2)
                        require(saved['memac'] == bytes(2), 'VBXE was not inactive at boot')

                runtime, _ = execute(bridge, selected, before_run=before_run,
                                     frame_limit=180, timeout=15)
                result = data(bridge, program['image'], 'result', True)[0]
                version = data(bridge, program['image'], 'version', True)[0]
                require(result == (0 if case == 'present' else 1), 'Wrong target detection result')
                require((version == 0x1026) == (case == 'present'), 'Wrong target identity')
                require(bridge.memdump(0x8000, len(sentinel)) == sentinel, 'Aperture RAM changed')
                require(bridge.memdump(0x230, 2) == saved['display_list'] and
                        bridge.memdump(0x22f, 1) == saved['dma_shadow'], 'OS presentation changed')
                if case != 'absent':
                    require(bridge.memdump(0xd65e, 2) == saved['memac'], 'MEMAC changed')
                    require(bridge.memdump(0xd653, 2) == bytes(2), 'Blitter or VBXE IRQ active')
                require(runtime['native_nmi_count'] > 0, 'No native VBI observed')
                report['cases'].append(dict(case=case, status='pass', pin=pin,
                    machine=machine, result=result, core_version=version, runtime=runtime,
                    aperture_intact=True, display_unchanged=True))
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'G0 {mode}: three hosted detection cases passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--slice', choices=('g0', 'g1', 'g2'), default='g0')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.slice == 'g1':
        from test_gem_vdi_context import run
    elif args.slice == 'g2':
        from test_gem_service import run
    run(args.output or ROOT/'build/gem-vdi'/(args.slice+'-'+args.mode), args.mode)
