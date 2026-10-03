#!/usr/bin/env python3
"""Record the three console responsiveness slices without relaxing targets."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, require, sha256


def visible_verdict(samples, limit=40):
    require(samples and any(s['includes_caret'] for s in samples),
            'Missing visible caret measurement')
    if any(s['last_incorrect_frame_ms'] is not None and
           s['last_incorrect_frame_ms'] > limit for s in samples):
        return 'fail'
    if all(s['first_correct_frame_upper_ms'] <= limit for s in samples):
        return 'pass'
    return 'unqualified'


def check_replay(observed, replay):
    require(observed['status'] == replay['status'] == 'pass', 'Failed workload or replay')
    require(observed['observed'] and not replay['observed'], 'Replay still has observers')
    require(observed['build']['xex_sha256'] == replay['build']['xex_sha256'],
            'Replay uses a different image')
    require(observed['pin'] == replay['pin'], 'Replay machine pin differs')
    if 'screen_sha256' in observed:
        require(observed['screen_sha256'] == replay['screen_sha256'], 'Replay pixels differ')
        require([(s['key'], s['phase_base_cycles']) for s in observed['scanout']] ==
                [(s['key'], s['phase_base_cycles']) for s in replay['scanout']],
                'Replay input phases differ')
    else:
        require(observed['observations'] == replay['observations'], 'Replay scenes differ')


def record(directory):
    artifacts = {}

    def read(relative):
        path = directory/relative
        value = json.loads(path.read_text())
        require(value['status'] == 'pass', 'Failed evidence: '+str(path))
        artifacts[str(path.relative_to(ROOT))] = dict(sha256=sha256(path),
            xex_sha256=value['build']['xex_sha256'], mode=value['mode'])
        return value

    baseline = read('s1-baseline/results.json')
    phases = [read(name+'/results.json') for name in ('s2-loaded', 's3-phase2', 's3-phase8')]
    for name, observed in zip(('s2-loaded', 's3-phase2', 's3-phase8'), phases):
        check_replay(observed, read(name+'/replay-results.json'))
    scroll = read('s3-scroll/results.json')
    check_replay(scroll, read('s3-scroll/results-replay.json'))
    for name in ('s2-text-raw', 's2-text-opt', 's2-fault-raw', 's2-fault-opt'):
        read(name+'/results.json')
    require(len({p['build']['xex_sha256'] for p in phases}) == 1,
            'Phase samples used different images')
    for value in [*phases, scroll]:
        require(value['build']['memory']['bank_zero_budget'] ==
                baseline['build']['memory']['bank_zero_budget'], 'Changed bank-zero budget')
        require(value['build']['memory']['task_pools'] ==
                baseline['build']['memory']['task_pools'], 'Changed Task pools')
        require(value['pin'] == baseline['pin'], 'Changed measurement pin')
        require(value['build']['revision'] == baseline['build']['revision'] and
                not value['build']['override'], 'Compiler changed or was overridden')
    measured = []
    for p, phase in zip(phases, (0, 3547, 14188)):
        require(all(s['phase_base_cycles'] == phase for s in p['scanout']),
                'Missing expected input phase')
        require(p['timing']['verdict'] == 'pass' and p['pointer']['losses'] == 0,
                'Coexistence failed')
        profile = p['turn_profile']
        measured.append(dict(phase_base_cycles=phase,
            scanout=[{k: s[k] for k in ('key', 'includes_caret',
                'first_correct_frame_upper_ms', 'last_incorrect_frame_ms')} for s in p['scanout']],
            visible_40ms=visible_verdict(p['scanout']),
            max_turn_charged_cpu_ms=profile['max_charged_cpu_ms'],
            max_text_charged_cpu_ms=profile['routines']['text']['charged_cpu_ms']['max'],
            max_turn_off_cpu_ms=profile['max_off_cpu_ms'],
            input_service_gap_max_ms=p['async_timing']['input_service_gap_max_ms'],
            launch_to_confirmed_idle_upper_ms=p['async_timing']['max_occupancy_upper_ms'],
            input=p['input_latency'], sio='pass', pointer='pass', replay='pass'))
    stages = {s['stage']: s for s in scroll['performance']['stages']}
    isolated = [t for n in (2, 3) for t in stages[n]['edit_through_final_chunk_ms']]
    repeated = stages[4]['edit_through_final_chunk_ms']
    for n in (2, 3, 7):
        calls = next(s['calls'] for s in scroll['operations'] if s['stage'] == n and s['kind'] == 'work')
        require(calls['GemDrawingScrollStart'] == 1 and calls.get('_text_record', 0) > 0,
                'Missing single scroll or native text observation')
        require(calls.get('_text_record', 0)+calls.get('blit_glyph', 0) <= 4,
                'Eligible scroll redrew glyphs')
    previous = baseline['turn_profile']
    source = ('platform/altirraos/vbxe.c', 'platform/altirraos/vbxe-map.s',
              'platform/altirraos/vbxe-internal.h', 'c/include/hardware/vbxe-upload.h',
              'ports/gem4xe/adapter/gem-vbxe.c', 'ports/gem4xe/hosted/hosted-dispatch.inc',
              'ports/gem4xe/patches/0005-hosted-text-run.patch',
              'tools/console_turn_profile.py', 'tools/measure_async_scroll.py',
              'tools/bitmap_console_trace.py', 'tools/test_console_bitmap_scroll.py',
              'tools/record_console_responsiveness.py')
    return dict(status='development-pass-performance-open', tier='development', slice='S3',
        artifacts=artifacts, source_inputs={p: sha256(ROOT/p) for p in source},
        machine=phases[0]['machine'], pin=phases[0]['pin'],
        compiler={k: phases[0]['build'][k] for k in ('revision', 'binary_sha256', 'override')},
        baseline=dict(max_turn_charged_cpu_ms=previous['max_charged_cpu_ms'],
            max_text_charged_cpu_ms=previous['routines']['text']['charged_cpu_ms']['max'],
            input_service_gap_max_ms=baseline['async_timing']['input_service_gap_max_ms'],
            visible_input_upper_ms=[s['first_correct_frame_upper_ms'] for s in baseline['scanout']]),
        phases=measured, scroll=dict(isolated_ms=isolated, repeated_ms=repeated,
            repaint_to_final_fence_ms=stages[13]['repaint_request_to_final_fence_ms'],
            exact_pixel_scenes=len(scroll['observations']), replay='pass'),
        acceptance=dict(functional='pass', coexistence='pass',
            turn_charge_4ms='pass' if all(p['max_turn_charged_cpu_ms'] <= 4 for p in measured) else 'fail',
            visible_input_40ms='fail' if any(p['visible_40ms'] == 'fail' for p in measured) else
                ('pass' if all(p['visible_40ms'] == 'pass' for p in measured) else 'unqualified'),
            scroll_20ms='pass' if all(t <= 20 for t in isolated+repeated) else 'fail',
            repaint_visible_500ms='unqualified', exact_busy_edges='unqualified'),
        bank_zero_delta=dict(fixed=0, root_kernel=0, per_task=[0]*8, idle=0),
        limits=['Charged CPU includes gateway/scheduling/return costs and bus stalls; native interrupt bodies and off-CPU time are separate.',
                'Three sampled input phases are not an exhaustive worst-case search.',
                'Launch to confirmed idle is an upper bound, not an exact BUSY edge.',
                'Repaint timing ends at its final drawing fence, not first visible scanout.',
                'No release qualification or demo refresh is claimed.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'build/console-responsiveness')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/development/console-responsiveness-s3.json')
    args = parser.parse_args()
    result = record(args.directory.resolve())
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'], result['acceptance'])
