#!/usr/bin/env python3
"""Passive operation costs on unchanged emitted C, keyboard and pointer fixtures."""
import argparse
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import re
import shutil
from unittest.mock import patch

import adapter_state as adapter
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, flat_markers
from input_registration_checks import audit_paths
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import read_events


def assembly_markers(program, names):
    """Read ca65 instruction boundaries; the compiler decoder covers only its IR."""
    listing = (program['output']/'hosted.lst').read_text()
    result = {}
    for name in names:
        matches = list(re.finditer(r'^([0-9A-F]{6})r?\s+\d+\s+'+name+r':\s*$', listing, re.M))
        ends = list(re.finditer(r'^([0-9A-F]{6})r?\s+\d+\s+'+name+r'_end:\s*$', listing, re.M))
        require(len(matches) == len(ends) == 1, 'Missing assembly boundaries '+name)
        start, end = matches[0], ends[0]
        address = program['labels'][name]
        offset = address-int(start[1], 16)
        require(offset+int(end[1], 16) == program['labels'][name+'_end'], 'Listing extent mismatch')
        returns = [offset+int(m[1], 16) for m in re.finditer(
            r'^([0-9A-F]{6})r?\s+\d+\s+6B\s+rtl\s*$', listing[start.end():end.start()], re.M)]
        require(returns, 'Missing assembly RTL '+name)
        for pc in returns:
            require(any(s['address'] <= pc < s['address']+len(s['bytes']) and
                        s['bytes'][pc-s['address']] == 0x6b for s in program['image']['segments']),
                    'Listing RTL disagrees with image')
        result['raw_'+name] = dict(entry=address, returns=returns)
    return result


def markers(program):
    names = [('INPUT_TAKE', 'take'), ('INPUT_PENDING', 'pending'),
        ('INPUT_SOURCEOF', 'source'), ('INPUT_EXTENT', 'extent'),
        ('INPUT_VALID', 'valid'), ('TASKMEMORY_WRITABLE', 'writable'),
        ('INPUTABI_CINPUTTAKE', 'c_take'), ('INPUTABI_CINPUTPENDING', 'c_pending'),
        ('INPUTTEST_RECORDS', 'seeded_keyboard')]
    spans = native_markers(program, names)
    spans.update(assembly_markers(program, ('input_take', 'input_take_break', 'pointer_take')))
    # All benchmark Take calls belong to the fixture's owning Task. Reuse the
    # existing timeline partitioner, with successive Take entries as boundaries;
    # only individual routine spans are reported, not these artificial turns.
    points = {n: program['labels'][n] for n in ('native_irq', 'native_nmi', 'interrupt_schedule')}
    restore = program['labels']['context_restore']
    code = (program['output']/'hosted.bin').read_bytes()
    require(code[restore-adapter.RESIDENT_BASE:restore-adapter.RESIDENT_BASE+8] == bytes.fromhex('c230ab2b7afa6840'),
            'Unknown context restore')
    points.update(turn=spans['take']['entry'], selected=restore+4, worker_retire=program['labels']['done'])
    return dict(spans=spans, points=points,
        task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])


def operation_rows(spans):
    result = []
    for row in spans:
        if row['kind'] not in ('take', 'pending', 'c_take', 'c_pending'):
            continue
        children = [s for s in spans if row['start'] <= s['start'] < s['end'] <= row['end']]
        sources = [s['return_a'] & 65535 for s in children if s['kind'] == 'source']
        source = {2: 'keyboard', 3: 'pointer'}.get(sources[-1] if sources else 0, 'unresolved')
        status = row['return_a'] & 65535
        kind = 'pending' if row['kind'].endswith('pending') else 'empty' if status == 1 else 'rejected'
        if row['kind'].endswith('take') and status == 0:
            kind = 'event'
            if any(s['kind'] == 'raw_input_take_break' and s['return_a'] for s in children):
                kind = 'cancel'
            elif any(s['kind'] == 'raw_input_take' and s['return_a'] == 65534 and
                     s['return_x'] == 65535 for s in children):
                kind = 'loss'
            elif source == 'keyboard':
                kind = 'key'
            elif any(s['kind'] == 'raw_pointer_take' and s['return_a'] == 2 for s in children):
                kind = 'loss'
        require(not any(s['kind'] in ('extent', 'valid', 'writable') for s in children),
                'Ordinary operation reached a full audit')
        seeded = any(s['kind'] == 'seeded_keyboard' and s['start'] <= row['start'] and
                     row['end'] <= s['end'] for s in spans)
        result.append(dict(**row, source=source, status=status, outcome=kind,
                           keyboard_fixture='seeded burst/loss/cancel' if seeded else 'other'))
    return result


def run(output, fixture, source):
    output.mkdir(parents=True, exist_ok=True)
    require(not (output/'program').exists(), 'Choose a fresh measurement output')
    shutil.copytree(source/'program', output/'program')
    if fixture == 'c':
        shutil.copyfile(source/'c-image.json', output/'c-image.json')
    program = read_build(output/'program')
    require(program['build']['optimize'] and not program['build']['input_diagnostics'],
            'Expected optimized production fixture')
    before = sha256(program['xex'])
    definition = markers(program)
    module = importlib.import_module({'c': 'test_input', 'keyboard': 'test_input_capture',
                                     'pointer': 'test_pointer_failures'}[fixture])
    original_emulator, original_execute = module.emulator, module.execute

    @contextmanager
    def observed(*args, **kwargs):
        setting = dict(EXEC816_LATENCY_TRACE='1', EXEC816_LATENCY_PCS=','.join(
            f'{pc:x}' for pc in flat_markers(definition).values()))
        with patch.dict(os.environ, setting), original_emulator(*args, **kwargs) as bridge:
            yield bridge

    def execute(bridge, *args, **kwargs):
        before_run = kwargs.get('before_run')
        def start(b):
            b.profile_start()
            if before_run:
                before_run(b)
        kwargs['before_run'] = start
        try:
            return original_execute(bridge, *args, **kwargs)
        finally:
            bridge.profile_stop()

    with patch.object(module, 'emulator', observed), patch.object(module, 'execute', execute):
        module.run(output, 'opt', replay=True)
    require(sha256(program['xex']) == before == sha256(source/'program/program.xex'),
            'Observed fixture image changed')
    trace = output/'emulator.log'
    profile = analyze_events(read_events(trace), definition)
    rows = operation_rows(profile['routine_spans'])
    groups = {}
    for row in rows:
        key = '/'.join((row['kind'], row['source'], row['outcome'], row['keyboard_fixture']))
        groups.setdefault(key, []).append(row)
    report = dict(status='pass', tier='development', qualification=False, fixture=fixture,
        scope='Entry to RTL; charged CPU includes gateway/scheduling tails and bus stalls, excluding native interrupt bodies and off-Task time. Nested native/C calls are not additive. No C baseline exists.',
        xex_sha256=before, trace_sha256=sha256(trace), audit_paths=audit_paths(program),
        groups={key: dict(calls=len(values), **{field: dict(min=min(r[field] for r in values),
            max=max(r[field] for r in values), mean=sum(r[field] for r in values)/len(values))
            for field in ('charged_cpu_ms', 'elapsed_ms', 'off_cpu_ms', 'interrupt_ms')})
            for key, values in groups.items()}, operations=rows)
    (output/'operation-costs.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Input operation costs', fixture, len(rows), 'calls', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixture', choices=('c', 'keyboard', 'pointer'), required=True)
    parser.add_argument('--from-build', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.fixture, args.from_build.resolve())
