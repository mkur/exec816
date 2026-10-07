#!/usr/bin/env python3
"""Physical timed streams under load, checked against a captured-fact oracle."""
import argparse
import json
import os
from pathlib import Path
from generate_input_native import definitions
from make_data_disk import make
from mouse_acceleration_oracle import Pointer
from native_program import read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN


def run(out, program):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    offsets, _ = definitions()
    capture = p['build']['memory']['input_storage']['POINTER_CAPTURE']
    at = lambda name: next(d['address'] for d in p['image']['data'] if name in d['name'])
    for name in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(name, None)
    os.environ['EXEC816_MOUSE_TRACE'] = '1'
    media = out/'media/TOOLS/SUB'; media.mkdir(parents=True, exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(range(256))*128)
    make(out/'disk.atr', out/'media', binary_names={'TOOLS/SUB/DATA.BIN'}, filesystem='sdfs')
    report = dict(status='running', tier='development', qualification=False, build=p['build'], traces=[])
    try:
        with emulator(BRIDGE, ROM, out, pin=PIN) as b:
            b.mount(0, str(out/'disk.atr')); b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)
            def value(field, size=1):
                return int.from_bytes(b.memdump(capture+offsets['POINTERCAPTURE_'+field], size), 'little')
            def reach(condition):
                marker = p['labels']['native_irq']
                b.bp_clear_all(); b.bp_set(marker, condition=condition)
                run_to(b, marker, condition=condition, timeout=120, frame_limit=6000)
            def frames(n):
                reach(f'@frame>={b.eval_expr("@frame")+n}')
            def point():
                return [int.from_bytes(b.memdump(at('_DESKINPUT_'+n+'_'), 2), 'little') for n in ('CURSORX','CURSORY')]
            def before(bridge):
                reach(f'dw(${at("_DESKTEST_READY_"):x})=1'); frames(30)
                oracle = Pointer(*point(), p['build']['desktop_mouse']['profile'])
                traces = [('alternating', [(1,0,4000),(0,1,4000)]*12),
                          ('thresholds', [(1,1,gap) for gap in (9000,11000,15000,18000,22000,30000)]*2),
                          ('pause-reverse', [(-1,-1,70000)] + [(-1,0,9000),(0,-1,9000)]*8)]
                for load, mode in [('idle',0),('scroll',2),('disk',3)]:
                    b.poke16(at('_DESKTEST_MODE_'), mode)
                    reach(f'dw(${at("_DESKTEST_RUNNINGMODE_"):x})={mode}')
                    for name, commands in traces:
                        frames(10)
                        require(value('HEAD') == value('TAIL'), 'Capture did not drain')
                        start = seen = value('HEAD'); epoch = value('EPOCH',2)
                        counts = [value(axis+'COUNT',4) for axis in ('X','Y')]
                        delay = 70000
                        for dx,dy,gap in commands:
                            delay += gap
                            b._cmd_ok(f'MOUSE AT {delay} {dx*16} {dy*16} -1')
                        end = b.eval_expr('@frame')+(delay+35567)//35568+16
                        high = 0
                        while b.eval_expr('@frame') < end:
                            reach(f'(db(${capture+1:x})!={seen})|(@frame>={end})')
                            seen = value('HEAD')
                            high = max(high,(seen-value('TAIL')) & 255)
                        require(value('HEAD') == value('TAIL'), 'Final capture did not drain')
                        require(value('EPOCH',2) == epoch and value('LOST') == 0, 'Unexpected capture loss')
                        delivered = []; index = start
                        while index != seen:
                            raw = b.memdump(capture+128+(index & 63)*28,28)
                            vector,steps = raw[25],int.from_bytes(raw[26:28],'little')
                            signs = [0,1,-1]
                            dx,dy = signs[vector & 3]*steps,signs[(vector >> 2) & 3]*steps
                            info = raw[24] | (32 if dx and dy else 0)
                            oracle.take(dx,dy,info)
                            delivered.append([dx,dy,info])
                            index = (index+1) & 255
                        actual_counts = [value(axis+'COUNT',4) for axis in ('X','Y')]
                        expected_counts = [(v+sum(c[a] for c in commands)) & 0xffffffff for a,v in enumerate(counts)]
                        require(actual_counts == expected_counts, 'Physical transitions lost')
                        require(point() == oracle.position, 'Loaded transform differs from rational oracle')
                        report['traces'].append(dict(load=load,name=name,commands=commands,
                            records=delivered,position=point(),observed_queue_high_water=high,
                            counts=actual_counts,epoch=epoch))
                        print(load,name,point(),'queue',high,flush=True)
                report['progress'] = {n:int.from_bytes(b.memdump(at('_DESKTEST_'+n+'_'),2),'little') for n in ('READS','WRITES')}
                require(all(report['progress'].values()), 'Load fixture made no progress')
                b.poke16(at('_DESKTEST_MODE_'),9); b.bp_clear_all()
            report['runtime'],_ = execute(b,p,before_run=before,timeout=180,frame_limit=16000)
            ownership(b,p,p['output'])
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error)); raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.program)
