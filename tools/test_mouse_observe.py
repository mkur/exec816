#!/usr/bin/env python3
"""M0: emitted read-only observation of the existing ST/port 1 model."""
import argparse
import json
import os
import re
from pathlib import Path

import adapter_state as adapter
from native_program import ROOT, build, compiler, execute, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_heap_api import clean_ownership

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
BRIDGE = ROOT/'build/mouse-bridge'
ROM = ROOT/'build/firmware/altirraos-816.rom'


def run(out, mode, replay=False, burst=False):
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', tier='development', slice='M0', mode=mode)
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                'Unpinned mouse bridge')
        p = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/mouse_observe.act',
                  out/'program', tasks=True, task_capacity=8, optimize=mode == 'opt')
        at = lambda name: next(d['address'] for d in p['image']['data']
                              if d['name'].startswith('M_MOUSEOBSERVE_'+name.upper()+'_'))
        if replay:
            os.environ.pop('EXEC816_MOUSE_TRACE', None)
        else:
            os.environ['EXEC816_MOUSE_TRACE'] = '1'
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROM, PIN)
            def reach(condition):
                b.bp_clear_all()
                b.bp_set(p['labels']['native_nmi'], condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                run_to(b, p['labels']['native_nmi'], condition=condition, timeout=30, frame_limit=500)
            def snapshot():
                return dict(pia=b.pia(), pokey=b.pokey(), gractl=b.gtia()['GRACTL'],
                            mask=b.memdump(16, 1).hex(), skctl=b.memdump(0x232, 1).hex())
            commands = []
            saved = {}
            def before(bridge):
                b._cmd_ok('MOUSE ST')
                reach(f'db(${at("stage"):x})=1')
                saved.update(snapshot())
                require(int(saved['gractl'].lstrip('$'), 16) & 4 == 0,
                        'GTIA trigger latch unexpectedly enabled')
                # One phase per command. Four transitions complete a cycle;
                # the phase trace remains independent of target sampling.
                movements = [(16, 0)]*8 + [(-16, 0)]*8 + [(0, 16)]*8 + [(0, -16)]*8
                if burst:
                    movements = [(128, 0), (-128, 0), (0, 128), (0, -128)]
                for i, (dx, dy) in enumerate(movements):
                    command = f'MOUSE AT {2000+i*(200000 if burst else 36000)} {dx} {dy} -1'
                    commands.append(dict(command=command, **b._cmd_ok(command)))
                for delay, state in ((1180000, 1), (1200000, 0)):
                    command = f'MOUSE AT {delay} 0 0 {state}'
                    commands.append(dict(command=command, **b._cmd_ok(command)))
                reach(f'@frame>={b.eval_expr("@frame")+40}')
                b.memload(at('stop'), b'\1')
                b.bp_clear_all()
            runtime, _ = execute(b, p, before_run=before, frame_limit=800, timeout=60)
            count = b.peek16(at('count'))
            raw = b.memdump(at('samples'), count*4)
            samples = [list(raw[i:i+4]) for i in range(0, len(raw), 4)]
            # Independent cyclic patterns specified by the ST port wiring.
            expected = [(15, 1)]
            for direction, shift in ((1, 0), (-1, 0), (1, 2), (-1, 2)):
                cycle = [0, 2, 3, 1]
                for n in range(1, 9):
                    expected.append((15 ^ (cycle[(direction*n) % 4] << shift), 1))
            expected += [(15, 0), (15, 1)]
            require([tuple(s[:2]) for s in samples] == expected,
                    'Electrical observation differs: '+str(samples))
            require(snapshot() == saved, 'Observation changed hardware state')
            clean_ownership(b, p, p['output'])
            report.update(samples=samples, commands=commands, runtime=runtime,
                          hardware_before=saved, hardware_after=snapshot(),
                          stack_usage=stack_usage(b, p['build']['memory']))
        trace = [list(map(int, m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)',
                                                       (out/'emulator.log').read_text())]
        if not replay:
            require(len(trace) == 34, 'Incomplete independent controller trace')
            require([(15 ^ (r[1] & 15), 1 ^ ((r[1] >> 8) & 1)) for r in trace] == expected[1:],
                    'Controller trace differs from independent oracle')
        report.update(status='pass', build=p['build'], xex_sha256=sha256(p['xex']),
                      pin=PIN, observer=not replay, burst=burst, controller_trace=trace,
                      bank_zero_delta=dict(fixed=0, per_task=[0]*8, private_idle=0))
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('ST mouse observation passed:', mode, 'replay' if replay else 'observed', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--burst', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.replay, args.burst)
