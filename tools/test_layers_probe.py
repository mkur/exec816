#!/usr/bin/env python3
"""Small emitted layout/access and transaction ABI probe, in either compiler mode."""
import argparse
import json
from pathlib import Path
from generate_layers import layout
from native_program import ROOT, build, compiler, verify_machine, require, sha256
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data
from stack_budget import stack_usage


def run(out, mode):
    out = out.resolve()
    size = layout()['Scene']['size']
    p = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/layers_probe.act',
              out/'program', optimize=mode == 'opt', tasks=True, task_capacity=8,
              console=False, image_data=[(0x11ffe0, bytes([0xa5])*(size+32))])
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned emulator')
        machine = verify_machine(b, ROM, PIN)
        runtime, _ = execute(b, p, timeout=120, frame_limit=12000)
        ownership(b, p, p['output'])
        raw = b.memdump(0x11ffe0, size+32)
        require(raw[:16] == raw[-16:] == bytes([0xa5])*16, 'Far scene guards changed')
        checks = data(b, p['image'], 'checks', True)[0]
        stacks = stack_usage(b, p['build']['memory'])
    result = dict(status='pass', tier='development', qualification=False, mode=mode,
                  scope='Far record layout/access, eight paint batches, early finish and call results',
                  layout=layout(), checks=checks, machine=machine, runtime=runtime,
                  stack_usage=stacks, build=p['build'])
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Layers boundary probe passed', mode, checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    args = parser.parse_args()
    run(args.output, args.mode)
