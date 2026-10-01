#!/usr/bin/env python3
"""Collect relative-path ownership, ancestry, layout and complete-read evidence."""
from image_data_usage import used as image_data_used
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import historical,account,current
CASES={'bank1-128','bank1-256','bank3-128','bank3-256','depth','corrupt-ancestry','abi',
       'headless','mixed','lifetime','directories','relative-large','absolute-large'}
# The retained record predates foreground calls. Its exact required call set
# remains fixed; freshly collected evidence must cover the current contract.
ARCHIVAL_CALLS={'Open','Read','Write','Seek','Close','IoErr','Lock','UnLock',
 'Examine','ExNext','ReleaseContext','Input','Output','SelectInput','SelectOutput',
 'IsInteractive','CurrentDir','NameFromLock'}


def validate(record,*,current_abi=False):
    require(record['status']=='pass','Unfinished relative paths')
    require(len(record['cases'])==2*len(CASES) and
            {(c['mode'],c['name'])for c in record['cases']}=={(m,n)for m in ('raw','opt')for n in CASES},'Missing relative case')
    budgets=current()['after'] if current_abi else historical()
    for case in record['cases']:
        require(case['status']=='pass' and case['runtime']['status']==0 and case['runtime']['guards']=='intact','Failed native case')
        require(case['compiler_revision']==record['compiler']['revision'] and not case['override'],'Unpinned compiler')
        require(case['bank_zero']==budgets['eight' if case['capacity']==8 else 'four'],'Bank-zero growth')
        require(all(record['inputs'][p]==h for p,h in case['inputs'].items()),'Mixed production sources')
        for s in case['runtime'].get('stack_observations',[]):require(s['untouched_above_floor']>=0,'Task reserve touched')
        if 'kernel_stack_observation' in case['runtime']:
            require(case['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel reserve touched')
        if case['name'].startswith('bank'):
            require(case['observations']==dict(checks=[82]),'Incomplete relative ownership/base checks')
            require(case['kernel_bank']==int(case['name'][4]) and case['sector_bytes']==int(case['name'].split('-')[1]),'Wrong bank/media matrix')
            require(len(set(case['media']))==2 and case['media_variant'],'Indistinguishable cross-mount data')
        if case['name'] in ('depth','corrupt-ancestry'):
            require(case['observations']==dict(checks=[14 if case['name']=='depth' else 10]),'Incomplete ancestry gate')
            require(case['fixture_sha256'] and len(case['media'])==1,'Missing derived fixture evidence')
        if case['name'] in ('headless','mixed'):
            o=case['observations'];require(o['checks']==(41 if case['name']=='headless' else 49) and o['no_payload_access'] and o['access_negative_control']=='stopped','Missing stream classification/access checks')
        if case['name'].endswith('-large'):
            require(case['observations']==dict(checks=10 if case['name']=='relative-large' else 7,received=70003,verified=70003,ioError=0),'Incomplete single Read')
        if case['name']=='abi':
            from generate_dos import ABI,check_routine
            calls=set(ABI['imports']) if current_abi else ARCHIVAL_CALLS
            require(set(case['routines'])==calls,'Missing DOS ABI call')
            for name in calls:check_routine(case['routines'][name],name)
    require(record['layouts']==dict(client=86 if current_abi else 84,client_heap=88,file=112,max_lock_heap=376,
            service_before=428,service=434,service_heap_before=432,service_heap=440,
            parent_sector_bytes=2,continuation_pointer_bytes=3,name_workspace=256),'Changed layout/budget')
    require(record['bank_zero_fixed_delta']==record['bank_zero_per_task_delta']==0,'Bank-zero delta changed')


def collect(directory):
    record=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
        scope='DOS relative/parent/current-volume-root paths from independent Tasks, private base validation and complete relative/absolute reads; no shell dependency.',
        layouts=dict(client=86,client_heap=88,file=112,max_lock_heap=376,service_before=428,service=434,
            service_heap_before=432,service_heap=440,parent_sector_bytes=2,continuation_pointer_bytes=3,name_workspace=256),
        bank_zero_fixed_delta=0,bank_zero_per_task_delta=0,inputs={},cases=[])
    for mode in ('raw','opt'):
        for name in sorted(CASES):
            path=directory/mode/name;r=json.loads((path/'results.json').read_text());b=r['build']
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs']}
            for p,h in inputs.items():require(sha256(ROOT/p)==h,'Source changed: '+p);record['inputs'][p]=h
            image=json.loads((path/'program.a816.json').read_text())
            near=image_data_used(image,b['memory'])
            record['cases'].append(dict(name=name,mode=mode,status=r['status'],compiler_revision=b['revision'],override=b['override'],
                source_sha256=b['source_sha256'],image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],
                compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],inputs=inputs,generated=b['task_generated'],
                runtime={k:v for k,v in r['runtime'].items()if not isinstance(v,list)or k=='stack_observations'},machine=r['machine'],
                observations=r.get('observations'),routines=r.get('routines'),checks=r.get('checks'),bank_zero=account(b['memory']),
                capacity=b['memory'].get('task_capacity',4),kernel_bank=b['memory']['constants']['KERNEL_BANK'],near_image_used=near,
                sector_bytes=r.get('sector_bytes'),media_sha256=r.get('media_sha256'),media=r.get('media'),
                media_variant=r.get('media_variant'),fixture_sha256=r.get('fixture_sha256'),result_sha256=sha256(path/'results.json')))
    for p in ('tools/test_dos_relative.py','tools/dos_relative_record.py','tests/programs/dos_relative_paths.act',
              'tests/programs/dos_relative_bounds.act','tests/programs/dos_relative_large.act',
              'tools/test_dos_lock_names.py','tests/programs/dos_streams_nil.act'):
        record['inputs'][p]=sha256(ROOT/p)
    validate(record,current_abi=True);return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(collect(a.directory),indent=2)+'\n')
