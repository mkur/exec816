#!/usr/bin/env python3
"""Cursor calls complete while another preemptible Task owns UPDATE."""
import argparse
import json
from pathlib import Path
import re

from calypsi_build import emit
from generate_memory import PROFILE
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from stack_budget import stack_usage
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    foreign = emit(out/'c', [ROOT/'c/calypsi/exec.c',
        ROOT/'tests/programs/cursor_scene.c'], [ROOT/'c/calypsi/gateway.s',
        ROOT/'c/calypsi/image-info.s'], [], roots=['CursorSceneApply'])
    source = ROOT/'tests/programs/cursor_scene.act'
    launcher = out/'cursor-scene.act'
    launcher.write_text(re.sub(r'\$(CursorScene\w+)',
        lambda m: f'${foreign["symbols"][m[1]]:x}', source.read_text()))
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 16384
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    program = build(compiler(ROOT/'build/actionc', release=True), launcher,
        out/'program', tasks=True, task_capacity=8, optimize=True,
        foreign_image=foreign, memory_profile=memory, console_deferred=True)
    report = dict(status='running', tier='development', qualification=False,
        build=program['build'], pin=PIN, runner_sha256=sha256(Path(__file__)),
        scope='Production local cursor dispatcher; only physical completion is substituted.')
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROM, PIN)
            report['runtime'], _ = execute(bridge, program, frame_limit=1800, timeout=90)
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            report['progress'] = int.from_bytes(bytes(
                data(bridge, program['image'], 'progress')), 'little')
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            require(report['checks'] == 64, 'Incomplete cursor scene checks: '+str(report['checks']))
            require(report['progress'] > 0, 'UPDATE-owner counter made no progress')
            ownership(bridge, program, program['output'])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Cursor scene checks passed:', report['checks'], flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
