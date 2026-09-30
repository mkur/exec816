#!/usr/bin/env python3
"""Collect canonical-lock-name execution, allocation and ownership evidence."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import account,current
CASES={'names-bank1','names-bank3','allocation','bounds','abi','current-directory','directories',
       'corrupt-name','files','lifetime','large-read'}


def validate(record):
    require(record['status']=='pass','Unfinished lock names')
    require(len(record['cases'])==2*len(CASES) and
            {(c['mode'],c['name']) for c in record['cases']}=={(m,n) for m in ('raw','opt') for n in CASES},'Missing lock-name case')
    for case in record['cases']:
        require(case['status']=='pass' and case['runtime']['status']==0 and case['runtime']['guards']=='intact','Failed native case')
        require(case['compiler_revision']==record['compiler']['revision'] and not case['override'],'Unpinned compiler')
        require(case['bank_zero']==current()['after']['eight' if case['capacity']==8 else 'four'],'Bank-zero growth')
        require(all(record['inputs'][p]==h for p,h in case['inputs'].items()),'Mixed sources')
        for s in case['runtime'].get('stack_observations',[]):require(s['untouched_above_floor']>=0,'Task reserve touched')
        if 'kernel_stack_observation' in case['runtime']:
            require(case['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel reserve touched')
        if case['name'].startswith('names-bank'):
            require(case['observations']==dict(checks=[53],layouts=[112,428,2,88]),'Incomplete name/layout checks')
            require(case['kernel_bank']==int(case['name'][-1]),'Wrong kernel bank')
        if case['name']=='allocation':
            require(case['observations']==dict(checks=[6]) and case['override_sha256'],'Missing allocation rollback')
        if case['name']=='bounds':
            require(case['observations']==dict(checks=[12]) and len(case['path_cases'])==7,'Missing path bounds')
        if case['name']=='abi':
            from generate_dos import check_routine
            check_routine(case['routines']['NameFromLock'],'NameFromLock')
            require(case['returns'][18]==0xffffffff,'Wrong name result ABI')
        if case['name']=='large-read':
            require(case['observations']==dict(checks=7,received=70003,verified=70003,ioError=0),'Incomplete full Read')
    require(record['layouts']==dict(file=112,lock_prefix=112,name_length=2,max_name=255,max_lock_request=370,
            max_lock_allocation=376,service_before=170,service_after=428,service_allocation_before=176,
            service_allocation_after=432,name_workspace=256,name_control=2,client_allocation=88),'Layout/budget changed')
    require(record['bank_zero_fixed_delta']==record['bank_zero_per_task_delta']==0,'Bank-zero delta changed')


def collect(directory):
    record=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
                scope='Cached canonical lock names, variable lock allocations, real SIO and mixed RAW/NIL/file ownership; parent and relative paths remain deferred.',
                layouts=dict(file=112,lock_prefix=112,name_length=2,max_name=255,max_lock_request=370,max_lock_allocation=376,
                    service_before=170,service_after=428,service_allocation_before=176,service_allocation_after=432,
                    name_workspace=256,name_control=2,client_allocation=88),
                bank_zero_fixed_delta=0,bank_zero_per_task_delta=0,
                lock_storage=dict(actual_names=[3,12,21,11],rounded_allocations=[120,128,136,128],
                    real_lock_heap=512,synthetic_maximum=376,peak_live_lock_heap=888,
                    simultaneous_ordinary_file=112,synthetic_fixture_workspace=432,
                    accounting='Known simultaneous fixture allocations; the 255-byte name and extra workspace are private storage-boundary probes.'),
                inputs={},cases=[])
    for mode in ('raw','opt'):
        for name in sorted(CASES):
            path=directory/mode/name;r=json.loads((path/'results.json').read_text());b=r['build']
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs']}
            for p,h in inputs.items():require(sha256(ROOT/p)==h,'Source changed: '+p);record['inputs'][p]=h
            image=json.loads((path/'program.a816.json').read_text())
            near=sum(len(s['bytes']) for s in image['segments'] if 0x8800<=s['address']<0x9000)
            near+=sum(s['size'] for s in image['zero_fill'] if 0x8800<=s['address']<0x9000)
            record['cases'].append(dict(name=name,mode=mode,status=r['status'],compiler_revision=b['revision'],override=b['override'],
                source_sha256=b['source_sha256'],image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],
                compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],inputs=inputs,generated=b['task_generated'],
                runtime={k:v for k,v in r['runtime'].items() if not isinstance(v,list) or k=='stack_observations'},
                machine=r['machine'],observations=r.get('observations'),routines=r.get('routines'),returns=r.get('returns'),
                checks=r.get('checks'),bank_zero=account(b['memory']),capacity=b['memory'].get('task_capacity',4),
                kernel_bank=b['memory']['constants']['KERNEL_BANK'],near_image_used=near,
                media_sha256=r.get('media_sha256'),media=r.get('media'),override_sha256=r.get('override_sha256'),
                path_cases=r.get('path_cases'),result_sha256=sha256(path/'results.json')))
    for p in ('tools/test_dos_lock_names.py','tools/dos_names_record.py','tests/programs/dos_lock_names.act',
              'tests/programs/dos_lock_allocation.act','tests/programs/dos_lock_bounds.act','tests/programs/dosfaultcontrol.act',
              'tools/test_dos_abi.py','tests/programs/dos_abi.act'):
        record['inputs'][p]=sha256(ROOT/p)
    validate(record);return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(collect(a.directory),indent=2)+'\n')
