#!/usr/bin/env python3
"""Collect completed DOS stream slices without rewriting earlier evidence."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, require, sha256
from ports_budget import account

ROUTING_CASES = {'objects-bank1', 'objects-bank3', 'abi', 'client', 'reuse',
                 'files', 'directories', 'lifetime', 'retry', 'large-read'}


def validate(record):
    require(record['status'] == 'pass' and record['suite'] in ('routing','nil','defaults','raw'), 'Incomplete streams gate')
    names={'routing':ROUTING_CASES,'nil':{'headless','mixed','abi'},
           'defaults':{'defaults-bank1','defaults-bank3','abi','reuse','files'},
           'raw':{'raw-bank1','raw-bank3','headless','abi','large-read','console-removal-guard'}}[record['suite']]
    require(len(record['cases']) == 2*len(names) and
            {(c['mode'], c['name']) for c in record['cases']} ==
            {(mode, name) for mode in ('raw', 'opt') for name in names}, 'Missing routing case')
    for case in record['cases']:
        require(case['status'] == 'pass' and case['runtime']['status'] == (4 if case['name']=='console-removal-guard' else 0) and
                case['runtime']['guards'] == 'intact', 'Failed routing execution')
        require(case['compiler_revision'] == record['compiler']['revision'] and not case['override'],
                'Unexpected routing compiler')
        for path, digest in case['inputs'].items():
            require(record['inputs'][path] == digest, 'Mixed slice inputs')
        for stack in case['runtime'].get('stack_observations', []):
            require(stack['untouched_above_floor'] >= 0, 'Touched task interrupt reserve')
        kernel = case['runtime'].get('kernel_stack_observation')
        if kernel:
            require(kernel['interrupt_reserve_bytes_touched'] == 0, 'Touched kernel interrupt reserve')
        if record['suite'] in ('nil','raw') and case['name'] in ('headless','mixed'):
            o=case['observations']
            require(o['checks']==(49 if case['name']=='mixed' else 41) and o['no_payload_access'] and
                    o['access_negative_control']=='stopped' and o['payload_before']==o['payload_after'],
                    'Missing NIL access/semantic evidence')
            require(case['runtime']['created']==(3 if case['name']=='mixed' else 1),'Unexpected NIL worker')
        if record['suite']=='nil' and case['name']=='abi':
            from generate_dos import check_routine
            check_routine(case['routines']['Write'],'Write')
            require(case['returns'][10:12]==[70003,0xffffffff],'Write argument/result width')
        if record['suite']=='defaults' and case['name'].startswith('defaults-'):
            require(case['observations']==dict(checks=44) and case['runtime']['created']==5,'Incomplete defaults/ownership gate')
            require(case['kernel_bank']==(3 if case['name'].endswith('3') else 1),'Wrong defaults bank')
        if record['suite'] in ('defaults','raw') and case['name']=='abi':
            from generate_dos import check_routine
            for name in ('Input','Output','SelectInput','SelectOutput','IsInteractive'):
                check_routine(case['routines'][name],name)
            require(case['returns'][-5:]==[0x70000,0x90000,0x70000,0x90000,0xffffffff],'Default ABI result width')
        if record['suite']=='raw' and case['name'].startswith('raw-'):
            require(case['checks']==dict(checks=51,otherChecks=8),'Incomplete RAW assertions')
            require(case['kernel_bank']==(3 if case['name'].endswith('3') else 1),'Wrong RAW bank')
            o=case['observations']
            require([v['stage'] for v in o]==['first-open','short-read-no-echo','pending-read-concurrent-write',
                    'first-opener-released','large-write-collected-source-freed'],'Missing RAW checkpoint')
            require(o[0]['created']==1 and o[2]['created']==2 and o[2]['live']==3,'Unexpected stream worker')
            require(o[-1]['payload_length']==70003 and o[-1]['cells_sha256'] and o[-1]['screen_sha256'],'Missing large-write oracle')
            require({v['key'] for v in case['schedule']}=={'A','B','C','CTRL','BREAK'},'Missing physical input')
        if case['name'].startswith('objects-'):
            require(case['observations'] == {'checks': 26}, 'Incomplete object-layout/identity gate')
            require(case['kernel_bank'] == (3 if case['name'].endswith('3') else 1), 'Wrong kernel bank')
        if case['name'] == 'large-read':
            require(case['observations'] == dict(checks=7, received=70003, verified=70003, ioError=0),
                    'Incomplete large-read stack gate')
        if case['capacity'] == 8:
            require(case['bank_zero'] == record['baseline_bank_zero'], 'Bank-zero reservation changed')
        else:
            require(case['capacity'] == 4 and case['bank_zero'] == record['baseline_bank_zero_four'],
                    'Four-task fixture reservation changed')
    require(record['bank_zero_fixed_delta'] == record['bank_zero_per_task_delta'] == 0,
            'Unexpected bank-zero growth')


def collect(directory):
    report = json.loads((directory / 'results.json').read_text())
    require(report['status'] == 'pass' and report['suite'] in ('routing','nil','defaults','raw'), 'Unfinished slice')
    pin = json.loads((ROOT / 'toolchain/actionc.json').read_text())
    baseline = json.loads((ROOT / 'docs/qualification/compiler-ae1f555.json').read_text())
    baseline_four = json.loads((ROOT / 'docs/qualification/memory-exec-api.json').read_text())['bank_zero']['after']['four']
    record = dict(schema_version=1, status='pass', suite=report['suite'], compiler=pin,
                  baseline_bank_zero=baseline['comparisons']['raw']['candidate']['bank_zero'],
                  baseline_bank_zero_four=baseline_four,
                  bank_zero_fixed_delta=0, bank_zero_per_task_delta=0,
                  scope='Shared inline DOS ownership, existing filesystem semantics, raw/optimized emitted execution and complete single-read call-chain stack gate.',
                  layouts=dict(common_header=8, filesystem_object_before=112,
                               filesystem_object_after=112, header_offsets=dict(next=0, owner=3, kind=6, backend=7),
                               filesystem_offsets=dict(mount=8, generation=12, cursor=16, ticket=108)),
                  inputs={}, cases=[], result_path=str(directory.relative_to(ROOT) / 'results.json'),
                  result_sha256=sha256(directory / 'results.json'))
    for group in report['cases']:
        for result in group['cases']:
            build = result['build']; path = directory / group['mode'] / result['name']
            inputs = {**build['task_inputs'], **build['platform_inputs'], **build['banked_inputs']}
            for relative, digest in inputs.items():
                require(sha256(ROOT / relative) == digest, 'Source changed during slice: ' + relative)
                record['inputs'][relative] = digest
            image = json.loads((path / 'program.a816.json').read_text())
            near = sum(len(s['bytes']) for s in image['segments'] if 0x8800 <= s['address'] < 0x9000)
            near += sum(s['size'] for s in image['zero_fill'] if 0x8800 <= s['address'] < 0x9000)
            baseline_near = None
            if result['name'] in ('files', 'directories', 'lifetime', 'retry'):
                old_path = ROOT / 'build/compiler-qualification-ae1f555' / ('dos-' + group['mode']) / result['name']
                old_result = json.loads((old_path / 'results.json').read_text())
                require(old_result['build']['source_sha256'] == build['source_sha256'], 'Different baseline fixture')
                old_image = json.loads((old_path / 'program.a816.json').read_text())
                baseline_near = sum(len(s['bytes']) for s in old_image['segments'] if 0x8800 <= s['address'] < 0x9000)
                baseline_near += sum(s['size'] for s in old_image['zero_fill'] if 0x8800 <= s['address'] < 0x9000)
            record['cases'].append(dict(name=result['name'], mode=group['mode'], status=result['status'],
                compiler_revision=build['revision'], override=build['override'],
                image_sha256=build['image_sha256'], xex_sha256=build['xex_sha256'],
                inputs=inputs, runtime=result['runtime'], observations=result.get('observations'),
                routines=result.get('routines'), returns=result.get('returns'), machine=result.get('machine'),
                checks=result.get('checks'),schedule=result.get('schedule'),
                kernel_bank=build['memory']['constants']['KERNEL_BANK'],
                capacity=build['memory'].get('task_capacity', 4),
                bank_zero=account(build['memory']), near_image_used=near,
                baseline_near_image_used=baseline_near,
                near_image_delta=None if baseline_near is None else near - baseline_near,
                result_sha256=sha256(path / 'results.json')))
    for path in ('tools/test_dos_streams.py', 'tools/dos_streams_record.py',
                 'tests/programs/dos_streams_routing.act', 'tools/test_dos_abi.py'):
        record['inputs'][path] = sha256(ROOT / path)
    if report['suite']=='nil':
        record['scope']='NIL and early destination dispatch; physical watchpoints with access negative control, headless and mixed MyDOS execution, 32-bit Write ABI.'
        record['layouts'].update(stream_handle=16, client_context=72, new_tasks=0, endpoint=0, transfer_request=0)
        for name in ('tests/programs/dos_streams_nil.act','tests/programs/dos_abi.act','tools/generate_dos_mounts.py'):
            record['inputs'][name]=sha256(ROOT/name)
    if report['suite']=='defaults':
        record['scope']='Task-local borrowed defaults, context lifetime and ownership, repeated Task reuse, read-only file output and current sixteen-call ABI.'
        record['layouts'].update(client_context_before=72,client_context_after=80,client_context_rounded=80,
            context_offsets=dict(owner=0,port=3,packet=6,objects=68,busy=70,input=71,output=74,request=77),
            slot_active=14,slot_reserved=16,additional_reply_ports=0,additional_signals=0)
        record['inputs']['tests/programs/dos_streams_defaults.act']=sha256(ROOT/'tests/programs/dos_streams_defaults.act')
        record['inputs']['tests/programs/dos_abi.act']=sha256(ROOT/'tests/programs/dos_abi.act')
    if report['suite']=='raw':
        record['scope']='Shared RAW endpoint and per-client synchronous requests; physical keyboard input, concurrent read/write ownership, allocation rollback, source release, 70003-byte output oracle and full MyDOS read stack gate.'
        record['layouts'].update(client_context=80,endpoint_record=98,endpoint_rounded=104,registry_reserved=16,
            handle=16,request_record=42,request_rounded=48,new_tasks=0,new_signal_ports=0,embedded_ignore_ports=1)
        for name in ('tests/programs/dos_streams_raw.act','tools/test_dos_streams_raw.py','tests/programs/dos_streams_nil.act'):
            record['inputs'][name]=sha256(ROOT/name)
    validate(record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Keep the existing qualification record')
    args.output.write_text(json.dumps(collect(args.directory.resolve()), indent=2) + '\n')
    print('Recorded passing DOS streams slice')
