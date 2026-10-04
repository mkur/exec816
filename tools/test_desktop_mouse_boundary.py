#!/usr/bin/env python3
"""Desktop ST fastest supported controller spacing and aliasing negative control."""
import argparse
from desktop_mouse import scale
from generate_input_native import definitions
import json
import os
from pathlib import Path
import re
from bisect import bisect_left
import adapter_state as adapter
from native_program import read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN
from gem_mouse_observe import timing
from sio_transaction_trace import BASE_HZ


def run(out, program, unobserved=False):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    factor=scale(p)
    supported=[min(639,320+97*factor),min(239,120+97*factor),0]
    offsets, _ = definitions()
    capture = p['build']['memory']['input_storage']['POINTER_CAPTURE']
    at = lambda module, name: next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    for key in ('EXEC816_MOUSE_TRACE', 'EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(key, None)
    if not unobserved:
        os.environ.update(EXEC816_MOUSE_TRACE='1', EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='1', EXEC816_LATENCY_PCS=','.join(
            f'{v:x}' for k, v in p['labels'].items() if k.startswith(('pointer_', 'native_', 'signal_route', 'sio_', 'timer_'))))
    report = dict(status='running', observed=not unobserved, build=p['build'], pin=PIN, commands=[])
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)
            def reach(condition):
                b.bp_clear_all()
                b.bp_set(p['labels']['native_nmi'], condition=condition)
                run_to(b, p['labels']['native_nmi'], condition=condition, timeout=60, frame_limit=3000)
            def frames(n):
                reach(f'@frame>={b.eval_expr("@frame")+n}')
            def command(delay, dx=0, dy=0, left=-1):
                text = f'MOUSE AT {delay} {dx} {dy} {left}'
                report['commands'].append(dict(command=text, **b._cmd_ok(text)))
            def point():
                return [int.from_bytes(b.memdump(at('DESKINPUT', name), 2), 'little') for name in ('cursorX', 'cursorY', 'buttons')]
            def before(bridge):
                if not unobserved:
                    b.profile_start()
                reach(f'dw(${at("DESKTEST", "ready"):x})=1')
                frames(30)
                command(2000, 272, 272)
                for i in range(80):
                    command(2000+(16+16*i)*114, 16, 16)
                command(25000, left=1)
                command(65000, left=0)
                reach(f'(dw(${at("DESKINPUT", "cursorX"):x})={supported[0]})&(dw(${at("DESKINPUT", "cursorY"):x})={supported[1]})&(dw(${at("DESKINPUT", "buttons"):x})=0)')
                frames(20)
                report['supported_position'] = point()
                report['supported_capture_counts'] = [int.from_bytes(b.memdump(
                    capture+offsets['POINTERCAPTURE_'+axis+'COUNT'], 4), 'little', signed=True)
                    for axis in ('X', 'Y')]
                require(report['supported_capture_counts'] == [97, 97], 'Decoder lost supported phases')
                require(report['supported_position'] == supported, 'Scaled supported position differs')
                report['supported_end'] = b.eval_expr('@clk') & 0xffffffff
                # Three/four unseen transitions may alias without a LOSS. This
                # is explicitly outside the advertised per-axis envelope.
                command(2000, -4096, -4096)
                frames(60)
                report['burst_position'] = point()
                b.memload(at('DESKTEST', 'mode'), (9).to_bytes(2, 'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, timeout=120, frame_limit=12000)
            if not unobserved:
                b.profile_stop()
            ownership(b, p, p['output'])
        if not unobserved:
            phases = [list(map(int, m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)', (out/'emulator.log').read_text())]
            report['controller_trace'] = phases
            end = report['supported_end'] + round((phases[0][0]-report['supported_end'])/(1 << 32))*(1 << 32)
            cycle = [0, 2, 3, 1]
            prior = 0
            x, y = 320, 120
            gap, last, edges = [], [None, None], 0
            count = [0, 0]
            for t, bits, _, _ in phases:
                if t > end:
                    break
                for axis, shift in enumerate((0, 2)):
                    change = (cycle.index((bits >> shift) & 3)-cycle.index((prior >> shift) & 3)) % 4
                    require(change != 2, 'Trace skipped a controller phase')
                    if change:
                        step = 1 if change == 1 else -1
                        count[axis] += step
                        if last[axis] is not None:
                            gap.append(t-last[axis])
                        last[axis] = t
                edges += bool((bits ^ prior) & 256)
                prior = bits
            require(count == [97, 97] and edges == 2, 'Independent phase/button count mismatch')
            require(min(gap)/BASE_HZ >= .001, 'Supported rate fixture exceeded its envelope')
            require(report['supported_position'] == supported, 'Decoder lost supported motion')
            report['minimum_supported_phase_ms'] = min(gap)/BASE_HZ*1000
            # The negative controller command contains 256 transitions on each
            # axis. Count the electrical trace, rather than trust absence of loss.
            burst_count = [0, 0]
            burst_gaps, last = [], [None, None]
            for t, bits, _, _ in phases:
                if t <= end:
                    continue
                for axis, shift in enumerate((0, 2)):
                    change = (cycle.index((bits >> shift) & 3)-cycle.index((prior >> shift) & 3)) % 4
                    require(change != 2, 'Negative-control electrical trace skipped a phase')
                    if change:
                        burst_count[axis] += 1 if change == 1 else -1
                        if last[axis] is not None:
                            burst_gaps.append(t-last[axis])
                        last[axis] = t
                prior = bits
            require(burst_count == [-256, -256], 'Incomplete negative-control electrical trace')
            expected = [max(0, supported[0]+factor*burst_count[0]), max(0, supported[1]+factor*burst_count[1]), 0]
            report['burst_axis_counts'] = burst_count
            report['burst_minimum_phase_us'] = min(burst_gaps)/BASE_HZ*1e6
            report['burst_ideal_position'] = expected
            report['burst_alias_observed'] = report['burst_position'] != expected
            report['timing'], _ = timing(out/'emulator.log', p['labels'], serial=False)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--unobserved', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.program, args.unobserved)
