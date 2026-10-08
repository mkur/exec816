#!/usr/bin/env python3
"""Physical ST profiles, fine/fast movement, clamping and edge reversal."""
import argparse
import json
import os
from pathlib import Path

import adapter_state as adapter
from desktop_budget import delta
from generate_input_native import definitions
from native_program import read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out, program):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    profile=p['build']['desktop_mouse']['profile']
    require(profile in ('off','mild'), 'Unknown desktop pointer profile')
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
            'Mouse emulator pin changed')
    offsets, _ = definitions()
    capture = p['build']['memory']['input_storage']['POINTER_CAPTURE']
    at = lambda module, name: next(d['address'] for d in p['image']['data']
                                  if '_'+module+'_'+name.upper()+'_' in d['name'])
    for key in ('EXEC816_MOUSE_TRACE', 'EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(key, None)
    report = dict(status='running', tier='development', qualification=False,
                  build=p['build'], steps=[], bank_zero_delta=delta(p['build']['memory']))
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)

            def reach(condition):
                b.bp_clear_all()
                marker = p['labels']['native_irq']
                b.bp_set(marker, condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                run_to(b, marker, condition=condition, timeout=60, frame_limit=3000)

            def frames(count):
                reach(f'@frame>={b.eval_expr("@frame")+count}')

            def point():
                return [int.from_bytes(b.memdump(at('DESKINPUT', name), 2), 'little')
                        for name in ('cursorX', 'cursorY')]

            def before(bridge):
                reach(f'dw(${at("DESKTEST", "ready"):x})=1')
                frames(20)
                require(point() == [320, 120], 'Initial screen position changed')
                counts = [0, 0]
                # Expectations are screen pixels, independent of the scale helper.
                cases=[(dx,dy,expected,8,85000) for dx,dy,expected in (
                    (5, -3, [330, 114]), (40, 20, [410, 154]),
                    (400, 200, [639, 239]), (-1, -1, [637, 237]),
                    (-4, -3, [629, 231]), (-500, -250, [0, 0]),
                    (1, 1, [2, 2]),
                )]
                if profile=='mild':
                    cases=[(5,-3,[325,117],1,36000),
                        (400,200,[639,239],2,130000),(-1,-1,[638,238],1,36000),
                        (-4,-3,[634,235],1,36000),(-650,-250,[0,0],2,130000),
                        (1,1,[1,1],1,36000)]
                for dx,dy,expected,packet,spacing in cases:
                    counts = [counts[0]+dx, counts[1]+dy]
                    item = dict(controller_steps=[dx, dy], expected=expected, commands=[])
                    index = 0
                    while dx or dy:
                        sx, sy = max(-packet, min(packet, dx)), max(-packet, min(packet, dy))
                        command = f'MOUSE AT {70000+index*spacing} {sx*16} {sy*16} -1'
                        b._cmd_ok(command)
                        item['commands'].append(command)
                        dx -= sx
                        dy -= sy
                        index += 1
                    # Finish every controller phase, including discarded overshoot,
                    # before checking immediate reversal. PAL has 35,568 base cycles/frame.
                    frames((70000+index*spacing+35567)//35568+20)
                    item['position'] = point()
                    item['capture_counts'] = [int.from_bytes(b.memdump(
                        capture+offsets['POINTERCAPTURE_'+axis+'COUNT'], 4), 'little', signed=True)
                        for axis in ('X', 'Y')]
                    report['steps'].append(item)
                    require(item['capture_counts'] == counts, 'Physical steps were lost')
                    require(item['position'] == expected, 'Scaled movement or edge reversal differs')
                    print('pointer', item['controller_steps'], '->', item['position'], flush=True)
                b.memload(at('DESKTEST', 'mode'), (9).to_bytes(2, 'little'))
                b.bp_clear_all()

            report['runtime'], _ = execute(b, p, before_run=before, timeout=120, frame_limit=12000)
            ownership(b, p, p['output'])
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
    args = parser.parse_args()
    run(args.output.resolve(), args.program)
