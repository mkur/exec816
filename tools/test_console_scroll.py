#!/usr/bin/env python3
"""Measure idle scrolling in guest ticks, with no disks or SIO worker."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT / 'toolchain/altirra-shell-paced.json').read_text())
PHASES = ('core_scroll', 'display_redraw', 'worker_hidden', 'worker_visible',
          'small_reply', 'small_visible', 'tile_reply', 'tile_visible')
INPUTS = ('lib/console/consolecore.act', 'lib/console/consoledisplay.act', 'lib/console/consoleinput.act',
          'lib/console/consoledriver.act', 'tests/programs/console_scroll.act',
          'lib/console/consolewindows.act', 'lib/console/consoletiling.act',
          'tools/test_console_scroll.py', 'tools/console_scroll_trace.py')


def run(t, out, optimize, from_build=None, observe=False):
    from console_scroll_trace import observation, summarize
    out.mkdir(parents=True, exist_ok=True)
    bridge = ROOT / 'build/shell-paced-bridge'
    require(sha256(bridge / 'AltirraBridgeServer') == PIN['emulator']['sha256'],
            'Unpinned scrolling emulator')
    p = read_build(from_build) if from_build else build(t, ROOT / 'tests/programs/console_scroll.act', out,
              optimize=optimize, tasks=True, task_capacity=8, kernel_bank=2,
              console=False, console_test=True, stack_checks=True)
    require(p['build']['optimize'] == optimize, 'Wrong benchmark NIR mode')
    with observation(p, observe) as marks, emulator(bridge, ROOT / 'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        saved = {}

        def before(b):
            saved.update(address=b.peek16(88), cursor=b.peek(752))
            saved['screen'] = b.memdump(saved['address'], 960)
            if observe:
                b.profile_start()

        runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        if observe:
            b.profile_stop()
        ownership(b, p, p['output'])
        require(b.memdump(saved['address'], 960) == saved['screen']
                and b.peek(752) == saved['cursor'], 'Borrowed screen not restored')
        require(runtime['created'] == 1, 'Expected only root and console worker')
        require(runtime['kernel_stack_observation']['interrupt_reserve_bytes_touched'] == 0,
                'Kernel interrupt reserve touched')
        ticks = dict(zip(PHASES, data(b, p['image'], 'elapsed', True)))
        require(len(ticks) == len(PHASES) and all(v >= 0 for v in ticks.values()), 'Missing timings')
        # 16 bottom-row line feeds, including the final visible redraw. The
        # prior raw/optimized implementation takes 270/255 guest ticks.
        require(ticks['worker_visible'] <= 112, 'Idle scrolling exceeded 112 guest ticks')
        return dict(status='pass', mode='opt' if optimize else 'raw', repetitions=16,
                    scope='No mounted disks or SIO worker; direct loops, then root plus '
                          'console worker; PAL 8x; stack checks enabled; guest RTC ticks. '
                          'Visibility polling yields rather than sleeping for a whole frame; '
                          'zero means below RTC resolution, not zero execution cost.',
                    ticks_50hz=ticks,
                    nominal_ms_per_scroll={k: v * 20 / 16 for k, v in ticks.items()},
                    worker_visible_limit_ticks=112, checks=data(b, p['image'], 'checks', True),
                    build=p['build'], runtime=runtime, machine=machine, platform_pin=PIN,
                    observation=summarize(out/'emulator.log', marks) if observe else None,
                    inputs={name: sha256(ROOT / name) for name in INPUTS})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT / 'build/actionc')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(None if args.from_build else compiler(args.compiler_dir), out,
                     args.case == 'opt', args.from_build, args.observe)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Idle scrolling passed', args.case, result['nominal_ms_per_scroll'], flush=True)
