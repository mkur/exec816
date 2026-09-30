"""Fail-closed native directory-packet qualification on original and damaged media."""
from library_paths import library_relative, record_input_paths
import json
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current
from generate_dos import check_routine
MODULES=tuple(library_relative(p) for p in ('doscalls.act','dos-implementation.inc','dosclient.act','fshandler.act','fsdirectory.act','fsinfo.act','fspacket.act','fsregistry.act','fstypes.act','fsinit.act','fsworker.act','fsio.act','fsboot.act','mydos.act','mydosfile.act'))
INPUTS=(*MODULES,'tools/test_dos_directories.py','tools/dos_directories_record.py','tests/programs/dos_directories.act','tools/native_program.py','tools/generate_tasks.py')
CALLS=('Open','Read','Seek','Close','IoErr','Lock','UnLock','Examine','ExNext','ReleaseContext')

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Incomplete directory qualification')
    require(len(r['cases'])==4 and {(c['build']['optimize'],c['sector_bytes']) for c in r['cases']}=={(m,s) for m in (False,True) for s in (128,256)},'Incomplete normal matrix')
    require(len(r['damage'])==6 and {(c['build']['optimize'],c['variant']) for c in r['damage']}=={(m,v) for m in (False,True) for v in ('empty','name','chain')},'Incomplete damage matrix')
    for c in r['cases']+r['damage']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed execution')
        for p in MODULES:require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed directory sources')
        require(c['build']['source_sha256']==r['inputs']['tests/programs/dos_directories.act'],'Mixed assertion programs')
        require(c['original_sha256']==r['media'][str(c['sector_bytes'])],'Unpinned oracle')
        require(len(c['oracle'])==67 and c['other_checks'][0]==(2 if c['variant'] in ('name','chain') else 9),'Missing entries or independent caller')
        if c['variant']=='normal':
            require(c['checks'][0]>1400 and c['media_sha256']==c['original_sha256'],'Missing full metadata comparison')
            if c['sector_bytes']==256:require(c['expected_sizes']['LARGE.BIN']==70003,'Missing exact large-file size')
        require(set(c['public_shapes'])==set(CALLS),'Missing native call shape')
        require(c['private_entries_excluded'],'Private helper published as application entry')
        require(all(s['untouched_above_floor']>=0 for s in c['stacks']) and c['kernel_stack']['interrupt_reserve_bytes_touched']==0,'Interrupt reserve touched')
        require(c['runtime']['live_tasks']==0 and c['runtime']['created']==3,'Incomplete service/client lifetime')
    require(len(r['regressions'])>=4 and all(c['status']=='pass' for c in r['regressions']),'Missing regressions')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')

def case(path):
    raw=json.loads((path/'results.json').read_text());c=compact(raw)
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    volume=next(v for v in manifest['volumes'] if v['sha256']==c['original_sha256'])
    c['expected_sizes']={f['path']:f['bytes'] for f in volume['files']}
    c['stacks']=raw['runtime']['stack_observations'];c['kernel_stack']=raw['runtime']['kernel_stack_observation']
    image=json.loads((path/'program.a816.json').read_text());c['public_shapes']={}
    for name in CALLS:
        f=next(f for f in image['routines'] if f['name'].startswith('M_DOS_'+name.upper()+'_'))
        check_routine(f,name);c['public_shapes'][name]='verified'
    c['private_entries_excluded']=not any(f['address'] in raw['build']['task_entries'] for f in image['routines'] if f['name'].startswith(('M_FS','M_DOS_','M_DOSCALLS_','M_DOSCLIENT_','M_DOSCORE_','M_DOSWIRE_')))
    c['frames']={f['name']:f['local_stack_peak'] for f in image['routines'] if f['name'].startswith(('M_FSDIRECTORY_','M_FSINFO_','M_FSPACKET_'))}
    return c

def collect():
    base=ROOT/'build/dos-slice8'
    cases=[case(base/f'final-{m}{s}') for m in ('raw','opt') for s in (128,256)]
    damage=[case(base/f'final-{v}-{m}128') for m in ('raw','opt') for v in ('empty','name','chain')]
    regressions=[]
    for suite in ('files','metadata'):
        for m in ('raw','opt'):
            p=base/f'regression-{suite}-{m}'/'results.json';v=json.loads(p.read_text());require(v['status']=='pass','Failed '+str(p))
            regressions.append(dict(name=p.parent.name,status='pass',results_sha256=sha256(p)))
    r=dict(schema_version=1,status='pass',scope='All public DOS call shapes and read-only directory packets in opt-in system fixtures. Root, filesystem worker, SIO worker and second client in eight-slot stack layout. Ordinary publication and integrated timing remain later gates.',inputs={p:sha256(ROOT/p) for p in INPUTS},compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text()),media={str(s):sha256(ROOT/f'tests/fixtures/mydos/mydos450-{s}.atr') for s in (128,256)},cases=cases,damage=damage,regressions=regressions,bank_zero=current(),
        storage=dict(fixed_upper_delta=0,per_worker_record=170,per_worker_heap=760,service_heap=176,per_mount_heap=192,per_client_heap=104,per_file_or_lock_record=112,per_file_or_lock_heap=112,fib_record=260,enumeration_record=16,enumeration_reserved_in_fib=32,additional_tasks=0,additional_signals=0),
        failed_experiments=[dict(case='normal-opt256',host_seconds=600,checks=370,reason='Host watchdog while the guest awaited the large-file metadata result',image_sha256=json.loads((base/'normal-opt256/build.json').read_text())['image_sha256'])],
        corrections='Slice 7 record sizes corrected to Service 70 and Object 108; heap rounding was already correct (72 and 112). Current emitted assertions verify Service 170 and Object 112, including the additional measurement cursor and unique object ticket.',
        limits=dict(host_seconds={128:600,256:3600},frames=30000,root_entries=64,max_chain_hops=65535,enumeration_state='Unique object ticket, mount generation checked by object lookup, FIB address, next ordinal; no wrapping object identities.'),
        commands=[f'python3 tools/test_dos_directories.py --case {m} --size {s} --output build/dos-slice8/final-{m}{s}' for m in ('raw','opt') for s in (128,256)]+[f'python3 tools/test_dos_directories.py --case {m} --size 128 --variant {v} --output build/dos-slice8/final-{v}-{m}128' for m in ('raw','opt') for v in ('empty','name','chain')])
    validate(r);return r
if __name__=='__main__':
    (ROOT/'docs/qualification/dos-directories.json').write_text(json.dumps(collect(),indent=2)+'\n');print('Validated DOS directory matrix')
