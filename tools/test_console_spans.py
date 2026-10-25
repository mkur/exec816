#!/usr/bin/env python3
"""Public cell vectors from an ordinary native Task, in emitted machine code."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT / 'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes'] = 8192
    memory = out / 'memory-profile.json'
    memory.write_text(json.dumps(profile))
    source = ROOT / 'tests/programs/console_spans.act'
    if mode == 'raw':
        text = source.read_text()
        begin = text.index('  ; All 256 values')
        end = text.index('  mode=0', begin)
        text = text[:begin] + text[end:]
        text = text.replace('  Async()\n', '')
        # A focused ABI/array/far-pointer probe; broad geometry stays optimized.
        text = text.replace('FOR row=0 TO 23 DO', 'FOR row=0 TO 1 DO')
        text = text.replace('BYTE POINTER(@spans),240)=240', 'BYTE POINTER(@spans),20)=20')
        source = out / 'spans.act'
        source.write_text(text)
    program = build(compiler(ROOT / 'build/actionc', release=True), source, out,
                    optimize=mode == 'opt', tasks=True, task_capacity=8,
                    console=True, memory_profile=memory)
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
    return dict(status='pass', tier='development', qualification=False, case=mode,
                checks=checks, runtime=runtime, machine=machine, build=program['build'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(out, args.case)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Console spans', args.case, result['checks'], 'checks passed', flush=True)
