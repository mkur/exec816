"""Fail-closed publication of native DOS client and lifecycle qualification."""
from library_paths import record_input_paths
import json
from native_program import ROOT,require,sha256
from ports_budget import current
REQUIRED={'call','early','reuse','alloc-context','alloc-port','alloc-signal','remove',*[f'context-{i}' for i in range(5)],*[f'regression-{n}' for n in ('tasks','signals','ports','heap','io')]}
KERNEL=('lib/exec/taskpolicy.act','lib/dos/task-dos.inc','platform/altirraos/dos.s','platform/altirraos/tasks.s')
CLIENT=('lib/dos/dosclient.act','lib/dos/doscore.act','lib/dos/dos-core-types.inc')

def validate(record):
    record=record_input_paths(record)
    require(record['status']=='pass','Incomplete DOS client record')
    require(len(record['suites'])==2 and {s['optimize'] for s in record['suites']}=={False,True},'Missing client compiler mode')
    for suite in record['suites']:
        require(suite['status']=='pass' and {c['case'] for c in suite['cases']}==REQUIRED and len(suite['cases'])==len(REQUIRED),'Incomplete client matrix')
        for case in suite['cases']:
            require(case['status']=='pass' and case['runtime']['guards']=='intact','Failed client case')
            require(case['build']['optimize']==suite['optimize'],'Mixed client compiler modes')
            for path in KERNEL+CLIENT:
                require(case['build']['task_inputs'][path]==record['inputs'][path],'Stale client/kernel input: '+path)
            if case['case']=='reuse':require(case['runtime']['created']==260,'Missing released task lifetimes')
            if case['case'] in ('early','alloc-context','alloc-port'):require(case['fixture_override_sha256'],'Missing controlled injection')
            if case['case']=='remove':require(case['runtime']['status']==4 and case['checks']==[0],'Live DOS resources removed')
            elif case['case'].startswith('context-') and case['case']!='context-0':require(case['runtime']['status']==4 and case['checks'][-1]==0,'Unsupported caller accepted')
            else:require(case['runtime']['status']==0,'Client did not complete')
    require(len(record['serial_regressions'])==2 and {c['build']['optimize'] for c in record['serial_regressions']}=={False,True},'Missing serial regressions')
    for case in record['serial_regressions']:
        for path in KERNEL:require(case['build']['task_inputs'][path]==record['inputs'][path],'Stale serial kernel')
        require(case['status']=='pass' and case['observed']['peakTasks']==8 and case['sector_size']==256,'Missing eight-task sector traffic')
        require(case['timing']['verdict']=='pass' and not case['timing']['violations'] and case['replay']['status']=='identical','Serial deadline/replay regression')
    require(len(record['stack_probes'])==2 and {c['build']['optimize'] for c in record['stack_probes']}=={False,True},'Missing eight-slot stack probes')
    for case in record['stack_probes']:
        require(case['status']=='pass' and case['runtime']['guards']=='intact' and len(case['runtime']['stack_observations'])==9,'Missing stack-profile evidence')
        for path in KERNEL+CLIENT:require(case['build']['task_inputs'][path]==record['inputs'][path],'Stale stack probe')
        require(all(s['untouched_above_floor']>=0 for s in case['runtime']['stack_observations']),'Task interrupt headroom consumed')
        require(case['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt headroom consumed')
    require(record['publication']['status']=='pass' and {c['name'] for c in record['publication']['cases'] if c['status']=='rejected'}=={'public','core','client'},'Unfinished DOS publication')
    require(record['bank_zero']['fixed_delta']==record['bank_zero']['per_task_delta']==0,'Unreviewed bank-zero growth')

def compact(case):
    c=dict(case);b=c['build'];c['build']={k:b[k] for k in ('revision','changes','override','binary_sha256','abi_sha256','source_sha256','image_sha256','xex_sha256','optimize','task_inputs','task_generated')}
    c['build']['kernel_bank']=b['memory']['constants']['KERNEL_BANK']
    c['build']['dos_storage']=b['memory']['dos_storage']
    r=c['runtime'];c['runtime']={k:r[k] for k in ('status','guards','created','live_tasks','native_nmi_count','native_irq_count','switches','gateway_calls','os_busy','fault_required')}
    if 'stack_observations' in r:
        c['runtime']['stack_observations']=r['stack_observations']
        c['runtime']['kernel_stack_observation']=r['kernel_stack_observation']
    return c

if __name__=='__main__':
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--suite',type=Path,action='append',required=True);p.add_argument('--serial',type=Path,action='append',required=True);p.add_argument('--stack',type=Path,action='append',required=True);p.add_argument('--publication',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'docs/qualification/dos-client.json');a=p.parse_args()
    suites=[json.loads(f.read_text()) for f in a.suite]
    require(all(s['inputs']==suites[0]['inputs'] for s in suites),'Mixed source snapshots')
    for suite in suites:suite['cases']=[compact(c) for c in suite['cases']]
    record=dict(schema_version=1,status='pass',scope='Test-enabled DOS contexts/packets and Task lifecycle; no filesystem or ordinary DOS publication',inputs=suites[0]['inputs'],suites=suites,serial_regressions=[compact(json.loads(f.read_text())) for f in a.serial],stack_probes=[compact(json.loads(f.read_text())) for f in a.stack],publication=json.loads(a.publication.read_text()),bank_zero=current(),storage=dict(side_entry_reserved=16,side_entry_active=11,fixed_upper_four=64,fixed_upper_eight=128,client_record=72,reply_port=27,reply_port_heap=32,per_initialized_client_heap=104,additional_bank_zero=0),completion_limits=dict(client_and_context=dict(host_seconds=240,frames=12000),reuse_and_task_regression=dict(host_seconds=600,frames=30000)),commands=['python3 tools/test_dos_client.py --case '+mode+' --suite '+','.join(sorted(REQUIRED))+' --output build/dos-slice3/verified-'+mode for mode in ('raw','opt')])
    record['inputs'].update({p:sha256(ROOT/p) for p in ('tools/dos_client_record.py','tools/test_dos_stack.py','tools/test_dos_publication.py')})
    validate(record);a.output.write_text(json.dumps(record,indent=2)+'\n');print('Validated DOS client matrix')
