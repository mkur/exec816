#!/usr/bin/env python3
"""Measure final console input drains against the saved CB4 single-key baseline."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import console_turn_profile
from console_turn_profile import markers as console_markers
from bitmap_console_performance import native_markers
from input_registration_checks import audit_paths
from measure_async_scroll import run
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import read_events

DETAILS = [('CONSOLEINPUT_PUMP', 'key_pump'), ('INPUT_TAKE', 'key_take'),
    ('INPUT_EXTENT', 'key_extent'), ('TASKMEMORY_WRITABLE', 'key_writable'),
    ('INPUT_VALID', 'key_valid'), ('INPUT_SHARED', 'key_shared'),
    ('INPUT_CAPTURE', 'key_capture_state'), ('INPUT_SOURCEOF', 'key_source'),
    ('CONSOLEFOREGROUND_RESOLVE', 'key_resolve'),
    ('CONSOLEINPUT_DELIVER', 'key_deliver'), ('CONSOLEINPUT_DECODE', 'key_decode')]
AUDITS = ('key_extent', 'key_writable', 'key_valid', 'key_find_task')


def add_details(definition, extra, labels):
    # Audit helper symbols may disappear as linking improves. Public drain
    # boundaries are mandatory so that absence cannot become a zero-cost claim.
    require(all(name in extra for name in ('key_pump', 'key_take')),
            'Missing public input drain boundaries')
    definition['spans'].update(extra)
    definition['spans']['key_find_task'] = dict(entry=labels['tasks_find_task'],
        returns=[labels['tasks_find_task_end']-1])
    return definition


def markers(program, foreign, output):
    return add_details(console_markers(program, foreign, output),
                       native_markers(program, DETAILS), program['labels'])


def drains(spans, captures):
    """Associate a capture with a successful Take, never with a cost threshold."""
    result = []
    services = sorted((s for s in spans if s['kind'] == 'input'), key=lambda s: s['start'])
    takes = [s for s in spans if s['kind'] == 'key_take']
    require(len(captures) == 4, 'Expected Z, A, Return and BREAK captures')
    for index, (key, capture) in enumerate(zip(('Z', 'A', 'Return', 'BREAK'), captures)):
        limit = captures[index+1] if index+1 < len(captures) else float('inf')
        matches = [s for s in services if any(
            s['start'] <= t['start'] < t['end'] <= s['end'] and
            capture <= t['end'] < limit and t['return_a'] & 65535 == 0 for t in takes)]
        require(matches, 'No successful input drain for '+key)
        service = matches[0]
        children = [s for s in spans if service['start'] <= s['start'] < s['end'] <= service['end']]
        selected = [s for s in children if s['kind'] == 'key_take']
        audit_count = sum(s['kind'] in AUDITS for s in children)
        require(audit_count == 0, 'Production input service reached an authority audit')
        result.append(dict(key=key, capture=capture, service=service,
            take_calls=len(selected), take_results=[s['return_a'] & 65535 for s in selected],
            audit_calls=audit_count, parts={kind: dict(calls=len(items),
                charged_cpu_ms=sum(s['charged_cpu_ms'] for s in items))
                for kind in sorted({s['kind'] for s in children if s['kind'].startswith('key_')})
                if (items := [s for s in children if s['kind'] == kind])}))
    return result


def verify_baseline(output, result, baseline):
    for item in baseline['sources'].values():
        require(sha256(ROOT/item['path']) == item['sha256'], 'Changed saved baseline '+item['path'])
    for name in ('rom', 'emulator'):
        item = baseline[name]
        require(sha256(ROOT/item['path']) == item['sha256'], 'Changed '+name)
    for key, value in baseline['compiler'].items():
        require(result['build'][key] == value, 'Unmatched compiler '+key)
    phase = result['scanout'][0]['phase_base_cycles']
    saved = json.loads((ROOT/baseline['sources']['existing_console_evidence']['path']).read_text())
    item = next(row['after']['result'] for row in saved['loaded'] if row['phase_base_cycles'] == phase)
    path = ROOT/item['path']
    require(sha256(path) == item['sha256'], 'Changed saved loaded result')
    old = json.loads(path.read_text())
    for key in ('pin', 'machine', 'media_sha256'):
        require(result[key] == old[key], 'Unmatched workload '+key)
    # Only output directories differ. This also checks the unchanged physical
    # input schedule and observer hooks, without depending on a replay's file.
    harness = path.parent/'wide-fairness.py'
    require(sha256(harness) == old['benchmark_harness_sha256'], 'Changed saved harness')
    relocated = harness.read_text().replace(str(path.parent), str(output))
    require(hashlib.sha256(relocated.encode()).hexdigest() == result['benchmark_harness_sha256'],
            'Unmatched loaded harness')
    sources = lambda r: {Path(p).name: digest for p, digest in r['source_inputs'].items()}
    require(sources(old) == sources(result), 'Unmatched workload sources')
    return dict(saved_hashes_verified=True, phase=phase, compiler_and_actual_binaries_match=True,
        machine_pin_media_and_workload_match=True, harness_difference='output paths only',
        service_before_after_available=phase == 0)


def analyze(output):
    result = json.loads((output/'results.json').read_text())
    baseline = json.loads((ROOT/'docs/development/input-registration-baseline.json').read_text())
    comparison = verify_baseline(output, result, baseline)
    profile = result['turn_profile']
    trace = output/'observed-trace.log'
    captures = [tick for tick, event in read_events(trace)
                if event[0] == 'cpu' and int(event[4], 16) == result['marks']['input_capture']]
    rows = drains(profile['routine_spans'], captures)
    old = {row['key']: row['service_cpu_ms'] for row in baseline['profile']['keys']}
    for row in rows:
        if comparison['service_before_after_available'] and row['key'] in old:
            row['baseline_service_cpu_ms'] = old[row['key']]
            row['service_cpu_reduction_percent'] = 100*(1-row['service']['charged_cpu_ms']/old[row['key']])
    target = all(row['service']['charged_cpu_ms'] <= 2 and row['take_results'] == [0, 1]
                 for row in rows[:3])
    program = read_build(output/'program')
    require(not program['build']['input_diagnostics'], 'Timing a diagnostic build')
    report = dict(status='pass', tier='development', qualification=False,
        scope=console_turn_profile.__doc__, xex_sha256=sha256(program['xex']),
        trace_sha256=sha256(trace), phase=result['scanout'][0]['phase_base_cycles'],
        baseline_comparison=comparison, audit_paths=audit_paths(program), keys=rows, target_single_key_2ms=target,
        max_worker_cpu_ms=profile['max_charged_cpu_ms'], max_turn_elapsed_ms=profile['max_elapsed_ms'],
        max_off_cpu_ms=profile['max_off_cpu_ms'], global_interrupt_ms=profile['global_interrupt_ms'],
        forbid=result['timing']['forbid'], forbid_scope=result['timing']['forbid_scope'],
        scanout=result['scanout'], mouse_timing=result['mouse_timing'],
        serial_verdict=result['timing']['verdict'], serial_violations=result['timing']['violations'])
    (output/'input-service.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Input service', [(r['key'], round(r['service']['charged_cpu_ms'], 3)) for r in rows],
          '2 ms target:', target, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', type=int, choices=(0, 3547, 14188), default=0)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if not args.analyze_only:
        with patch.object(console_turn_profile, 'markers', markers):
            run(output, args.phase, reuse=args.reuse, profile_turns=True)
    analyze(output)
