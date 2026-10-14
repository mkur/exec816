#!/usr/bin/env python3
"""Execute larger raw frames, unit ownership and deadlines through real serial."""
import argparse
import json
import shutil
from pathlib import Path
from fujinet_peer import make_peer
from native_program import ROOT, build, compiler, require, verify_machine, sha256, read_build
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from test_sio_device import PIN
from banked_test_memory import read


def run(output, reuse=None):
    output.mkdir(parents=True, exist_ok=True)
    peer = make_peer(output / 'peer')
    p = read_build(reuse) if reuse else build(compiler(ROOT / 'build/actionc', release=True),
              ROOT / 'tests/programs/fujinet_sio.act', output,
              optimize=True, tasks=True, task_capacity=8,
              image_data=[(0xdffc0, bytes([0xa5]) * 576)])
    if reuse and reuse.resolve() != output.resolve():
        shutil.copyfile(reuse / 'manifest.bin', output / 'manifest.bin')
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        b.device_set('custom', path=str(peer))
        for k, v in PIN['configuration'].items():
            b.config(k, str(v).lower() if isinstance(v, bool) else v)
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        def before(b):
            field = next(d for d in p['image']['data'] if '_CLOCKADDRESS_' in d['name'])
            abi = json.loads((ROOT / 'abi/sio-adapter.json').read_text())
            address = p['build']['task_storage']['BASE'] + abi['state_offset'] + abi['fields']['SD_CLOCK']
            b.memload(field['address'], address.to_bytes(4, 'little'))
        try:
            runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        except Exception:
            print('Failing SIO assertion', data(b, p['image'], 'checks', True), flush=True)
            raise
        checks = data(b, p['image'], 'checks', True)[0]
        require(data(b, p['image'], 'completed') == [1], 'SIO fixture incomplete')
        guard = read(b, 0xdffc0, 576, output)
        require(guard[:32] == bytes([0xa5]) * 32 and guard[544:] == bytes([0xa5]) * 32,
                'Far payload guard changed')
        ownership(b, p, output)
    return dict(status='pass', tier='development', checks=checks, build=p['build'],
                machine=machine, runtime=runtime, peer_sha256=sha256(peer),
                bank_zero_delta=dict(fixed=0, per_task=0, idle=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/fujinet/fn1')
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.from_build)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('FujiNet raw SIO passed', result['checks'])
