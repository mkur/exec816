#!/usr/bin/env python3
"""Focused emitted input ABI and capture development checks."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from calypsi_build import emit
from generate_input import expected_layout, files
from library_paths import read_source
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_calypsi import pattern
from test_cooperative import data
from test_heap_api import clean_ownership
from test_large_stacks import observe

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())


def build_abi(output, optimize):
    for path, content in files().items():
        require(path.read_text() == content, 'Stale input definition: '+str(path))
    foreign = emit(output,
        [ROOT/'c/calypsi/exec.c', ROOT/'c/calypsi/input.c', ROOT/'tests/programs/input_abi.c'],
        [ROOT/'c/calypsi/gateway.s', ROOT/'c/calypsi/input.s', ROOT/'c/calypsi/image-info.s'],
        [], optimize=optimize,
        probes=[(ROOT/'c/calypsi/input-layout.c', expected_layout())])
    paths = [ROOT/'abi/input.json', ROOT/'tools/generate_input.py', ROOT/'tools/test_input.py',
             ROOT/'tools/calypsi_build.py', ROOT/'tools/calypsi_image.py',
             *ROOT.glob('c/calypsi/*'), *ROOT.glob('c/include/**/*.h'),
             *ROOT.glob('lib/input/*'), *ROOT.glob('tests/programs/input_abi*')]
    foreign['provenance'].update(slice='I1', hardware_execution=False,
        source_inputs={p.relative_to(ROOT).as_posix(): sha256(p) for p in paths if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign, indent=2)+'\n')
    include = output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
                              for name in ('main', 'stage', 'config', 'event', 'lease', 'ExecInputEntries')))
    source = output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/input_abi_launcher.act', {'c-image.inc': include}))
    program = build(compiler(ROOT/'build/actionc'), source, output/'program',
                    optimize=optimize, tasks=True, task_capacity=8, console=False,
                    foreign_image=foreign)
    return program, foreign


def run(output, mode, case='abi', replay=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', slice='I1', mode=mode, cases=[],
                  qualification=False, scope='Records and C/native bridge; no active input producer')
    try:
        if replay:
            program = read_build(output/'program')
            foreign = json.loads((output/'c-image.json').read_text())
            for path, digest in foreign['provenance']['source_inputs'].items():
                require(sha256(ROOT/path) == digest, 'Changed input probe source: '+path)
        else:
            program, foreign = build_abi(output, mode == 'opt')
        require(program['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
        memory = program['build']['memory']
        baseline = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget', 'task_pools', 'runtime_reservations', 'phase_reservations'):
            require(memory[key] == baseline[key], 'Input changed '+key)
        report.update(build=program['build'], pin=PIN, harness_sha256=sha256(Path(__file__)),
            xex_sha256=sha256(program['xex']),
            bank_zero_delta=dict(fixed=0, per_task=[0]*8, private_idle=0),
            c_map=dict(segments=[dict(address=s['address'], bytes=len(s['bytes']), executable=s['executable'])
                                for s in foreign['segments']], zero_fill=foreign['zero_fill'],
                       reserved_upper_bytes=131072), layout=foreign['provenance']['checked_layout'])
        symbols = foreign['symbols']
        result = dict(name=case, status='running')
        report['cases'].append(result)
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
            saved = {}

            def before(bridge):
                marker = program['labels']['task_start']
                bridge.bp_set(marker)
                run_to(bridge, marker)
                bridge.bp_clear_all()
                dp = memory['task_pools'][0]['dp']
                bridge.memload(dp+8, pattern(0)[8:16])
                bridge.memload(adapter.KERNEL_DP, pattern(4))
                saved['display'] = bridge.memdump(0x22f, 3)
                saved['aperture'] = bytes((i*37+11)&255 for i in range(4096))
                bridge.memload(0x8000, saved['aperture'])
                result['c_context'] = observe(bridge, program, [symbols['progress']], slots=(0,),
                    code_bank=12, pc_range=(0xc0000, 0xd0000))

            runtime, _ = execute(b, program, before_run=before, frame_limit=4000, timeout=120)
            read = lambda name, size=2: int.from_bytes(b.memdump(symbols[name], size), 'little')
            result.update(runtime=runtime, checks=read('checks'), failures=read('failures'),
                          first_failure=read('first_failure'), stack_usage=stack_usage(b, memory))
            require(read('failures') == 0, 'Input C check '+str(read('first_failure')))
            require(data(b, program['image'], 'result', True) == [0], 'Native bridge failed')
            a, bv = 0x12345678, 0x87654321
            for i in range(30000):
                a = ((a << 1) ^ (a >> 31) ^ bv)&0xffffffff
                bv = (bv+(a ^ i))&0xffffffff
            require(read('checksum', 4) == a ^ bv, 'C context corrupted')
            dp = memory['task_pools'][0]['dp']
            require(b.memdump(dp+8, 8) == pattern(0)[8:16], 'C callee-preserved DP changed')
            require(b.memdump(adapter.KERNEL_DP, 128) == pattern(4), 'Kernel lower DP changed')
            require(b.memdump(0x22f, 3) == saved['display'], 'Display changed')
            require(b.memdump(0x8000, 4096) == saved['aperture'], 'Aperture changed')
            require(all(u['remaining_above_floor'] > 0 for u in result['stack_usage'].values()), 'Stack floor reached')
            clean_ownership(b, program, program['output'])
            result['status'] = 'pass'
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        if report['cases']:
            report['cases'][-1].update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Input', mode, case, 'pass', flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['raw', 'opt'], required=True)
    p.add_argument('--case', choices=['abi'], default='abi')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--replay', action='store_true')
    args = p.parse_args()
    run(args.output, args.mode, args.case, args.replay)
