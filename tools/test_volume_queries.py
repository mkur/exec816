#!/usr/bin/env python3
"""Focused public volume enumeration and packet ownership checks."""
import argparse
import json
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sio_device import PIN
from generate_memory import PROFILE


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 4096
    memory = output/'memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    p = build(compiler(ROOT/'build/actionc', release=True), ROOT/'tests/programs/volume_queries.act',
              output, optimize=True, tasks=True, task_capacity=8,
              console_deferred=True, memory_profile=memory,
              dos_mounts=[dict(alias='RAM', format=3)])
    with emulator(ROOT/'build/altirra-sio-multi',
                  ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as b:
        machine = verify_machine(b, ROOT/'build/firmware/altirraos-816.rom', PIN)
        try:
            runtime, _ = execute(b, p, timeout=180, frame_limit=6000)
        except Exception:
            print('Volume query checks:', data(b, p['image'], 'checks', True), flush=True)
            raise
        ownership(b, p, output)
        require(data(b, p['image'], 'finished') == [1], 'Incomplete volume queries')
        report = dict(status='pass', tier='development', machine=machine,
                      build=p['build'], runtime=runtime,
                      checks=data(b, p['image'], 'checks', True),
                      bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Public volume queries passed', report['checks'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=lambda s: (ROOT/s).resolve(), required=True)
    run(parser.parse_args().output)
