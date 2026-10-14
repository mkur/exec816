#!/usr/bin/env python3
"""Execute protocol constants and the existing scripted serial boundary."""
import argparse
import json
from pathlib import Path
from fujinet_peer import make_peer
from native_program import ROOT, build, compiler, require, verify_machine, sha256, read_build
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_sio_device import PIN


def run(output, reuse=None):
    output.mkdir(parents=True, exist_ok=True)
    peer = make_peer(output / 'peer')
    p = read_build(reuse) if reuse else build(compiler(ROOT / 'build/actionc', release=True),
              ROOT / 'tests/programs/fujinet_protocol.act', output,
              optimize=True, tasks=True)
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        b.device_set('custom', path=str(peer))
        for k, v in PIN['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        runtime, _ = execute(b, p, timeout=180, frame_limit=9000)
        checks = data(b, p['image'], 'checks', True)[0]
        require(checks == 161, f'Protocol checks incomplete: {checks}')
        ownership(b, p, output)
    return dict(status='pass', tier='development', checks=checks, build=p['build'],
                machine=machine, runtime=runtime, peer_sha256=sha256(peer),
                bank_zero_delta=dict(fixed=0, per_task=0, idle=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/fujinet/fn0')
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.from_build)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('FujiNet protocol and scripted serial boundary passed', result['checks'])
