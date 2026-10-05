#!/usr/bin/env python3
"""Observe native presenter wakeups in a settled desktop without input traffic."""
import argparse
import json
import os
from pathlib import Path

import adapter_state as adapter
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, flat_markers
from native_program import read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from sio_transaction_trace import read_events
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out, program):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    spans = native_markers(p, [('DESKHOST_CONTROLS', 'controls'),
                              ('DESKCORE_PUMP', 'native_intake')])
    restore = p['labels']['context_restore']
    code = (p['output']/'hosted.bin').read_bytes()
    require(code[restore-0x1400:restore-0x1400+8] == bytes.fromhex('c230ab2b7afa6840'),
            'Unknown context restore for presenter accounting')
    points = {name: p['labels'][name] for name in ('native_irq', 'native_nmi', 'interrupt_schedule')}
    points.update(turn=spans['controls']['entry'], selected=restore+4,
                  worker_retire=p['labels']['done'])
    definition = dict(points=points, spans=spans,
                      task_dps=[pool['dp'] for pool in p['build']['memory']['task_pools']])
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{v:x}' for v in flat_markers(definition).values())
    report = dict(status='running', tier='development', qualification=False,
                  build_sha256=sha256(p['output']/'build.json'), xex_sha256=sha256(p['xex']))
    address = lambda name: next(d['address'] for d in p['image']['data'] if '_DESKTEST_'+name.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            report['machine'] = verify_machine(b, ROM, PIN)
            b._cmd_ok('MOUSE ST')

            def before(bridge):
                b.profile_start()

                def reach(condition):
                    b.bp_clear_all()
                    b.bp_set(p['labels']['native_nmi'], condition=condition)
                    b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                    run_to(b, p['labels']['native_nmi'], condition=condition,
                           frame_limit=8000, timeout=100)

                reach(f'dw(${address("ready"):x})=1')
                reach(f'@frame>={b.eval_expr("@frame")+150}')
                begin = b.eval_expr('@clk') & 0xffffffff
                reach(f'@frame>={b.eval_expr("@frame")+50}')
                report['idle_window'] = [begin, b.eval_expr('@clk') & 0xffffffff]
                b.poke16(address('mode'), 9)
                b.bp_clear_all()

            report['runtime'], _ = execute(b, p, before_run=before, timeout=120, frame_limit=10000)
            ownership(b, p, p['output'])
            b.profile_stop()
        events = read_events(out/'emulator.log')
        profile = analyze_events(events, definition)
        first = next(t for t, event in events if event[0] == 'cpu')
        begin, end = [value+round((first-value)/(1 << 32))*(1 << 32) for value in report['idle_window']]
        report['idle_presenter_turns'] = sum(begin <= t <= end and event[0] == 'cpu'
            and int(event[4], 16) == spans['controls']['entry'] for t, event in events)
        report['pump_cost'] = profile['routines']
        report['pump_cost_scope'] = 'Startup and retirement, excluding off-Task and interrupt time; idle count covers 50 settled PAL frames.'
        report['trace_sha256'] = sha256(out/'emulator.log')
        require(report['idle_presenter_turns'] == 0, 'Settled presenter wakes without input')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Settled presenter:', report['idle_presenter_turns'], 'turns in 50 frames')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--program', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.program.resolve())
