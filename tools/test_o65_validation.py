#!/usr/bin/env python3
"""Execute the bounded o65 reader on native raw/optimized code."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, command, require, sha256, verify_machine
from library_paths import read_source
from o65_fixtures import mutations, mutation_bytes
from o65_oracle import build_oracle, reference
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())


def run(out, mode, abi_smoke=False):
    out.mkdir(parents=True, exist_ok=True)
    toolchain = compiler(ROOT/'build/actionc')
    options = out/'o65-options.json'
    options.write_text(json.dumps(dict(profile='actionc.o65.compact.v3', nmi_extra_stack=0, imports=[])))
    artifact = out/'sample.o65'
    command([toolchain['binary'], '--entry', 'Main', '--format', 'o65-experimental', '--o65-options', options,
             *(['--no-opt'] if mode == 'raw' else []), '-o', artifact, ROOT/'tests/programs/o65_sample.act'])
    raw = artifact.read_bytes()
    oracle = reference(build_oracle(toolchain), artifact, prefixes=True, mutations=mutations(raw))
    require(oracle == dict(valid=True, accepted_prefixes=[], accepted_mutations=[]), 'Reference oracle disagrees with corruption fixtures: '+str(oracle))
    (out/'o65-fixture.inc').write_text(f'CONST FIXTURE_BYTES={len(raw)}\nCONST MUTATION_COUNT={len(mutations(raw))}\n')
    source = read_source(ROOT/'lib/dos/o65memory.act').replace('USE EXEC\n', 'USE EXEC\nUSE O65CONTROL\n')
    source = source.replace('RETURN(EXEC.AllocMem', '  O65CONTROL.allocations==+1\n'
                            '  IF O65CONTROL.failAt<>0 AND O65CONTROL.allocations=O65CONTROL.failAt THEN RETURN(BYTE POINTER(0)) FI\nRETURN(EXEC.AllocMem')
    (out/'o65memory.act').write_text(source)
    fixture = out/'probe.act'
    text = read_source(ROOT/'tests/programs/o65_validation.act', {'o65-fixture.inc':out/'o65-fixture.inc'})
    if abi_smoke:
        text = text.replace('WHILE prefix<FIXTURE_BYTES DO\n    Reject(prefix)\n    prefix==+1\n  OD',
                            '; Structural truncation matrix is covered by the full fixture.')
        text = text.replace('FOR mutation=0 TO MUTATION_COUNT-1 DO', 'FOR mutation=0 TO 1 DO')
    fixture.write_text(text)
    (out/'o65control.act').write_text((ROOT/'tests/programs/o65control.act').read_text())
    program = build(toolchain, fixture, out,
                    optimize=mode == 'opt', tasks=True, task_capacity=8, console=False,
                    image_data=[(0xd0000, raw+mutation_bytes(raw))])
    with emulator(ROOT/'build/shell-console-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(bridge, program, timeout=240, frame_limit=12000)
        except Exception:
            print({name: data(bridge, program['image'], name) for name in ('checks','prefix','mutation')}, flush=True)
            raise
        ownership(bridge, program, out)
        checks = int.from_bytes(bytes(data(bridge, program['image'], 'checks')), 'little')
        return dict(status='pass', mode=mode, build=program['build'], runtime=runtime, machine=machine,
                    checks=checks, truncated_prefixes=0 if abi_smoke else len(raw), mutations=2 if abi_smoke else len(mutations(raw)),
                    scope="native ABI smoke" if abi_smoke else "full validation fixture",
                    allocation_failures=2, artifact_sha256=sha256(artifact),
                    reference=oracle,
                    override_sha256=sha256(out/'o65memory.act'), bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw','opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--abi-smoke', action='store_true', help='Check current ABI, old descriptor/magic and allocation cleanup only')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try: result = run(out, args.case, args.abi_smoke)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally: (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('o65 validation passed', args.case, result['checks'], flush=True)
