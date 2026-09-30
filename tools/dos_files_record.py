"""Public file-handler evidence; actual SIO and injected completions kept separate."""
from library_paths import library_relative, record_input_paths
import json
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current
from generate_dos import check_routine
MODULES=tuple(library_relative(p) for p in ('doscalls.act','dos-implementation.inc','dosclient.act','doscore.act','dos-core-types.inc','dos-registry-types.inc','task-dos.inc','fsboot.act','fshandler.act','fsinit.act','fsio.act','fsnames.act','fsports.act','fsregistry.act','fstypes.act','fsworker.act','blockio.act','mydos.act','mydosfile.act'))
INPUTS=(*MODULES,'tools/native_program.py','tools/generate_dos.py','tools/generate_tasks.py','tools/test_dos_files.py','tools/dos_files_record.py','tests/programs/dos_files.act','tests/programs/dos_files_fault.act')

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Incomplete file API qualification')
    require(len(r['cases'])==4 and {(c['build']['optimize'],c['sector_bytes']) for c in r['cases']}=={(m,s) for m in (False,True) for s in (128,256)},'Incomplete file matrix')
    require(len(r['faults'])==4 and {(c['build']['optimize'],c['fault']) for c in r['faults']}=={(m,f) for m in (False,True) for f in ('checksum','short')},'Incomplete causal-error matrix')
    for c in r['cases']+r['faults']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed native execution')
        for p in MODULES:require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed handler sources')
        require(c['media_sha256']==r['media'][str(c['sector_bytes'])],'Unexpected media')
        require(c['runtime']['live_tasks']==0 and c['runtime']['os_busy']==0,'Incomplete shutdown')
        require(all(s['untouched_above_floor']>=0 for s in c['stacks']),'Task interrupt reserve touched')
        require(c['kernel_stack']['interrupt_reserve_bytes_touched']==0,'Kernel reserve touched')
        if c['fault']:require(c['override_sha256'] and c['checks'][0]==8,'Missing failure transaction checks')
        else:
            require(c['concurrent'] and c['checks'][0]>=26 and c['other_checks'][0]==28 and c['io_progress'][0]>0,'Missing concurrent clients or allocation rollback')
            require(c['runtime']['created']==4,'Missing five-task workload')
        require(set(c['public_shapes'])=={'Open','Read','Seek','Close','IoErr','ReleaseContext'},'Incomplete emitted DOS ABI')
    require(all(c['status']=='pass' for c in r['regressions']),'Failed regression')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')

def case(directory):
    raw=json.loads((directory/'results.json').read_text());c=compact(raw)
    c['stacks']=raw['runtime']['stack_observations'];c['kernel_stack']=raw['runtime']['kernel_stack_observation']
    c['configuration']={k:raw['build'][k] for k in ('dos_system','dos_mounts')}
    c['configuration']['task_capacity']=raw['build']['memory']['task_capacity']
    p=json.loads((directory/'program.a816.json').read_text());c['public_shapes']={}
    for name in ('Open','Read','Seek','Close','IoErr','ReleaseContext'):
        routine=next(f for f in p['routines'] if f['name'].startswith('M_DOS_'+name.upper()+'_'))
        check_routine(routine,name);c['public_shapes'][name]='verified'
    c['frames']={f['name']:f['local_stack_peak'] for f in p['routines'] if f['name'].startswith(('M_FSWORKER_','M_FSHANDLER_','M_DOSCALLS_'))}
    return c

def collect():
    base=ROOT/'build/dos-slice7'
    cases=[case(base/f'verified-{m}{s}') for m in ('raw','opt') for s in (128,256)]
    faults=[case(base/f'error-{f}-{m}') for m in ('raw','opt') for f in ('checksum','short')]
    names=[f'{suite}-{m}{s}' for suite in ('metadata','parser-files') for m in ('raw','opt') for s in (128,256)]
    names += [f'{suite}-{m}' for suite in ('block-fixture','block-sio','client-regression') for m in ('raw','opt')]
    regressions=[]
    for n in names:
        path=base/n/'results.json';v=json.loads(path.read_text());require(v['status']=='pass','Failed '+n)
        regressions.append(dict(name=n,status=v['status'],results_sha256=sha256(path)))
    path=ROOT/'build/dos-slice3/publication/results.json';require(json.loads(path.read_text())['status']=='pass','Public gate failed')
    regressions.append(dict(name='ordinary-publication-rejection',status='pass',results_sha256=sha256(path)))
    r=dict(schema_version=1,status='pass',scope='Opt-in file API on original MyDOS media over real SIO. Five simultaneous public tasks in the eight-slot stack profile; no full eight-task timing or ordinary publication claim.',
        inputs={p:sha256(ROOT/p) for p in INPUTS},compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text()),media={str(s):sha256(ROOT/f'tests/fixtures/mydos/mydos450-{s}.atr') for s in (128,256)},cases=cases,faults=faults,regressions=regressions,bank_zero=current(),
        fault_scope='Test-only completion overrides after real SIO collection on data sector 5: checksum error 4 or short io_Actual. Physical wire faults are qualified separately in sio-sectors.json.',
        storage=dict(fixed_upper_active=90,fixed_upper_reserved=96,service_record=70,service_heap=72,per_worker_heap=656,per_mount_heap=192,per_client_heap=104,per_file_record=108,per_file_heap=112,worker_signals=2,worker_task_slots=1,descriptor_reserved=128,per_configured_mount_descriptor=44,context_slot_active=14,context_slot_reserved=16),
        limits=dict(host_seconds=240,frames=12000,alias_bytes=31,path_bytes=255,operation_scheduling='One complete DOS operation; round-robin mount queues between operations.'),
        commands=[f'python3 tools/test_dos_files.py --case {m} --size {s} --capacity 8 --concurrent --output build/dos-slice7/verified-{m}{s}' for m in ('raw','opt') for s in (128,256)]+[f'python3 tools/test_dos_files.py --case {m} --size 128 --capacity 8 --fault {f} --output build/dos-slice7/error-{f}-{m}' for m in ('raw','opt') for f in ('checksum','short')])
    validate(r);return r
if __name__=='__main__':
    (ROOT/'docs/qualification/dos-files.json').write_text(json.dumps(collect(),indent=2)+'\n');print('Validated public file API matrix')
