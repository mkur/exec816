#!/usr/bin/env python3
"""Focused emitted-code boot settings, including the real loader handoff."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, execute, require, verify_machine
from os_boundary import emulator, run_to
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership


def run(output, mode):
    program = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/boot_config.act',
                    output, optimize=mode=='opt', tasks=True)
    address = program['build']['memory']['boot_config']['address']
    require(program['build']['memory']['boot_config']['settings'] >= 65536,
            'Captured boot settings must live in upper RAM')
    require(not any(d['name'].startswith('M_BOOTCONFIG_') for d in program['image']['data']),
            'Boot settings introduced bank-zero globals')
    cases = [('default', {}, [512,0,0,512]), ('disabled', {4:0,5:0}, [0,0,0,0]),
             ('override', {4:128,5:0}, [128,0,0,128]),
             ('no-system', {6:2}, [512,1,0,512]),
             ('magic', {0:0}, [512,1,0,512]), ('version', {2:255}, [512,1,0,512]),
             ('size', {3:7}, [512,1,0,512]), ('reserved', {7:1}, [512,1,0,512]),
             ('drive', {6:9}, [512,1,0,512]), ('capacity', {4:17,5:0}, [512,2,0,512]),
             ('wide', {4:0,5:16}, [512,2,0,512])]
    observations = []
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        for name,patch,expected in cases:
            bridge.bp_clear_all()
            bridge.boot(str(program['xex']))
            run_to(bridge, program['labels']['loader_start'], frame_limit=1800, timeout=180)
            require(bridge.memdump(address,8)==bytes([0x45,0x42,1,8,0,2,0,0]), 'Loader defaults differ')
            for offset,value in patch.items(): bridge.poke(address+offset,value)
            bridge.bp_clear_all()
            bridge.bp_set(program['labels']['start'])
            run_to(bridge, program['labels']['start'])
            runtime,_ = execute(bridge, program, preloaded=True)
            observed = data(bridge, program['image'], 'facts', True)
            require(observed == expected, f'{name}: {observed} != {expected}')
            clean_ownership(bridge, program, output)
            observations.append(dict(case=name, facts=observed, runtime=runtime))
    return dict(status='pass', mode=mode, machine=machine, build=program['build'], cases=observations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw','opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = run(args.output.resolve(), args.mode)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Boot configuration passed', args.mode)
