#!/usr/bin/env python3
"""Passively split physical display ownership into C, assembly and Action costs.

Replay an existing optimized display-borrow fixture without changing guest bytes.
Nested entry/caller-return boundaries include the return instruction, match full
native S and D, and separate Task CPU from interrupts and off-Task time.
"""
import argparse
from bisect import bisect_left
import json
from pathlib import Path
import re
import statistics
from unittest.mock import patch

from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls, listing_returns
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import read_events


OPERATIONS = {
    'DisplayEnter': ('DISPLAY_ENTER', 'AESPROBE_CDISPLAYENTER'),
    'DisplayLeave': ('DISPLAY_LEAVE', 'AESPROBE_CDISPLAYLEAVE'),
    'DisplayOwnerEnter': ('DISPLAY_OWNERENTER', None),
    'DisplayOwnerEnd': ('DISPLAY_OWNEREND', 'AESPROBE_CDISPLAYOWNEREND'),
}
LAYERS = ('c_binding', 'assembly_bridge', 'action_wrapper', 'native_ownership')
METRICS = ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')


def definitions(program, foreign, directory):
    names = [name for pair in OPERATIONS.values() for name in pair if name]
    native = native_markers(program, [(name, name) for name in names])
    require(set(native) == set(names), 'Missing ownership routine')
    entries = {foreign['symbols'][name]: name for name in (*OPERATIONS, '_DisplayCall')}
    entries.update({span['entry']: name for name, span in native.items()})
    returns = set(listing_returns(foreign, directory/'drawing'))
    # The assembly dispatcher synthesizes an RTL into the selected Action entry.
    # Its return is the successor of this real JSL, shared by all table entries.
    ready = foreign['symbols']['display_ready']
    segment = next(s for s in foreign['segments']
                   if s['address'] <= ready < s['address']+len(s['bytes']))
    at = ready-segment['address']
    require(bytes(segment['bytes'][at:at+4]) ==
            bytes([0x22])+foreign['symbols']['display_dispatch'].to_bytes(3, 'little'),
            'Display dispatcher changed')
    returns.add(ready+4)
    # Get Action caller-return sites from decoded instructions, not byte scans.
    decoder = {'__name__': 'display_bridge_decoder'}
    source = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(source.read_text(), str(source), 'exec'), decoder)
    image = program['image']
    for routine in image['routines']:
        if routine['address'] not in {span['entry'] for span in native.values()}:
            continue
        segments = []
        for segment in image['segments']:
            lo = max(segment['address'], routine['address'])
            hi = min(segment['address']+len(segment['bytes']), routine['address']+routine['size'])
            if lo < hi:
                segments.append(dict(address=lo, executable=True,
                    bytes=segment['bytes'][lo-segment['address']:hi-segment['address']]))
        listing = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
        returns.update(int(match[1], 16)+4 for match in
                       re.finditer(r'^([0-9A-F]{6}) .* JSL ', listing, re.M))
    return dict(entries=entries, returns=sorted(returns),
                points={name: program['labels']['tasks_'+name]
                        for name in ('wait', 'signal', 'forbid', 'permit')})


def split_costs(public, assembly, wrapper, native):
    """Exclusive costs of properly nested full calls; all values use one timeline."""
    result = {}
    for metric in METRICS:
        values = (public[metric]-assembly[metric], assembly[metric]-wrapper[metric],
                  wrapper[metric]-native[metric], native[metric])
        require(all(value >= -1e-8 for value in values), 'Ownership spans are not nested')
        for name, value in zip(LAYERS, values):
            result.setdefault(name, {})[metric] = max(0, value)
        require(abs(sum(values)-public[metric]) < 1e-8, 'Ownership partition mismatch')
    return result


def summarize(rows):
    result = dict(count=len(rows))
    if not rows:
        return result
    for scope in ('total', 'bridge', *LAYERS):
        result[scope] = {}
        for metric in METRICS:
            values = sorted(row[scope][metric] for row in rows)
            result[scope][metric] = dict(mean=statistics.mean(values),
                median=statistics.median(values), minimum=values[0], maximum=values[-1])
    return result


def pair_costs(rows):
    """Sum admission/release only; do not count the drawing between them."""
    active, pairs = {}, []
    for row in sorted(rows, key=lambda r: r['start']):
        if row['kind'] == 'DisplayEnter' and row['status'] == 0:
            require(row['dp'] not in active, 'Repeated successful drawing admission')
            active[row['dp']] = row
        elif row['kind'] == 'DisplayLeave' and row['status'] == 0:
            require(row['dp'] in active, 'Release without successful admission')
            enter = active.pop(row['dp'])
            pairs.append(dict(uncontended_no_wake=not (
                enter['kernel_calls']['wait'] or row['kernel_calls']['signal']),
                **{scope: {metric: enter[scope][metric]+row[scope][metric]
                           for metric in METRICS} for scope in ('total', 'bridge', *LAYERS)}))
    require(not active, 'Unreleased drawing admission')
    return dict(all=summarize(pairs),
                uncontended_no_wake=summarize([p for p in pairs if p['uncontended_no_wake']]))


def analyze(events, timeline_definition, definition):
    profile = analyze_events(events, timeline_definition, include_segments=True)
    entries = {int(pc): name for pc, name in definition['entries'].items()}
    returns = set(definition['returns'])
    points = {name: {} for name in definition['points']}
    for tick, event in events:
        if event[0] != 'cpu':
            continue
        pc, dp = int(event[4], 16), int(event[9], 16)
        for name, address in definition['points'].items():
            if pc == address:
                points[name].setdefault(dp, []).append(tick)
    rows = []
    for dp in timeline_definition['task_dps']:
        spans, unfinished = calls(events, entries, returns, dp)
        require(not [s for s in unfinished if s['kind'] in (*OPERATIONS, '_DisplayCall')],
                'Incomplete C ownership call')
        spans.sort(key=lambda s: s['start'])
        starts = [s['start'] for s in spans]
        timeline = Timeline(profile['segments'], dp)
        for public in spans:
            if public['kind'] not in OPERATIONS:
                continue
            nested = spans[bisect_left(starts, public['start']):bisect_left(starts, public['end'])]
            def one(kind):
                found = [s for s in nested if s['kind'] == kind and s['end'] <= public['end']]
                require(len(found) == 1, 'Expected one '+kind+' in '+public['kind'])
                return found[0]
            native_name, wrapper_name = OPERATIONS[public['kind']]
            assembly, native = one('_DisplayCall'), one(native_name)
            wrapper = one(wrapper_name) if wrapper_name else native
            boundaries = (public, assembly, wrapper, native)
            require(all(a['start'] <= b['start'] < b['end'] <= a['end']
                        for a, b in zip(boundaries, boundaries[1:])), 'Crossed bridge boundary')
            measured = [timeline.measure(s['start'], s['end']) for s in boundaries]
            layers = split_costs(*measured)
            counts = {}
            for name, by_dp in points.items():
                ticks = by_dp.get(dp, [])
                counts[name] = bisect_left(ticks, native['end'])-bisect_left(ticks, native['start'])
            rows.append(dict(kind=public['kind'], dp=dp, start=public['start'], end=public['end'],
                status=public['return_a'], kernel_calls=counts, total=measured[0], **layers,
                bridge={metric: sum(layers[layer][metric] for layer in LAYERS[:-1])
                        for metric in METRICS}))
    groups = {}
    for name in OPERATIONS:
        selected = [r for r in rows if r['kind'] == name]
        good = [r for r in selected if r['status'] == 0]
        groups[name] = dict(all=summarize(selected), success=summarize(good),
            failed=summarize([r for r in selected if r['status'] != 0]))
        if name == 'DisplayEnter':
            groups[name]['uncontended'] = summarize([r for r in good if not r['kernel_calls']['wait']])
            groups[name]['waited'] = summarize([r for r in good if r['kernel_calls']['wait']])
        if name in ('DisplayLeave', 'DisplayOwnerEnd'):
            groups[name]['no_wake'] = summarize([r for r in good if not r['kernel_calls']['signal']])
            groups[name]['wake'] = summarize([r for r in good if r['kernel_calls']['signal']])
        if name == 'DisplayOwnerEnter':
            groups[name]['no_delegates'] = summarize([r for r in good if not r['kernel_calls']['forbid']])
            groups[name]['delegated'] = summarize([r for r in good if r['kernel_calls']['forbid']])
    require(groups['DisplayEnter']['success']['count'] == 48, 'Expected 48 drawing acquisitions')
    require(groups['DisplayEnter']['uncontended']['count'] > 0, 'No uncontended sample')
    require(groups['DisplayLeave']['success']['count'] == 48, 'Expected 48 drawing releases')
    return dict(groups=groups, pairs=pair_costs(rows), calls=rows)


def run(directory, out, replay=False):
    import test_aes_server
    import test_display_borrow
    directory, out = directory.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    program = read_build(directory/'program')
    foreign = json.loads((directory/'c-image.json').read_text())
    require(program['build']['optimize'], 'Measure optimized native code')
    require('-O2' in foreign['provenance']['compiler_flags'], 'Measure optimized C code')
    recorded_sources = {**program['build']['task_inputs'], **foreign['provenance']['source_inputs']}
    for name in ('c/calypsi/display.c', 'c/calypsi/display.s',
                 'lib/display/display-access.inc', 'tests/programs/display_borrow.c'):
        require(recorded_sources[name] == sha256(ROOT/name), 'Stale ownership fixture: '+name)
    definition = definitions(program, foreign, directory)
    original_setup = test_display_borrow.trace_setup

    def setup(program, foreign, output):
        import os
        timeline, spans, saved = original_setup(program, foreign, output)
        pcs = set(definition['entries']) | set(definition['returns']) | set(definition['points'].values())
        os.environ['EXEC816_LATENCY_PCS'] += ','+','.join(f'{pc:x}' for pc in sorted(pcs))
        (out/'bridge-definition.json').write_text(json.dumps(
            dict(timeline=timeline, bridge=definition), indent=2)+'\n')
        return timeline, spans, saved

    if not replay:
        with patch.object(test_display_borrow, 'trace_setup', setup):
            test_aes_server.applications(out, 'display', from_build=directory)
    fixture = json.loads((out/'results.json').read_text())
    require(fixture['status'] == 'pass', 'Mixed-renderer check failed')
    saved = json.loads((out/'bridge-definition.json').read_text())
    result = analyze(read_events(out/'emulator.log'), saved['timeline'], saved['bridge'])
    from test_mouse_observe import BRIDGE, ROM
    result.update(status='pass', tier='development', qualification=False, scope=__doc__,
        guest_changes=False, from_build=str(directory.relative_to(ROOT)),
        actionc_revision=program['build']['revision'],
        c_toolchain=foreign['provenance']['tools'], machine=fixture['machine'],
        runtime=fixture['runtime'], assertions=fixture['AESChecks'],
        borrowed_renderer=fixture['borrowed_renderer'],
        hashes={name: sha256(path) for name, path in {
            'native_image': directory/'program/program.a816.json',
            'c_image': directory/'c-image.json', 'xex': directory/'program/program.xex',
            'definition': out/'bridge-definition.json', 'trace': out/'emulator.log',
            'analyzer': Path(__file__), 'emulator': BRIDGE/'AltirraBridgeServer', 'rom': ROM}.items()},
        source_inputs={name: sha256(ROOT/name) for name in (
            'c/calypsi/display.c', 'c/calypsi/display.s', 'c/calypsi/display-bridge.inc',
            'lib/display/display-access.inc', 'tests/programs/display_borrow.c')},
        reserved_bank_zero_delta=dict(fixed=0, per_public_task=[0]*8, idle=0),
        limits=[
            'Instrumented mixed-renderer fixture, not GUI operation or input latency.',
            'Guest entry to caller return includes RTL but excludes the outer caller JSL and argument preparation.',
            'Bridge overhead is nested subtraction on the same call, not subtraction of different runs.',
            'Charged CPU excludes native interrupts and time running another Task.',
            'Waited, failed and wake-producing calls are separated from successful uncontended acquisition.',
            'Eight bridge pairs per dialog is a CPU projection; scheduling and whole-dialog latency are not measured.',
        ])
    (out/'bridge-cost.json').write_text(json.dumps(result, indent=2)+'\n')
    for name, group in result['groups'].items():
        row = group.get('uncontended', group['success'])
        print(name, row['count'], 'calls;', ', '.join(
            f"{scope} {row[scope]['charged_cpu_ms']['mean']*1000:.3f} us"
            for scope in ('total', 'bridge', *LAYERS)), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', action='store_true', help='Reanalyze an existing capture')
    args = parser.parse_args()
    run(args.from_build, args.output, args.replay)
