"""Fail-closed emitted metadata evidence and original-MyDOS fixture provenance."""
from library_paths import record_input_paths
import json
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current
ARCHIVAL_MODULES=('lib/mydos/mydos.act','lib/mydos/mydosnames.act','lib/mydos/mydostypes.act')
LEGACY_MODULES=ARCHIVAL_MODULES+('lib/fs/fsbtypes.act',)
SHARED_MODULES=('lib/mydos/mydos.act','lib/mydos/mydostypes.act',
         'lib/fs/fsbtypes.act','lib/fs/fs83.act','lib/fs/fscore.act')
MODULES=(*SHARED_MODULES,'lib/fs/fsstatus.act')
INPUTS=(*MODULES,'tools/mydos_cases.py','tools/test_mydos.py','tools/mydos_fixtures.py','tools/mydos_producer.py','tools/mydos_metadata_record.py','tests/programs/mydos_metadata.act','tests/fixtures/mydos/blockwire.act','tests/fixtures/mydos/driver.inc','tests/fixtures/block/driver.inc','tests/fixtures/mydos/manifest.json')

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Unfinished metadata qualification')
    require(len(r['cases'])==4 and {(c['build']['optimize'],c['sector_bytes']) for c in r['cases']}=={(m,s) for m in (False,True) for s in (128,256)},'Incomplete metadata matrix')
    modules=ARCHIVAL_MODULES if r['schema_version']==1 else LEGACY_MODULES if r['schema_version']<=3 else SHARED_MODULES if r['schema_version']==4 else MODULES
    for c in r['cases']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed metadata execution')
        require(c['checks'][0]>=1099 and len(c['cases'])==33,'Incomplete assertions')
        for p in modules:require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed parser sources')
        require(c['fixture_provider_sha256']==r['inputs']['tests/fixtures/mydos/blockwire.act'],'Undeclared provider')
        if r['schema_version']>=2:require(c['driver_sha256']==r['inputs']['tests/fixtures/mydos/driver.inc'],'Undeclared parser driver')
        if r['schema_version']>=3:require(c['block_driver_sha256']==r['inputs']['tests/fixtures/block/driver.inc'],'Undeclared block driver')
        volume=next(v for v in r['fixtures'] if v['sector_bytes']==c['sector_bytes'])
        require(c['fixture_sha256']==volume['sha256'],'Mixed disk fixtures')
        phases={n['phase'] for n in c['requests']}
        require(set(range(10,24))|{0,1,2,3,4,5,30}<=phases,'Missing corruption/geometry case')
        require(any(n==dict(phase=30,sector=65520) for n in c['requests']),'Missing high directory')
        require(len(c['requests'])<4096,'Unbounded I/O')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')

def collect():
    cases=[]
    for mode in ('raw','opt'):
        for size in (128,256):
            directory=ROOT/f'build/dos-slice5/meta-{mode}{size}'
            case=compact(json.loads((directory/'results.json').read_text()))
            image=json.loads((directory/'program.a816.json').read_text())
            from mydos_files_record import storage_sizes
            case['storage_sizes']=storage_sizes(image)
            case['frames']={f['name']:f['local_stack_peak'] for f in image['routines'] if any(f['name'].startswith('M_'+m+'_') for m in ('MYDOS','FS83','FSCORE'))}
            cases.append(case)
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    record=dict(schema_version=5,status='pass',scope='Metadata parser with sector-byte provider; root caller, four-slot profile. Sparse 65535-sector metadata is parser-only. No public DOS API, filesystem worker or hardware claim.',inputs={p:sha256(ROOT/p) for p in INPUTS},cases=cases,
        fixtures=[{k:v[k] for k in ('path','sha256','sector_bytes','sectors','vtoc','producer')} for v in manifest['volumes']],
        platform=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text()),compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),bank_zero=current(),
        storage=dict(fixed_upper_delta=0,per_parser_workspace=cases[0]['storage_sizes'][0],workspace_heap=(cases[0]['storage_sizes'][0]+7)&~7,per_volume_record=cases[0]['storage_sizes'][1],volume_heap=(cases[0]['storage_sizes'][1]+7)&~7,additional_tasks=0,additional_signals=0),
        limits=dict(host_seconds=240,frames=12000,sector_requests=4096,path_bytes=255,components=16,directory_entries=64),
        commands=[f'python3 tools/test_mydos.py --case {m} --size {s} --output build/dos-slice5/meta-{m}{s}' for m in ('raw','opt') for s in (128,256)]+[f'python3 tools/mydos_producer.py --size {s} --output build/dos-slice5/producer{s}' for s in (128,256)]+['python3 tools/mydos_fixtures.py'])
    validate(record);return record
if __name__=='__main__':
    (ROOT/'docs/qualification/mydos-metadata.json').write_text(json.dumps(collect(),indent=2)+'\n');print('Validated MyDOS metadata matrix')
