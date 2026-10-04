#!/usr/bin/env python3
"""Read-only 12-key actual-scanout observer for a frozen bitmap shell image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import adapter_state as adapter
from native_program import read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM
from gem_render_oracle import font_bytes, PENS, PALETTE
from sio_transaction_trace import BASE_HZ, read_events
from measure_desktop import distribution
from console_model import read_cells


def run(bundle, out):
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    p = read_build(bundle)
    require(all(sha256(bundle/name) == value for name, value in manifest['artifacts'].items()), 'Changed frozen artifact')
    pin = manifest['pin']
    instance = p['build']['memory']['console_storage']['INSTANCE']
    capture = p['build']['memory']['input_storage']['CAPTURE']
    font = font_bytes(bundle/manifest['font_source'])
    colors = {hw: bytes((v & 254)+(v >> 7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen, hw in enumerate(PENS)}
    report = dict(status='running', build=p['build'], pin=pin, samples=[],
                  scanout_scope='First matching completed scanout; bounded observation, not drawing return')
    os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_LATENCY_PCS=f'{p["labels"]["input_capture"]:x}')
    for key in ('EXEC816_MASK_TRACE', 'EXEC816_MOUSE_TRACE'):
        os.environ.pop(key, None)
    try:
        with emulator(BRIDGE, ROM, out, pin=pin) as b:
            for key, value in manifest['configuration'].items():
                b.config(key, str(value).lower() if isinstance(value, bool) else value)
            media = bundle/manifest['media']
            b.mount(0, str(media))
            report['machine'] = verify_machine(b, ROM, pin)
            clock = lambda: b.eval_expr('@clk') & 0xffffffff
            def reach(condition, label='native_nmi'):
                b.bp_clear_all()
                b.bp_set(p['labels'][label], condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                run_to(b, p['labels'][label], condition=condition, timeout=120, frame_limit=12000)
            def frames(n):
                reach(f'@frame>={b.eval_expr("@frame")+n}')
            def key(name):
                head = b.peek16(capture+10)
                submitted = clock()
                require(b._cmd_ok(f'KEY {name} down')['raw_scan'], 'Nonphysical key')
                reach(f'dw(${capture+10:x})!={head}')
                recorded = clock()
                b._cmd_ok(f'KEY {name} up')
                return submitted, recorded
            def before(bridge):
                reach(f'(db(${instance+51:x})=2)&(db(${instance+194:x})=0)&(db(${instance+20:x})=0)')
                frames(5)
                b.profile_start()
                for index, char in enumerate(b'abcdefghijkl'):
                    column, row = b.peek16(instance+10), b.peek16(instance+12)
                    left, top = (column+5)*8, (row+5)*8 if manifest.get('desktop') else row*8
                    if not manifest.get('desktop'):
                        left = column*8
                    start, captured = key(chr(char).upper())
                    wanted = b''.join(colors[PENS[1] if font[y*256+char] & (128 >> x) else PENS[0]] for y in range(8) for x in range(8))
                    for attempt in range(12):
                        width = b.peek16(instance+4)
                        retained = read_cells(b.memdump, instance)
                        start_index = row*width+column
                        location = next((i for i in range(start_index, min(start_index+4, len(retained))) if retained[i] == char), None)
                        if location is not None:
                            left = ((location % width)+(5 if manifest.get('desktop') else 0))*8
                            top = ((location//width)+(5 if manifest.get('desktop') else 0))*8
                        frame = b.rawscreen(str(out/'echo.bgra'))
                        raw = (out/'echo.bgra').read_bytes()
                        actual = b''.join(raw[y*frame.stride+(x+16)*4:y*frame.stride+(x+16)*4+3] for y in range(top, top+8) for x in range(left, left+8))
                        if actual == wanted:
                            break
                        reach(f'@frame>{b.eval_expr("@frame")}')
                    require(actual == wanted, 'No visible echo for '+chr(char))
                    report['samples'].append(dict(key=chr(char), submitted=start, capture_observed=captured,
                                                  visible=clock(), position=[left, top], scans=attempt+1,
                                                  scanout_sha256=hashlib.sha256(actual).hexdigest()))
                    frames(1+(index % 3))
                b.profile_stop()
                for _ in range(12):
                    key('BACKSPACE')
                    frames(3)
                for name in 'EXIT':
                    key(name)
                    frames(3)
                b._cmd_ok('KEY RETURN down')
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, timeout=180, frame_limit=12000)
            ownership(b, p, p['output'])
        events = read_events(out/'emulator.log')
        captures = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == p['labels']['input_capture']]
        require(len(report['samples']) == 12, 'Wrong sample count')
        for sample in report['samples']:
            align = lambda value: value+round((captures[0]-value)/(1 << 32))*(1 << 32)
            matches = [t for t in captures if align(sample['submitted']) <= t <= align(sample['capture_observed'])]
            require(len(matches) == 1, 'Ambiguous physical key capture')
            tick = matches[0]
            visible = sample['visible']+round((tick-sample['visible'])/(1 << 32))*(1 << 32)
            sample['capture_cycle'] = tick
            sample['capture_to_visible_ms'] = (visible-tick)/BASE_HZ*1000
        report['timing'] = distribution([s['capture_to_visible_ms'] for s in report['samples']])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.bundle.resolve(), args.output.resolve())
