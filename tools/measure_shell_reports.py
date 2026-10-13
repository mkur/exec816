#!/usr/bin/env python3
"""Measure resident report commands through a pinned standalone bitmap demo.

Prefill cooked input only at an idle prompt, then press physical Return. Passive
PC markers measure the real command and synchronous DOS Writes. No guest
counters or filesystem/cache edits are used. Pixel, ownership and EXIT checks
come from test_demo; use test_shell_reports for exact formatter byte checks.
"""
import argparse
import json
import shutil
import statistics
from pathlib import Path
from types import SimpleNamespace

from bitmap_console_performance import native_markers
import measure_spartados_listing as listing
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events

DEFAULT_COMMANDS = ('TASKS', 'MOUNT', 'DEVICES', 'JOBS', 'MEM', 'ALIAS', 'PATH', 'ECHO one two')
HEADERS = {'TASKS': b'SLOT STATE    NAME', 'MOUNT': b'MOUNT FILESYSTEM ACCESS',
           'DEVICES': b'DEVICE          STATE', 'JOBS': b'No background jobs',
           'MEM': b'ordinary total ', 'ALIAS': b'MKDIR -> MAKEDIR',
           'PATH': b'Current directory', 'ECHO one two': b'one two'}


def run(bundle, out, commands, samples):
    require(samples>0, 'Positive sample count required')
    require(all(command in HEADERS for command in commands), 'Unsupported report command')
    out.mkdir(parents=True, exist_ok=True)
    copied = out/'bundle'
    require(not copied.exists(), 'Choose a fresh measurement output')
    shutil.copytree(bundle, copied, symlinks=True,
                    ignore=shutil.ignore_patterns('emulator.log', 'pixels-*'))
    p = read_build(copied)
    definition = listing.markers(p)
    names = [('TASKINSPECT_SNAPSHOT', 'task_snapshot'), ('FSINSPECT_SNAPSHOT', 'mount_snapshot'),
             ('DEVICEINSPECT_SNAPSHOT', 'device_snapshot')]
    definition['routines'].update(native_markers(p, names))
    for name, routine in definition['routines'].items():
        definition['marks'][name+'_entry'] = routine['entry']
        for i, pc in enumerate(routine['returns']):
            definition['marks'][name+'_return_'+str(i)] = pc
    (out/'markers.json').write_text(json.dumps(definition, indent=2)+'\n')

    def exercise(c):
        ledger = c.ledger()
        measurements = []
        for command in commands:
            for nil in (False, True):
                for sample in range(samples):
                    listing.submit(c, 'CLS')
                    text = command+(' >NIL:' if nil else '')
                    start = c.b.eval_expr('@clk')
                    screen = listing.submit(c, text)
                    if not nil:
                        require(HEADERS[command] in screen, 'Missing report output: '+text)
                    require(c.ledger() == ledger, 'Report retained resources: '+text)
                    measurements.append(dict(command=text, sample=sample, input_clock=start,
                                             settled_clock=c.saved['settled_clock']))
        c.saved['measurements'] = measurements
        c.save_screen(c.p['output']/'boot-smoke.png')
        listing.prefill(c, 'EXIT')
        c.b._cmd_ok('KEY RETURN down')
        c.b.bp_clear_all()

    listing.observe(definition['marks'])
    record = listing.test_demo.run(copied, boot_smoke=True, measurement_commands=[],
                                  profile_commands=True, integration=SimpleNamespace(exercise=exercise))
    (out/'run.json').write_text(json.dumps(record, indent=2)+'\n')
    events = read_events(copied/'emulator.log')
    spans = listing.spans(events, definition['routines'])
    rows = []
    for sample in record['measurements']:
        windows = [w for w in spans if w['kind'] == 'command' and
                   listing.in_clock_window(w, sample['input_clock'], sample['settled_clock'])]
        require(len(windows) == 1, 'Missing command window')
        window = windows[0]
        inside = [s for s in spans if window['begin'] <= s['begin'] <= s['end'] <= window['end']]
        cpu = [(t, e) for t, e in events if window['begin'] <= t <= window['end'] and e[0] == 'cpu']
        writes = [s for s in inside if s['kind'] == 'write']
        row = dict(command=sample['command'], sample=sample['sample'], total_ms=window['ms'],
                   writes=len(writes), write_ms=sum(s['ms'] for s in writes),
                   first_write_ms=(min(s['begin'] for s in writes)-window['begin'])/BASE_HZ*1000,
                   kernel_calls=sum(int(e[4],16) == definition['marks']['gateway'] for _, e in cpu),
                   load_calls=sum(s['kind'] == 'load' for s in inside),
                   ata_commands=sum(int(e[4],16) == definition['marks'].get('ata_command') and
                                    int(e[6],16) == 23 for _, e in cpu))
        for name in ('task_snapshot', 'mount_snapshot', 'device_snapshot'):
            row[name+'_ms'] = sum(s['ms'] for s in inside if s['kind'] == name)
        require(row['load_calls'] == row['ata_commands'] == 0, 'Report performed loading or ATA commands')
        rows.append(row)
    summary = {}
    for command in dict.fromkeys(r['command'] for r in rows):
        selected = [r for r in rows if r['command'] == command]
        summary[command] = {key: statistics.median(r[key] for r in selected)
                            for key in selected[0] if key not in ('command', 'sample')}
        print(command, json.dumps(summary[command]), flush=True)
    return dict(status='pass', tier='development',
                scope='Optimized standalone bitmap console; console/NIL output, passive markers, '
                      'physical Return, independent pixels, ownership, guards and EXIT restoration.',
                summary=summary, rows=rows, runtime=record['runtime'], machine=record['machine'],
                rom=record['rom'], observer_sha256=sha256(Path(__file__)),
                input_hashes=dict(xex=sha256(copied/'program.xex'),
                                  manifest=sha256(copied/'demo-manifest.json'),
                                  trace=sha256(copied/'emulator.log')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--command', action='append')
    parser.add_argument('--samples', type=int, default=3)
    args = parser.parse_args()
    result = run(args.bundle.resolve(), args.output.resolve(), args.command or DEFAULT_COMMANDS, args.samples)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
