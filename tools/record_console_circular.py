#!/usr/bin/env python3
"""Record the circular console comparison using preserved BI5 measurements.

This only reads saved observations and replays; it never runs the old image.
"""
import json
from pathlib import Path

from native_program import ROOT, require, sha256


def read(path):
    return json.loads(path.read_text())


def reference(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=sha256(path))


def checked(path):
    result = read(path)
    require(result['status'] == 'pass', 'Failed measurement: '+str(path))
    return result


def runtime(result):
    return {k: result[k] for k in ('status', 'guards', 'stack_observations',
            'kernel_stack_observation', 'native_nmi_count', 'native_irq_count')}


def image(result):
    return {k: result['build'][k] for k in ('revision', 'override',
            'xex_sha256', 'image_sha256', 'memory_sha256') if k in result['build']}


def isolated(path):
    result = checked(path/'results.json')
    replay = checked(path/'results-replay.json')
    require(image(result) == image(replay), 'Changed isolated replay image')
    stages = result['performance']['stages']
    return dict(result=reference(path/'results.json'),
        replay=reference(path/'results-replay.json'), build=image(result),
        observed_log=reference(path/'observed-emulator.log'),
        runtime=runtime(result['runtime']), stack_usage=result['stack_usage'],
        stages=[dict(stage=s['stage'],
            routines={k: v for k, v in s['routines'].items()
                      if k in ('cells', 'present', 'edit')},
            **{k: s[k] for k in ('edit_through_final_chunk_ms',
               'repaint_request_to_final_fence_ms') if k in s})
            for s in stages if s['stage'] in (1, 2, 3, 4, 11, 13)],
        completion=result['completion_timing'],
        pixels=[o for o in result['observations']], pin=result['pin'],
        machine=result['machine'])


def loaded(path):
    result = checked(path/'results.json')
    replay = checked(path/'replay-results.json')
    require(image(result) == image(replay), 'Changed loaded replay image')
    routines = result['turn_profile']['routines']
    costs = {k: v for k, v in routines.items()
             if k in ('model_edit', 'feed', 'cells', 'poll', 'present')}
    for cost in costs.values():
        cost['mean_charged_cpu_ms'] = cost['charged_cpu_ms']['total']/cost['calls']
    return dict(result=reference(path/'results.json'),
        replay=reference(path/'replay-results.json'), build=image(result),
        trace=reference(path/'observed-trace.log'),
        runtime=runtime(result['runtime']), counters=result['counters'],
        routine_costs=costs,
        max_turn_cpu_ms=result['turn_profile']['max_charged_cpu_ms'],
        max_turn_elapsed_ms=result['turn_profile']['max_elapsed_ms'],
        scanout=[{k: r[k] for k in ('key', 'phase_base_cycles',
                    'first_correct_frame_upper_ms', 'last_incorrect_frame_ms',
                    'target_40ms')} for r in result['scanout']],
        completion=result['completion_timing'],
        sio=dict(verdict=result['timing']['verdict'],
            watchdog_max_us=result['timing']['alarms']['sio_watchdog']['service']['max_us'],
            deadline_misses=result['timing']['deadline_misses']),
        st_sample_gap_max_us=result['mouse_timing']['sample_gaps']['max_us'],
        pin=result['pin'], machine=result['machine'])


def record():
    root = ROOT/'build/console-circular'
    baseline = read(root/'baseline-refs.json')
    for ref in baseline:
        require(sha256(ROOT/ref['path']) == ref['sha256'], 'Changed BI5 baseline')
    rows = []
    for phase in (0, 3547, 14188):
        before = loaded(ROOT/f'build/blitter-irq/bi5-loaded-{phase}')
        after = loaded(root/f'cb4-loaded-{phase}')
        require(before['pin'] == after['pin'] and before['machine'] == after['machine'],
                'Changed loaded comparator configuration')
        b = before['routine_costs']['model_edit']['mean_charged_cpu_ms']
        a = after['routine_costs']['model_edit']['mean_charged_cpu_ms']
        require(a < b, 'Retained edit did not get cheaper')
        rows.append(dict(phase_base_cycles=phase, before=before, after=after,
                         retained_edit_mean_reduction_percent=100*(b-a)/b))
    require(len({r['after']['build']['xex_sha256'] for r in rows}) == 1,
            'Loaded phases changed images')
    code = {}
    for label, path in [('before', ROOT/'build/blitter-irq/bi5-scroll'),
                        ('after', root/'cb2-bitmap-opt')]:
        compiled = read(path/'program/program.a816.json')
        code[label] = {name: sum(r['size'] for r in compiled['routines']
                                if r['name'].startswith('M_'+name+'_'))
                       for name in ('CONSOLECORE', 'CONSOLEDISPLAY')}
    pin = rows[0]['after']['pin']
    bridge = ROOT/'build/mouse-bridge/AltirraBridgeServer'
    require(sha256(bridge) == pin['mouse_input']['tooling']['sha256'],
            'Changed mouse-capable emulator')
    result = dict(actual_emulator=reference(bridge),
        actual_rom=reference(ROOT/'build/firmware/altirraos-816.rom'),
        schema_version=1, slice='CB4', status='pass', tier='development',
        host_checks=dict(tests_run=321, skipped=4, failures=0),
        baseline=baseline, loaded=rows, isolated=dict(
            before=isolated(ROOT/'build/blitter-irq/bi5-scroll'),
            after=isolated(root/'cb2-bitmap-opt')),
        emitted_opt_code_bytes=code,
        bank_zero_delta=dict(fixed=0, root_kernel=0, per_task=[0]*8, private_idle=0),
        storage=dict(instance_bytes=200, instance_payload_delta_from_bi5=2,
            default_console_reserved_bytes=880, dynamic_instance_allocated_bytes=200,
            dynamic_instance_charge_delta=0, extra_cells_bytes=0),
        notes=[
            'BI5 artifacts were reused unchanged. No baseline workload was executed.',
            'The isolated CB2 image is the final production implementation; CB3 only changes fixtures.',
            'Retained-edit CPU includes full logical damage bookkeeping, not just row clearing.',
            'Loaded flood production is stopped by interactive progress: BI5 completes 33 rows and 10 lists, the new image 35 rows and 12 lists. Report call counts; aggregate totals are not equal-work comparisons.',
            'Feed and Cells call mixes, interrupt phase and presentation batching differ. Fixed isolated stages supplement these loaded totals when assessing mapping overhead.',
            'Raw input improves in all three phases; cooked input regresses in two. No general input-latency improvement or worst-case bound is claimed.',
            'The 4 ms worker-turn, 20 ms whole-scroll and 40 ms visible-input targets remain open.',
            'All reservation deltas include guards, alignment and unused capacity. No new Task, DP, stack or production cell buffer.',
            'Host checks include the pre-existing cartridge checks in the workspace; cartridge work is outside these commits.',
            'No full release qualification or demo refresh was performed.'])
    target = ROOT/'docs/development/console-circular-buffer-cb4.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print('Recorded CB4 comparison and same-image replays')


if __name__ == '__main__':
    record()
