#!/usr/bin/env python3
"""Freeze the resident shell's capacity, payload, replay and timing evidence."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, require, sha256
from ports_budget import account, current
from sio_concurrent_trace import LIMITS
from sio_transaction_trace import BASE_HZ

NAMES = {'target128-raw', 'target128-opt', 'target256-raw', 'target256-opt',
         'stock128-opt', 'bank3-raw', 'bank3-opt'}
ENTRIES = ['MAIN', 'READERENTRY', 'PRODUCERENTRY', 'SIGNALENTRY', 'RECEIVERENTRY']
BOUNDS = dict(checkpoint_host_seconds=180, checkpoint_guest_frames=9000,
              completion_host_seconds=1800, completion_guest_frames=30000)
STACKS = [1536] + [1024] * 7 + [512]


def guards(rt, status=0):
    require(rt['status'] == status and rt['guards'] == 'intact', 'Failed native execution')
    kernel = rt['kernel_stack_observation']
    require(kernel['reserved_bytes'] == 1536 and kernel['interrupt_reserve_bytes_touched'] == 0,
            'Kernel stack/reserve changed')
    stacks = rt['stack_observations']
    require([s['reserved_bytes'] for s in stacks] == STACKS, 'Task stack reservations changed')
    require(all(s['untouched_above_floor'] >= 0 and
                s['untouched_above_floor'] + s['touched_bytes'] + 256 == s['reserved_bytes']
                for s in stacks), 'Task interrupt reserve touched/changed')


def validate(r):
    require(r['status'] == 'pass' and len(r['cases']) == 7 and
            {c['name'] for c in r['cases']} == NAMES, 'Incomplete shell matrix')
    require(r['bank_zero_fixed_delta'] == r['bank_zero_per_task_delta'] == 0 and
            r['shell_allocation_bytes'] == 1288, 'Memory budget changed')
    require(r['serial_limits'] == LIMITS, 'Serial gates changed')
    for c in r['cases']:
        name = c['name']
        require(c['compiler_revision'] == r['compiler']['revision'] and not c['override'] and
                c['optimize'] == name.endswith('-opt'), 'Compiler/mode changed')
        require(c['bank_zero'] == r['baseline_bank_zero'] and c['task_capacity'] == 8 and
                c['kernel_bank'] == (3 if name.startswith('bank3') else 1), 'Capacity/map changed')
        require(c['fixture_task_entries'] == ENTRIES and c['hook_sha256'] and c['task_table_sha256'],
                'Missing fixture provenance')
        require(c['limits'] == BOUNDS and c['near_image_used'] <= 2048, 'Execution/image bounds changed')
        expected = 70003 if name.startswith('target256') else 777
        live = c['case']
        for execution in [live] + ([c['replay']] if c['replay'] else []):
            guards(execution['runtime'])
            require(execution['status'] == 'pass' and execution['runtime']['created'] == 7,
                    'Unexpected execution/Task creation')
            require(execution['sector_bytes'] == (256 if expected == 70003 else 128) and
                    execution['speed'] == int(name.startswith('stock')), 'Wrong media/drive')
            counts = execution['counters']
            require(counts['expected'] == counts['verified'] == expected, 'Incomplete file Read')
            require(counts['collected'] == counts['visible'] == 9 and counts['duringRead'] > 0,
                    'Missing keyboard progress')
            require(counts['commands'] == 5 and counts['captureCount'] == 1259 and
                    execution['writes_sha256'] == execution['expected_sha256'] == r['expected_writes_sha256'],
                    'Missing/incorrect command output')
            require(expected != 70003 or counts['commandOverlap'] > 0, 'No command queued during large Read')
            require(counts['allocations'] == counts['signals'] == counts['messages'] and
                    counts['allocations'] > 0 and counts['floods'] == 30 and
                    counts['finalAlloc'] > counts['initialAlloc'], 'Missing independent work')
            observations = execution['observations']
            require(len(observations) == 3 and all(o['live'] == 8 and o['created'] == 7 and
                    len(o['contexts']) == 8 and all(o['contexts']) for o in observations[:2]),
                    'Eight simultaneous Tasks not demonstrated')
            require(observations[-1]['frame'] - observations[0]['frame'] < BOUNDS['completion_guest_frames'],
                    'Guest completion bound exceeded')
            require(execution['xex_sha256'] == c['xex_sha256'] and
                    execution['image_sha256'] == c['image_sha256'], 'Executed image changed')
            machine = execution['machine']
            require(machine['accuratedisk'] and machine['siopatch'] == 'off' and not machine['burstio'] and
                    machine['diskemu'] == ('810' if name.startswith('stock') else 'fastest'), 'Machine shortcuts enabled')
        if name.startswith('bank3'):
            require(c['replay'] is None and c['timing'] is None, 'Bank-3 timing scope changed')
            continue
        replay = c['replay']
        require(replay and replay['schedule'] == live['schedule'] and
                replay['observations'][-1]['screen_sha256'] == live['observations'][-1]['screen_sha256'],
                'Image/input/display changed in replay')
        t = c['timing']
        require(t['verdict'] == 'pass' and not t['violations'] and
                t['deadline_misses'] == dict(rx=0, tx=0, tx_gaps=0), 'Failed serial byte oracle')
        deadline = (930 if name.startswith('stock') else 140) / BASE_HZ * 1e6
        require(abs(t['rx_byte_deadline_us'] - deadline) < .00001, 'Physical baud deadline changed')
        for field, limit in [('forbid', 'forbid_max_us'), ('critic_deferral_bound', 'critic_max_us'),
                             ('post_to_worker', 'post_to_worker_max_us'),
                             ('post_to_sector_collection', 'post_to_collect_max_us'),
                             ('post_to_next_start_during_read', 'next_start_max_us')]:
            require(t[field]['count'] > 0 and t[field]['max_us'] <= LIMITS[limit], 'Phase/collection gate: ' + field)
        for alarm in t['alarms'].values():
            require(alarm['service']['count'] > 0 and all(v['max_us'] is None or v['max_us'] <= 100
                    for v in alarm.values()), 'Alarm/watchdog deadline changed')
        require(t['file_read']['bytes'] == expected and all(t['read_progress'].values()), 'Missing measured Read/progress')
        for field in ('capture_to_collected_reply_upper_bound', 'capture_to_completed_editor_write_upper_bound'):
            require(t['keyboard'][field]['count'] == 9 and t['keyboard'][field]['median_us'] > 0,
                    'Missing editor/read latency observations')
        require(t['commands']['physical_completions'] == 1 and t['commands']['native_completions'] == 4 and
                t['commands']['durations']['count'] == 4, 'Missing command observations')
        stream = c['stream_timing']
        require(0 < stream['endpoint_forbid']['count'] <= t['forbid']['count'] and
                stream['endpoint_forbid']['max_us'] <= t['forbid']['max_us'] + .00001 and
                stream['endpoint_call_sites'] and stream['active_cpu_masked_max'] and stream['active_idle_masked_max'],
                'Missing endpoint/CPU/idle attribution')
    require(len(r['tx']) == 2 and {t['mode'] for t in r['tx']} == {'raw', 'opt'}, 'Missing transport TX')
    for tx in r['tx']:
        require(len(tx['cases']) == 2 and tx['cases'][0]['schedule'] == tx['cases'][1]['schedule'], 'Missing TX replay')
        for c in tx['cases']:
            guards(c['runtime'])
            require(c['media_before_sha256'] != c['media_after_sha256'], 'Missing TX media mutation')
        t = tx['cases'][0]['timing']
        require(t['verdict'] == 'pass' and not t['violations'] and
                LIMITS['write_delay_us'][0] <= t['write_delay_us'] <= LIMITS['write_delay_us'][1], 'Failed TX/turnaround oracle')
    controls = r['negative_controls']
    require(controls['status'] == 'pass' and {c['name'] for c in controls['cases']} ==
            {'missing-key', 'missing-command', 'late-rx', 'wrong-payload'} and
            all(c['expected_violation'] in c['violations'] for c in controls['cases']), 'Incomplete negative controls')
    require(controls['source_trace_sha256'] == next(c['trace_sha256'] for c in r['cases']
            if c['name'] == 'target128-opt'), 'Negative controls used a different observation')
    recovery = r['recovery']
    require(recovery['status'] == 'pass' and recovery['current_production_inputs_match'] and
            {(c['mode'], c['sector_size']) for c in recovery['cases']} ==
            {(mode, size) for mode in ('raw', 'opt') for size in (128, 256)}, 'Stale/incomplete recovery evidence')
    for c in recovery['cases']:
        require(len(c['cases']) == 6 and {x['name'] for x in c['cases']} ==
                {'checksum', 'device', 'short', 'firstcause', 'framing', 'protocol'}, 'Missing real fault responder')
        for fault in c['cases']:
            unsafe = fault['name'] not in ('checksum', 'device')
            guards(fault['runtime'], 0xff93 if unsafe else 0)
            state = fault['runtime']['shell_cleanup']
            require(state['directory_checked'] and state['directory_released'] and state['unsafe_retained'] == unsafe and
                    bool(state['shell_pointer']) == unsafe and fault['posts_baseline'] == 1 and fault['cleanup_reached'],
                    'Fault lost directory/console ownership or first completion')
    regression = r['watchdog_regression']
    require(regression['verdict'] == 'fail' and regression['violations'] == ['alarm deadline sio_watchdog'] and
            regression['watchdog_max_us'] > 100 and regression['deadline_misses'] == dict(rx=0, tx=0, tx_gaps=0),
            'Missing original watchdog failure evidence')


def collect(out):
    r = dict(schema_version=1, status='pass', compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
             platform_pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()),
             tx_platform_pin=json.loads((ROOT/'toolchain/altirra-console.json').read_text()),
             baseline_bank_zero=current()['after']['eight'], bank_zero_fixed_delta=0, bank_zero_per_task_delta=0,
             shell_allocation_bytes=1288, serial_limits=LIMITS, inputs={}, cases=[], tx=[],
             scope='Eight live Tasks plus idle: actual shared shell editor/parser/commands, independent current directories, '
                   'single complete MyDOS Read, memory/messages/signals and shared display. Five bank-1 timing cases with '
                   'identical-image/key replay; two bank-3 functional cases. Editor timing ends at retained redraw DOS.Write '
                   'completion, not physical scanout. Separate raw/optimized transport TX/readback and rerun real serial recovery '
                   'after a bounded console-path watchdog service fix; original 100 us deadline retained.')

    def provenance(b):
        for name, digest in {**b['task_inputs'], **b['platform_inputs'], **b['banked_inputs'], **b.get('console_inputs', {})}.items():
            require(sha256(ROOT/name) == digest, 'Production source changed: ' + name)
            r['inputs'][name] = digest
        require(b['compiler_contract'] == r['compiler'] and not b['override'], 'Unqualified compiler')
        compiler_inputs = {key: b[key] for key in ('binary_sha256', 'abi_sha256', 'abi_assembly_sha256')}
        require(r.setdefault('compiler_inputs', compiler_inputs) == compiler_inputs, 'Mixed compiler/ABI inputs')
        require(account(b['memory']) == r['baseline_bank_zero'], 'Bank-zero reservation changed')

    def trimmed(execution):
        result = dict(execution)
        result['runtime'] = {k: v for k, v in execution['runtime'].items()
                             if not isinstance(v, list) or k == 'stack_observations'}
        return result

    for name in sorted(NAMES):
        p = out/name/'results.json'
        v = json.loads(p.read_text())
        require(v['status'] == 'pass', 'Incomplete ' + name)
        b = v['build']
        provenance(b)
        require(v['pin'] == r['platform_pin'], 'Emulator pin changed')
        for path, digest in v['source_inputs'].items():
            require(sha256(ROOT/path) == digest, 'Workload source changed: ' + path)
            r['inputs'][path] = digest
        require(sha256(p.parent/'program.xex') == b['xex_sha256'], 'Image changed after execution')
        image = json.loads((p.parent/'program.a816.json').read_text())
        near = sum(len(s['bytes']) for s in image['segments'] if 0x8800 <= s['address'] < 0x9000)
        near += sum(s['size'] for s in image['zero_fill'] if 0x8800 <= s['address'] < 0x9000)
        trace = p.parent/'observed/trace.log'
        r['cases'].append(dict(name=name, compiler_revision=b['revision'], override=b['override'], optimize=b['optimize'],
            kernel_bank=b['memory']['constants']['KERNEL_BANK'], task_capacity=b['memory']['task_capacity'],
            image_sha256=b['image_sha256'], xex_sha256=b['xex_sha256'], source_sha256=b['source_sha256'],
            memory_sha256=b['memory_sha256'], manifest_sha256=b['manifest_sha256'],
            bank_zero=account(b['memory']), near_image_used=near, fixture_task_entries=v['fixture_task_entries'],
            task_table_sha256=b['task_generated']['tasks.inc'], fixture_sha256=v['fixture_sha256'], hook_sha256=v['hook_sha256'],
            case=trimmed(v['case']), replay=trimmed(v['replay']) if v.get('replay') else None,
            timing=v.get('timing'), stream_timing=v.get('stream_timing'), marks=v['marks'], limits=v['limits'],
            trace_sha256=sha256(trace) if trace.exists() else None,
            result_path=str(p.relative_to(ROOT)), result_sha256=sha256(p)))
    r['expected_writes_sha256'] = r['cases'][0]['case']['expected_sha256']
    for mode in ('raw', 'opt'):
        p = out/('tx-' + mode)/'results.json'
        v = json.loads(p.read_text()); b = v['build']
        require(v['status'] == 'pass' and b['optimize'] == (mode == 'opt'), 'Incomplete TX')
        provenance(b)
        r['tx'].append(dict(mode=mode, image_sha256=b['image_sha256'], xex_sha256=b['xex_sha256'], source_sha256=b['source_sha256'],
            cases=[trimmed(c) for c in v['cases']], limits=v['limits'], result_path=str(p.relative_to(ROOT)), result_sha256=sha256(p)))
    p = out/'controls/results.json'
    r['negative_controls'] = json.loads(p.read_text())
    r['negative_controls']['result_sha256'] = sha256(p)
    r['recovery'] = dict(status='pass', current_production_inputs_match=True, cases=[],
        scope='All four slice-7 real serial responder runs rebuilt with the console-path watchdog fix. Selected directory and RAW endpoint remain live during faults; safe cleanup and explicit unsafe retention are checked again.')
    for mode in ('raw', 'opt'):
        for size in (128, 256):
            p = out/'recovery'/mode/('serial-' + str(size))/'results.json'
            v = json.loads(p.read_text()); b = v['build']
            require(v['status'] == 'pass' and b['optimize'] == (mode == 'opt'), 'Incomplete recovery')
            provenance(b)
            for name, digest in v['source_inputs'].items():
                require(sha256(ROOT/name) == digest, 'Recovery source changed: ' + name)
                r['inputs'][name] = digest
            from test_sio_device import PIN as recovery_pin
            r['recovery']['cases'].append(dict(mode=mode, sector_size=size, cases=[trimmed(x) for x in v['cases']],
                image_sha256=b['image_sha256'], xex_sha256=b['xex_sha256'], source_sha256=b['source_sha256'],
                fixture_sha256=v['shell_fixture_sha256'], machine=v['machine'], media_sha256=v['media_sha256'],
                loaded_snapshot=v['loaded_snapshot'], pin=recovery_pin if size == 128 else
                json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text()),
                result_path=str(p.relative_to(ROOT)), result_sha256=sha256(p)))
    prior = ROOT/'docs/qualification/shell-watchdog-regression.json'
    r['watchdog_regression'] = dict(json.loads(prior.read_text()),
        record=str(prior.relative_to(ROOT)), record_sha256=sha256(prior))
    for name in ('tools/shell_concurrency_record.py', 'tools/test_shell_concurrent_suite.py', 'tools/shell_concurrent_trace.py',
                 'tools/test_shell_trace.py', 'tools/console_concurrent_trace.py', 'tools/dos_streams_timing.py',
                 'tools/test_console_tx.py', 'tests/programs/native_console_tx.act'):
        r['inputs'][name] = sha256(ROOT/name)
    validate(r)
    return r


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('directory', type=Path); a.add_argument('--output', type=Path, required=True)
    args = a.parse_args()
    require(not args.output.exists(), 'Keep existing evidence')
    args.output.write_text(json.dumps(collect(args.directory.resolve()), indent=2) + '\n')
    print('Recorded passing resident shell concurrency')
