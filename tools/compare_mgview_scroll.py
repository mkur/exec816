#!/usr/bin/env python3
"""Compare two frozen MGVIEW captures without rebuilding or rerunning guests."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from console_turn_profile import Timeline, analyze_events
from native_program import require, sha256
from sio_transaction_trace import BASE_HZ, read_events


def api_calls(sample):
    """Pair emitted APP call/return sites, excluding other Tasks' observations."""
    pending = defaultdict(list)
    calls = defaultdict(list)
    for row in sample['boundaries']:
        if row['dp'] != sample['viewer_dp']:
            continue
        name, separator, edge = row['name'].rpartition('/')
        if not separator or edge not in ('call', 'returned'):
            continue
        if edge == 'call':
            pending[name].append(row['ms'])
        elif pending[name]:
            calls[name].append((pending[name].pop(), row['ms']))
    return calls


def metrics(path):
    record = json.loads(path.read_text())
    require(record['status'] == 'pass' and record['runtime']['status'] == 0
            and record['runtime']['guards'] == 'intact', 'Incomplete capture: '+str(path))
    require(record['base_clock_hz'] == BASE_HZ, 'Different trace clock')
    definition = json.loads((path.parent/'definition.json').read_text())
    events = read_events(path.parent/'emulator.log', kinds={'cpu'})
    interrupts = {definition['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in interrupts:
        events.pop()
    profile = analyze_events(events, definition['timeline'], include_segments=True)
    rows = {}
    for sample in record['audit']['samples']:
        clock = Timeline(profile['segments'], sample['viewer_dp'])
        calls = api_calls(sample)
        mouse = calls['set_shift/graf_mouse']
        setters = calls['window_calc_slider/wind_set']
        require(len(mouse) == len(setters) == 2, 'Missing mouse/slider call brackets')
        stages = {}
        for name, intervals in (
                ('begin', calls['set_shift/ExecAESBeginUpdate']),
                ('setters', setters), ('hide', mouse[:1]), ('show', mouse[1:]),
                ('end', calls['set_shift/wind_update'])):
            require(intervals, 'Missing API stage: '+name)
            measured = [clock.measure(sample['start']+start*BASE_HZ/1000,
                                      sample['start']+end*BASE_HZ/1000)
                        for start, end in intervals]
            stages[name] = dict(calls=len(intervals), **{key: sum(v[key] for v in measured)
                for key in ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')})
        for name, kind in (('copy', 'vro_cpyfm'), ('row', '_my_draw'), ('shift', 'set_shift'),
                           ('slider_helper', 'window_calc_slider')):
            selected = [s for s in sample['spans'] if s['kind'] == kind]
            require(len(selected) == 1, 'Missing unique stage: '+kind)
            stages[name] = {key: selected[0][key] for key in
                ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')}
        resident = next(s for s in sample['spans'] if s['kind'] == 'ExecAESBeginUpdate')
        begin = calls['set_shift/ExecAESBeginUpdate']
        require(len(begin) == 1 and
                sample['start']+begin[0][0]*BASE_HZ/1000 <= resident['start']+.01 and
                resident['end'] <= sample['start']+begin[0][1]*BASE_HZ/1000+.01,
                'APP bracket does not enclose resident BEGIN')
        presenter = next(s for s in record['presenter']['samples']
                         if s['action'] == sample['action'])
        scopes = {}
        for name, scope in presenter['windows'].items():
            scopes[name] = dict(cpu_ms=scope['measured']['charged_cpu_ms'],
                turns=len(scope['turns']), decoded_presenter_posts=scope['presenter_signal_counts'],
                all_native_signal_sites=dict(Counter(s['caller'] for s in scope['signals'])),
                undecoded_signal_sites=dict(Counter(s['caller'] for s in scope['signals']
                                                    if s['arguments'] is None)))
        require(len(sample['owned_copy_completions']) == 1, 'Copy-unit count changed')
        rows[sample['action']] = dict(offered_to_pixels_upper_ms=sample['offered_to_complete_ms'],
            pixels_bracket_ms=sample['complete_bracket_ms'], stages=stages,
            viewer_to_pixels=sample['cpu_to_complete'], presenter=scopes,
            pixel_sha256=sample['pixel_sha256'], copy_units=1)
    return record, rows


def compare(before, after, output):
    old, a = metrics(before)
    new, b = metrics(after)
    for field in ('machine', 'app_sha256', 'app_abi', 'aes_abi', 'document_sha256',
                  'work', 'pointer_start', 'pointer_end', 'rom_sha256', 'emulator_sha256',
                  'base_clock_hz'):
        require(old[field] == new[field], 'Unmatched capture input: '+field)
    require(set(a) == set(b) == {'down', 'up'}, 'Incomplete down/up pair')
    for action in a:
        require(a[action]['pixel_sha256'] == b[action]['pixel_sha256'], 'Different final pixels')
    result = dict(status='pass', tier='development', qualification=False,
        captures={name: dict(path=str(path), sha256=sha256(path))
                  for name, path in (('before', before), ('after', after))},
        app_sha256=new['app_sha256'], before=a, after=b,
        counter_progress=dict(before=old['counter_progress'], after=new['counter_progress']),
        scope='Two actions, not a distribution. PAL pixel matches are upper bounds. '
              'CPU includes gateways/bus stalls; other Tasks and IRQ/NMI are separate. '
              'Undecoded native signal sites are reported by caller, not guessed as decoded wakes.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.before.resolve(), args.after.resolve(), args.output.resolve())
    for action in ('down', 'up'):
        print(action, round(report['before'][action]['offered_to_pixels_upper_ms'], 2),
              '->', round(report['after'][action]['offered_to_pixels_upper_ms'], 2), 'ms')
