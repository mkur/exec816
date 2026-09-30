#!/usr/bin/env python3
"""Native device/mount snapshots: lifetime, nesting, capacity and far buffers."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_console_coexistence import PIN


def run(mode, out):
    bridge = ROOT/'build/console-bridge'
    require(sha256(bridge/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Unpinned inspection bridge')
    p = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/system_inspect.act', out,
              optimize=mode=='opt', tasks=True, task_capacity=8, console=False, dos_mounts=[],
              image_data=[(0xdffe8, bytes([0xa5])*512)])
    with emulator(bridge, ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=120, frame_limit=6000)
        require(data(b, p['image'], 'finished') == [1], 'System inspection incomplete')
        require(runtime['created'] == 0, 'Inspection unexpectedly started a worker')
        ownership(b, p, out)
        return dict(status='pass', mode=mode, checks=data(b, p['image'], 'checks', True),
                    build=p['build'], runtime=runtime, machine=machine, pin=PIN)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = run(args.case, out)
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('System inspection passed', args.case, result['checks'])
