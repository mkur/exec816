#!/usr/bin/env python3
"""Real standard-console resident mount workflow, redirection and EXECUTE."""
import argparse
import json
import shutil
from pathlib import Path
from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    media = output / 'data.atr'
    shutil.copyfile(ROOT / 'tests/fixtures/mydos/mydos450-128.atr', media)
    digest = sha256(media)
    profile = json.loads(PROFILE.read_text()); profile['image_data_bytes'] = 8192
    memory = output / 'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    p = build(compiler(ROOT / 'build/actionc', release=True),
              ROOT / 'tests/programs/user_mount_shell.act', output,
              optimize=True, tasks=True, task_capacity=8, console=True,
              memory_profile=memory, dos_mounts=[dict(alias='RAM', format=3)])
    with emulator(ROOT / 'build/altirra-sio-multi',
                  ROOT / 'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.config('diskemu', 'generic56k'); b.mount(1, str(media))
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, p, timeout=240, frame_limit=12000)
        except Exception:
            print('Shell mount checks:', data(b, p['image'], 'checks', True), flush=True)
            raise
        require(data(b, p['image'], 'finished') == [1], 'Incomplete shell mount workflow')
        checks = data(b, p['image'], 'checks', True)
        ownership(b, p, output)
    require(sha256(media) == digest, 'Shell admission modified media')
    result = dict(status='pass', tier='development', checks=checks,
                  machine=machine, runtime=runtime, build=p['build'],
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output / 'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Shell mount workflow passed:', checks, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.output.resolve())
