#!/usr/bin/env python3
"""Archive DOS directory slice evidence and enforce its execution/map gates."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, require, sha256
from ports_budget import account, current

CURRENT_CASES = {'directory-bank1','directory-bank3','defaults-bank1','defaults-bank3',
                 'abi','selected-removal','client','lifetime','reuse','files','large-read'}


def validate(record,*,current_layout=False):
    require(record['status'] == 'pass', 'Failed directory qualification')
    expected = {(mode,name) for mode in ('raw','opt') for name in CURRENT_CASES}
    require(len(record['cases']) == len(expected) and
            {(c['mode'],c['name']) for c in record['cases']} == expected, 'Missing directory case')
    budgets = current()['after']
    for case in record['cases']:
        require(case['status'] == 'pass' and case['runtime']['guards'] == 'intact', 'Failed execution/guards')
        require(case['compiler_revision'] == record['compiler']['revision'] and not case['override'], 'Unpinned compiler')
        expected_status = 4 if case['name'] == 'selected-removal' else 0
        require(case['runtime']['status'] == expected_status, 'Unexpected native termination')
        require(case['bank_zero'] == budgets['eight' if case['capacity'] == 8 else 'four'], 'Bank-zero growth')
        for path,digest in case['inputs'].items():
            require(record['inputs'][path] == digest, 'Mixed production inputs')
        for stack in case['runtime'].get('stack_observations',[]):
            require(stack['untouched_above_floor'] >= 0, 'Task interrupt reserve touched')
        kernel = case['runtime'].get('kernel_stack_observation')
        if kernel: require(kernel['interrupt_reserve_bytes_touched'] == 0, 'Kernel reserve touched')
        if case['name'].startswith('directory-bank'):
            require(case['observations'] == dict(checks=40) and case['runtime']['created'] == 5, 'Incomplete directory ownership checks')
            require(case['kernel_bank'] == int(case['name'][-1]), 'Wrong kernel bank')
        if case['name'] == 'selected-removal':
            require(case['observations'] == dict(checks=14) and case['runtime']['live_tasks'] == 3, 'Missing selected-directory removal guard')
        if case['name'] == 'large-read':
            require(case['observations'] == dict(checks=7,received=70003,verified=70003,ioError=0), 'Incomplete full Read')
        if case['name'] == 'abi':
            from generate_dos import check_routine
            check_routine(case['routines']['CurrentDir'],'CurrentDir')
            require(case['returns'][17] == 0x70000, 'Truncated CurrentDir result')
    require(record['memory_delta'] == dict(bank_zero_fixed=0,bank_zero_per_task=0,
            client_active=86 if current_layout else 83,client_record=86 if current_layout else 84,client_allocation=88,previous_client_allocation=80), 'Client layout mismatch')


def collect(directory):
    record = dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
                  scope='DOS CurrentDir ownership and lifetime; absolute paths and existing streams retained; relative paths deferred.',
                  memory_delta=dict(bank_zero_fixed=0,bank_zero_per_task=0,client_active=86,client_record=86,
                                    client_allocation=88,previous_client_allocation=80),inputs={},cases=[])
    for mode in ('raw','opt'):
        for name in sorted(CURRENT_CASES):
            path = directory/mode/name
            result = json.loads((path/'results.json').read_text()); build = result['build']
            inputs = {**build['task_inputs'],**build['platform_inputs'],**build['banked_inputs']}
            for relative,digest in inputs.items():
                require(sha256(ROOT/relative) == digest, 'Source changed: '+relative)
                record['inputs'][relative] = digest
            image = json.loads((path/'program.a816.json').read_text())
            near = sum(len(s['bytes']) for s in image['segments'] if 0x8800 <= s['address'] < 0x9000)
            near += sum(s['size'] for s in image['zero_fill'] if 0x8800 <= s['address'] < 0x9000)
            record['cases'].append(dict(name=name,mode=mode,status=result['status'],runtime={k:v for k,v in result['runtime'].items() if not isinstance(v,list) or k=='stack_observations'},
                compiler_revision=build['revision'],override=build['override'],image_sha256=build['image_sha256'],
                xex_sha256=build['xex_sha256'],source_sha256=build['source_sha256'],
                compiler_binary_sha256=build['binary_sha256'],abi_sha256=build['abi_sha256'],
                inputs=inputs,generated=build['task_generated'],machine=result['machine'],
                observations=result.get('observations'),routines=result.get('routines'),returns=result.get('returns'),
                checks=result.get('checks'),bank_zero=account(build['memory']),near_image_used=near,
                kernel_bank=build['memory']['constants']['KERNEL_BANK'],capacity=build['memory'].get('task_capacity',4),
                media_sha256=result.get('media_sha256'),result_sha256=sha256(path/'results.json')))
    for name in ('tools/test_dos_directory.py','tools/dos_directory_record.py','tests/programs/dos_current_directory.act',
                 'tests/programs/dos_streams_defaults.act','tests/programs/dos_abi.act','tools/test_dos_abi.py'):
        record['inputs'][name] = sha256(ROOT/name)
    validate(record,current_layout=True)
    return record

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_text(json.dumps(collect(args.directory),indent=2)+'\n')
