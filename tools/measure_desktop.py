#!/usr/bin/env python3
"""Passive physical ST capture/consumption and actual scanout observations."""
import argparse
from bisect import bisect_left
import hashlib
import json
import math
import os
from pathlib import Path
import re

import adapter_state as adapter
from native_program import ROOT, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from make_data_disk import make
from test_gem_cursor import ARROW
from gem_render_oracle import PALETTE, PENS
from sio_transaction_trace import read_events, BASE_HZ
from bitmap_console_performance import native_markers
from desktop_budget import delta


def distribution(values):
    if not values:
        return dict(count=0)
    ordered = sorted(values)
    return dict(count=len(values), median_ms=ordered[len(values)//2],
                p95_ms=ordered[math.ceil(len(values)*.95)-1], max_ms=max(values))


def trace_report(path, marks, windows, samples, native):
    events = read_events(path)
    times = lambda pc: [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == pc]
    reads = times(marks['pointer_port_read'])
    starts, ends = times(marks['pointer_sample']), times(marks['pointer_sample_return'])
    entries, exits = times(marks['native_irq']), times(marks['signal_route_return'])
    consumed, notified = times(marks['consume']), times(marks['pointer_notify'])
    service = times(marks['input_service'])
    cursor_entries = times(native['cursor']['entry'])
    cursor_returns = sorted(t for pc in native['cursor']['returns'] for t in times(pc))
    phases = [list(map(int, m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)', path.read_text())]
    decoded = []
    cycle = [0, 2, 3, 1]
    previous = 0
    counters = [0, 0]
    phase_gaps = []
    last = [None, None]
    edges = 0
    for t, bits, _, _ in phases:
        for axis, shift in enumerate((0, 2)):
            amount = (cycle.index((bits >> shift) & 3)-cycle.index((previous >> shift) & 3)) % 4
            require(amount != 2, 'Independent trace skipped a phase')
            if amount:
                counters[axis] += 1 if amount == 1 else -1
                if last[axis] is not None:
                    phase_gaps.append(t-last[axis])
                last[axis] = t
        edges += bool((bits ^ previous) & 256)
        previous = bits
        decoded.append((t, *counters, (bits >> 8) & 1))
    require(phase_gaps and min(phase_gaps)/BASE_HZ >= .001, 'Stimulus exceeds the supported phase envelope')
    phase_times = [v[0] for v in decoded]
    result = {}
    for name, (begin, end) in windows.items():
        # The debugger exposes the same wrapping base clock as the trace. Align
        # read-only observations to the independently extended event timeline.
        align = lambda value: value + round((reads[0]-value)/(1 << 32))*(1 << 32)
        begin, end = align(begin), align(end)
        selected = [t for t in reads if begin <= t <= end]
        gaps = [b-a for a, b in zip(selected, selected[1:])]
        costs = []
        for t in entries:
            if begin <= t <= end:
                i = bisect_left(exits, t)
                if i < len(exits) and exits[i] <= end:
                    costs.append(exits[i]-t)
        services = [t for t in service if begin <= t <= end]
        spans = [b-a for a, b in zip(services, services[1:])]
        observed = [s for s in samples if s['load'] == name]
        for s in observed:
            lower, upper = align(s['submitted_clock']), align(s['capture_observed_clock'])
            captures = [t for t in notified if lower <= t <= upper]
            require(captures, 'Missing captured pointer publication')
            captured = captures[-1]
            i = bisect_left(consumed, captured)
            require(i < len(consumed), 'Missing pointer consumption')
            electrical = decoded[bisect_left(phase_times, captured)-1]
            if 'record' in s:
                raw = bytes.fromhex(s['record'])
                counts = [int.from_bytes(raw[n:n+4], 'little', signed=True) for n in (12, 16)]
                require(counts == list(electrical[1:3]), 'Capture differs from independent electrical counts')
                require(raw[11] == electrical[3], 'Captured button differs from electrical level')
            s['capture_cycle'] = captured
            s['consume_cycle'] = consumed[i]
            s['capture_to_consume_ms'] = (consumed[i]-captured)/BASE_HZ*1000
            if 'visible_clock' in s:
                s['capture_to_visible_ms'] = (align(s['visible_clock'])-captured)/BASE_HZ*1000
        motion = [s['capture_to_visible_ms'] for s in observed if s['kind'] == 'motion']
        button = [s['capture_to_consume_ms'] for s in observed if s['kind'] == 'button']
        cursor_costs = []
        for t in cursor_entries:
            if begin <= t <= end:
                i = bisect_left(cursor_returns, t)
                if i < len(cursor_returns) and cursor_returns[i] <= end:
                    cursor_costs.append((cursor_returns[i]-t)/BASE_HZ*1000)
        max_gap = max(gaps)/BASE_HZ*1000
        result[name] = dict(sample_count=len(selected), sample_gap=distribution([v/BASE_HZ*1000 for v in gaps]),
            sample_gap_pass=max_gap < 1, irq_entry_through_routing_share=sum(costs)/(end-begin),
            irq_scope='Elapsed native IRQ entry through signal routing; excludes final dispatch/RTI',
            active_and_idle_input_service_gap=distribution([v/BASE_HZ*1000 for v in spans]),
            visible=distribution(motion), button_consumption=distribution(button),
            cursor_call_elapsed=distribution(cursor_costs),
            minimum_electrical_phase_ms=min(phase_gaps)/BASE_HZ*1000, independent_button_edges=edges)
        limit = (40, 60) if name == 'idle' else (60, 100)
        result[name]['visible_target_pass'] = bool(motion) and distribution(motion)['p95_ms'] <= limit[0] and max(motion) <= limit[1]
        result[name]['button_target_pass'] = bool(button) and max(button) <= (40 if name == 'idle' else 100)
    return result


def run(out, program, count=100, unobserved=False, loads=('idle', 'scroll', 'disk')):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    pin = json.loads(json.dumps(PIN))
    fastest = p['build']['dos_mounts'][0]['profile'] == 1
    if fastest:
        pin['startup_configuration']['diskemu'] = 'fastest'
    at = lambda module, name: next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    second_app = any('_DESKAPP_WINDOWID_' in d['name'] for d in p['image']['data'])
    native = native_markers(p, [('DESKINPUT_CONSUME', 'consume'), ('DESKINPUT_SERVICE', 'input_service'),
                              ('CONSOLEBITMAP_CURSOR', 'cursor')])
    marks = {k: v for k, v in p['labels'].items() if k.startswith(('sio_', 'timer_', 'native_', 'signal_route', 'pointer_'))}
    marks.update({k: v['entry'] for k, v in native.items()})
    pcs = set(marks.values()) | {pc for v in native.values() for pc in v['returns']}
    for name in ('EXEC816_MOUSE_TRACE', 'EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE'):
        os.environ.pop(name, None)
    if not unobserved:
        os.environ.update(EXEC816_MOUSE_TRACE='1', EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='1',
                          EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in pcs))
    files = out/'media/TOOLS/SUB'
    files.mkdir(parents=True, exist_ok=True)
    (files/'DATA.BIN').write_bytes(bytes(i & 255 for i in range(32768)))
    disk = out/'disk.atr'
    make(disk, out/'media', binary_names={'TOOLS/SUB/DATA.BIN'}, filesystem='sdfs')
    report = dict(status='running', tier='development', qualification=False, build=p['build'],
                  pin=pin, samples=[], windows={}, observer=not unobserved,
                  reserved_bank_zero_delta=delta(p['build']['memory']), marks=marks,
                  media_sha256=sha256(disk), scanout_scope='Actual last completed scanout; observation is an upper bound, at most one frame late')
    try:
        with emulator(BRIDGE, ROM, out, pin=pin) as b:
            b.config('diskemu', 'fastest' if fastest else 'generic56k')
            b.mount(0, str(disk))
            b._cmd_ok('MOUSE ST')
            require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned mouse emulator')
            report['machine'] = verify_machine(b, ROM, pin)
            read = lambda module, name, size=2: int.from_bytes(b.memdump(at(module, name), size), 'little')
            clock = lambda: b.eval_expr('@clk') & 0xffffffff
            def reach(condition, label='native_nmi'):
                marker = p['labels'][label]
                b.bp_clear_all()
                b.bp_set(marker, condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                run_to(b, marker, condition=condition, frame_limit=8000, timeout=100)
            def frames(n):
                reach(f'@frame>={b.eval_expr("@frame")+n}')
            capture = p['build']['memory']['input_storage']['POINTER_CAPTURE']
            rgb = bytes((v & 254)+(v >> 7) for v in PALETTE)
            colors = {hw: rgb[pen*3:pen*3+3][::-1] for pen, hw in enumerate(PENS)}
            def scan(old, new):
                x0, y0 = min(old[0], new[0]), min(old[1], new[1])
                x1, y1 = max(old[0], new[0])+16, max(old[1], new[1])+16
                path = out/'scanout.bgra'
                frame = b.rawscreen(str(path))
                raw = path.read_bytes()
                expected = bytearray()
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        char = ARROW[y-new[1]][x-new[0]] if 0 <= x-new[0] < 16 and 0 <= y-new[1] < 16 else '.'
                        expected.extend(colors[15 if char == 'X' else 0 if char == 'O' else PENS[8]])
                actual = b''.join(raw[y*frame.stride+(x+16)*4:y*frame.stride+(x+16)*4+3]
                                  for y in range(y0, y1) for x in range(x0, x1))
                return actual == expected, hashlib.sha256(actual).hexdigest()
            def hardware():
                return {name: b.memdump(address, size).hex() for name, address, size in
                        [('mask', 16, 1), ('skctl', 0x232, 1), ('timer', 0x210, 2),
                         ('key', 0x208, 2), ('break', 0x236, 2), ('display', 0x22f, 3), ('memac', 0xd65e, 2)]}
            def before(bridge):
                if not unobserved:
                    b.profile_start()
                report['hardware_before'] = hardware()
                reach(f'dw(${at("DESKTEST", "ready"):x})=1')
                # Exercise the graphical route before motion timing. Keys and
                # BREAK must reach the client; hidden-window routes retire.
                b.memload(at('DESKTEST', 'mode'), (4).to_bytes(2, 'little'))
                panel = read('DESKTEST', 'panel', 4)
                reach(f'(dw(${at("DESKTEST", "lastKind"):x})=6)&(dw(${at("DESKTEST", "lastWindow"):x})={panel})')
                require(b._cmd_ok('KEY A down')['raw_scan'], 'Nonphysical keyboard')
                reach(f'dw(${at("DESKTEST", "keyCount"):x})=1')
                b._cmd_ok('KEY A up')
                require(read('DESKTEST', 'lastWindow', 4) == panel, 'Key missed graphical destination')
                b._cmd_ok('KEY BREAK down')
                reach(f'dw(${at("DESKTEST", "cancelCount"):x})=1')
                b._cmd_ok('KEY BREAK up')
                b.memload(at('DESKTEST', 'mode'), bytes(2))
                frames(30)
                require(read('DESKTEST', 'keyCount') == 1, 'Duplicate graphical key')
                report['graphical_keyboard'] = dict(keys=1, breaks=1, destination=panel)
                position = [320, 120]
                if second_app:
                    # Select the independently scheduled application's exposed
                    # client area. Graphical keys now drive real compute/repaint.
                    for i in range(264):
                        b._cmd_ok(f'MOUSE AT {2000+i*4000} 16 {16 if i<32 else 0} -1')
                    reach(f'(dw(${at("DESKINPUT", "cursorX"):x})=584)&(dw(${at("DESKINPUT", "cursorY"):x})=152)')
                    b._cmd_ok('MOUSE AT 3000 0 0 1')
                    reach(f'dw(${at("DESKAPP", "updates"):x})>=1')
                    frames(2)
                    b._cmd_ok('MOUSE AT 3000 0 0 0')
                    reach(f'dw(${at("DESKINPUT", "buttons"):x})=0')
                    position = [584, 152]
                # Paced one-phase changes move to a blank desktop margin; no
                # burst injection or sensitivity adjustment is used.
                dx, dy = 590-position[0], 24-position[1]
                for i in range(max(abs(dx), abs(dy))):
                    b._cmd_ok(f'MOUSE AT {2000+i*4000} {16 if i<dx else 0} {-16 if i<abs(dy) else 0} -1')
                reach(f'(dw(${at("DESKINPUT", "cursorX"):x})=590)&(dw(${at("DESKINPUT", "cursorY"):x})=24)')
                frames(3)
                position = [590, 24]
                for load in loads:
                    mode = {'idle': 0, 'scroll': 2, 'disk': 3}[load]
                    b.memload(at('DESKTEST', 'mode'), mode.to_bytes(2, 'little'))
                    begin = clock()
                    for i in range(count):
                        if second_app and i % 10 == 0:
                            b._cmd_ok('KEY SPACE down')
                        # Change one diagonal phase and reverse every ten steps.
                        dx = 1 if (i//10) % 2 == 0 else -1
                        old = list(position)
                        position = [position[0]+dx, position[1]+dx]
                        head = b.peek(capture+1)[0]
                        submitted = clock()
                        b._cmd_ok(f'MOUSE AT {2000+(i*379)%7000} {dx*16} {dx*16} -1')
                        reach(f'db(${capture+1:x})!={head}', 'native_irq')
                        raw = b.memdump(capture+128+(head & 31)*24, 24)
                        item = dict(load=load, kind='motion', submitted_clock=submitted,
                                    capture_observed_clock=clock(), record=raw.hex(), position=position)
                        report['samples'].append(item)
                        for attempt in range(12):
                            matches, digest = scan(old, position)
                            if matches:
                                break
                            reach(f'@frame>{b.eval_expr("@frame")}', 'native_irq')
                        require(matches, 'Pointer scanout failed: '+str(item))
                        item.update(visible_clock=clock(), scanout_sha256=digest, scans=attempt+1)
                        require([read('DESKINPUT', 'cursorX'), read('DESKINPUT', 'cursorY')] == position, 'Decoded phase count mismatch')
                        # Thirty clicks (sixty separately observed edges), each
                        # level held for at least a full PAL frame.
                        if i < 60:
                            pressed = 1 if i % 2 == 0 else 0
                            head = b.peek(capture+1)[0]
                            submitted = clock()
                            b._cmd_ok(f'MOUSE AT 3000 0 0 {pressed}')
                            reach(f'db(${capture+1:x})!={head}', 'native_irq')
                            item = dict(load=load, kind='button', submitted_clock=submitted,
                                        capture_observed_clock=clock(), buttons=pressed,
                                        record=b.memdump(capture+128+(head & 31)*24, 24).hex())
                            report['samples'].append(item)
                            reach(f'dw(${at("DESKINPUT", "buttons"):x})={pressed}')
                            frames(1)
                        if second_app and i % 10 == 0:
                            b._cmd_ok('KEY SPACE up')
                        if i % 20 == 0:
                            print(load, i, flush=True)
                    report['windows'][load] = [begin, clock()]
                    report.setdefault('progress', {})[load] = dict(writes=read('DESKTEST', 'writes'), reads=read('DESKTEST', 'reads'))
                if second_app:
                    report['independent_app_updates'] = read('DESKAPP', 'updates')
                    require(report['independent_app_updates'] > 1, 'Second app did not repaint')
                b.memload(at('DESKTEST', 'mode'), (9).to_bytes(2, 'little'))
                b.bp_clear_all()
            report['runtime'], _ = execute(b, p, before_run=before, timeout=120, frame_limit=12000)
            if not unobserved:
                b.profile_stop()
            ownership(b, p, p['output'])
            report['hardware_after'] = hardware()
            require(report['hardware_after'] == report['hardware_before'], 'Input/display hardware not restored')
            require(b.memdump(at('DESKINPUT', 'lease'), 32) == bytes(32), 'Pointer lease retained')
        report['controller_trace'] = [list(map(int, m)) for m in re.findall(r'MOUSE_PHASE (\d+) (\d+) (\d+) (\d+)', (out/'emulator.log').read_text())]
        if not unobserved:
            report['timing'] = trace_report(out/'emulator.log', marks, report['windows'], report['samples'], native)
            if 'disk' in loads:
                from gem_mouse_observe import timing
                report['shared_timer'], _ = timing(out/'emulator.log', p['labels'], divisor=0 if fastest else 8)
            require(all(v['sample_gap_pass'] for v in report['timing'].values()), 'Sampling envelope failed')
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--unobserved', action='store_true')
    parser.add_argument('--loads', nargs='+', choices=('idle', 'scroll', 'disk'), default=['idle', 'scroll', 'disk'])
    args = parser.parse_args()
    run(args.output.resolve(), args.program, args.count, args.unobserved, args.loads)
