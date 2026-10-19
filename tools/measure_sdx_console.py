#!/usr/bin/env python3
"""Measure ARC console and NIL output on an unchanged packaged SDX demo."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics

from bitmap_console_performance import native_markers
from desktop_menu_check import Menus
from desktop_mouse import schedule
from measure_spartados_listing import prefill, spans
from native_program import read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run


class ConsoleOutput:
    def __init__(self, utilities, repeats):
        self.utilities, self.repeats = utilities, repeats
        self.rows = []

    def exercise(self, s):
        if s.manifest.get('desktop'):
            def move(x, y):
                s.saved['pointer'] = schedule(s.b, s.p, s.saved['pointer'], (x, y))
                s.frames(20)

            def click(x, y):
                move(x, y)
                s.b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(20)
                s.b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(40)

            s.saved['desktop_menu'] = {}
            Menus(s, click, move).select('Shell')
        s.b.mount(1, str(self.utilities))
        s.command('MOUNT D2: FORMAT SPARTA')
        before = s.ledger()
        s.b.profile_start('basicblock')
        for destination in ('console', 'NIL:'):
            text = 'D2:ARC.COM L SAMPLE.ARC' + (' >NIL:' if destination == 'NIL:' else '')
            for sample in range(self.repeats + 1):
                s.command('CLS')
                prefill(s, text)
                previous = s.number(s.saved['scope'] + 14)
                start = s.b.eval_expr('@clk')
                s.press('\n'); s.ready(previous); s.result()
                completed = s.b.eval_expr('@clk')
                screen = s.cells(text)
                settled = s.saved['settled_clock']
                if destination == 'console':
                    require(b'EXTRACT.TXT' in screen and b'EMPTY.TXT' in screen,
                            'ARC listing did not reach the console')
                require(s.ledger() == before, 'ARC retained Process/DOS ownership')
                row = dict(destination=destination, sample=sample,
                           temperature='first' if sample == 0 else 'warm',
                           start=start, completed=completed, settled=settled,
                           completion_ms=(completed-start)/BASE_HZ*1000,
                           visible_ms=(settled-start)/BASE_HZ*1000)
                self.rows.append(row)
                print('ARC output:', row, flush=True)
        s.b.profile_stop()
        s.command('UNMOUNT D2:')
        s.save_screen(s.p['output']/'boot-smoke.png')
        prefill(s, 'EXIT')
        s.b._cmd_ok('KEY RETURN down'); s.b.bp_clear_all()


def measure(bundle, utilities, output, repeats):
    require(repeats > 0, 'Need at least one warm repetition')
    output.mkdir(parents=True, exist_ok=True)
    copied = output/'bundle'
    require(not copied.exists(), 'Choose a fresh measurement directory')
    shutil.copytree(bundle, copied, symlinks=True,
                    ignore=shutil.ignore_patterns('emulator.log', 'altirra', 'extracted', 'pixels-*'))
    program = read_build(copied)
    require(program['build']['sdx_enabled'], 'The demo must enable SDX')
    markers = native_markers(program, [
        ('SDXPRINT_PRINT', 'printf'), ('SDXPRINT_CHARACTER', 'putc'),
        ('SDXPRINT_FLUSH', 'flush'), ('DOSCALLS_WRITE', 'write')])
    require(len(markers) == 4, 'Missing output measurement routines')
    pcs = {pc for routine in markers.values()
           for pc in [routine['entry'], *routine['returns']]}
    keys = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')
    previous = {key: os.environ.get(key) for key in keys}
    observer = ConsoleOutput(utilities, repeats)
    try:
        os.environ.update(EXEC816_LATENCY_TRACE='1',
                          EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs)))
        os.environ.pop('EXEC816_MASK_TRACE', None)
        result = run(copied, boot_smoke=True, integration=observer, profile_commands=False)
    finally:
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
    events = read_events(copied/'emulator.log')
    measured = spans(events, markers)
    require(measured, 'No CPU output observations; profiler history must be enabled')
    for row in observer.rows:
        # The trace normalizes wrapping 32-bit base clocks. Select the epoch
        # containing this physical Return and its settled output checkpoint.
        first = events[0][0]
        low = row['start'] + round((first-row['start'])/(1 << 32))*(1 << 32)
        high = low + row['settled']-row['start']
        inside = [r for r in measured if low <= r['begin'] <= r['end'] <= high]
        row['routines'] = {name: dict(calls=len(selected),
            elapsed_ms=sum(r['ms'] for r in selected))
            for name in markers if (selected := [r for r in inside if r['kind'] == name])}
    summary = {destination: dict(
        median_completion_ms=statistics.median(r['completion_ms'] for r in observer.rows
            if r['destination'] == destination and r['temperature'] == 'warm'),
        median_visible_ms=statistics.median(r['visible_ms'] for r in observer.rows
            if r['destination'] == destination and r['temperature'] == 'warm'))
        for destination in ('console', 'NIL:')}
    report = dict(status='pass', tier='development', qualification=False,
        scope='Pinned ARC listing with native interactive console or NIL output; '
              'warm cached files; physical Return and ordinary dispatch; '
              'routine times include preemption and must not be summed across nesting.',
        summary=summary, rows=observer.rows, markers=markers, runtime=result['runtime'],
        rom=result['rom'], machine=result['machine'],
        hashes=dict(xex=sha256(copied/'program.xex'), utilities=sha256(utilities),
                    manifest=sha256(copied/'demo-manifest.json'), observer=sha256(Path(__file__))))
    (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--utilities', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    measure(args.bundle.resolve(), args.utilities.resolve(), args.output.resolve(), args.repeats)
