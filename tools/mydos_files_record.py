"""Publish bounded native file-chain evidence without conflating it with SIO."""
from library_paths import record_input_paths
import collections,hashlib,json
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current
ARCHIVAL_MODULES=('lib/mydos/mydosfile.act','lib/mydos/mydosfiletypes.act','lib/mydos/mydos.act','lib/mydos/mydosnames.act','lib/mydos/mydostypes.act')
LEGACY_MODULES=tuple(p for p in ARCHIVAL_MODULES if 'mydosfiletypes' not in p)+('lib/fs/fsbtypes.act','lib/spartados/sdfstypes.act')
SHARED_MODULES=tuple(p for p in LEGACY_MODULES if 'mydosnames' not in p)+('lib/fs/fs83.act','lib/fs/fscore.act')
MODULES=(*SHARED_MODULES,'lib/fs/fsstatus.act')
INPUTS=(*MODULES,'tools/mydos_file_cases.py','tools/test_mydos_files.py','tools/mydos_files_record.py','tests/programs/mydos_files.act','tests/fixtures/mydos/blockwire.act','tests/fixtures/mydos/driver.inc','tests/fixtures/block/driver.inc','tests/fixtures/mydos/manifest.json')

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Incomplete file qualification')
    require(len(r['cases'])==4 and {(c['build']['optimize'],c['sector_bytes']) for c in r['cases']}=={(m,s) for m in (False,True) for s in (128,256)},'Incomplete compiler/sector matrix')
    modules=ARCHIVAL_MODULES if r['schema_version']==1 else LEGACY_MODULES if r['schema_version']<=3 else SHARED_MODULES if r['schema_version']==4 else MODULES
    for c in r['cases']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed native execution')
        require(c['checks'][0]>700,'Missing guest assertions')
        for p in modules:require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed parser source')
        require(c['fixture_provider_sha256']==r['inputs']['tests/fixtures/mydos/blockwire.act'],'Unpinned provider')
        if r['schema_version']>=2:require(c['driver_sha256']==r['inputs']['tests/fixtures/mydos/driver.inc'],'Undeclared parser driver')
        if r['schema_version']>=3:require(c['block_driver_sha256']==r['inputs']['tests/fixtures/block/driver.inc'],'Undeclared block driver')
        require(c['fixture_sha256']==r['media'][str(c['sector_bytes'])],'Mixed media')
        require(set(map(str,range(40,55))) - {'53'} <= set(c['phase_reads']),'Missing damage or encoding case')
        require(c['high_reads']==[360,32768,65535],'Missing maximum-sector coverage')
        require(c['request_count']<4096,'Unbounded file reads')
        if c['sector_bytes']==256:require(any(f.get('path')=='LARGE.BIN' and f.get('size')==70003 for f in c['cases']),'Missing large-file oracle')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')

def storage_sizes(image):
    """Read the compiler-emitted fixture size table, without a second layout model."""
    cell=next(d for d in image['data'] if '_STORAGESIZES_' in d['name'])
    memory={s['address']+i:v for s in image['segments'] for i,v in enumerate(s['bytes'])}
    raw=bytes(memory[cell['address']+i] for i in range(cell['size']))
    return [int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]


def collect():
    cases=[]
    for mode in ('raw','opt'):
        for size in (128,256):
            directory=ROOT/f'build/dos-slice6/final-{mode}{size}'
            c=compact(json.loads((directory/'results.json').read_text()))
            requests=c.pop('requests');c['request_count']=len(requests)
            c['request_trace_sha256']=hashlib.sha256(json.dumps(requests,sort_keys=True).encode()).hexdigest()
            c['phase_reads']=dict(collections.Counter(str(n['phase']) for n in requests))
            c['high_reads']=[n['sector'] for n in requests if n['phase']==60]
            image=json.loads((directory/'program.a816.json').read_text())
            c['storage_sizes']=storage_sizes(image)
            c['frames']={f['name']:f['local_stack_peak'] for f in image['routines'] if f['name'].startswith(('M_MYDOSFILE_','M_FSCORE_','M_FS83_'))}
            cases.append(c)
    r=dict(schema_version=5,status='pass',scope='Standalone file parser with sector-byte fixture provider and root caller in four-slot profile. No filesystem task, public DOS API, actual wire or physical-hardware claim.',inputs={p:sha256(ROOT/p) for p in INPUTS},cases=cases,
        media={str(s):sha256(ROOT/f'tests/fixtures/mydos/mydos450-{s}.atr') for s in (128,256)},
        compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text()),bank_zero=current(),
        storage=dict(fixed_upper_delta=0,per_open_cursor=cases[0]['storage_sizes'][1],cursor_heap=(cases[0]['storage_sizes'][1]+7)&~7,per_worker_operation=cases[0]['storage_sizes'][2],operation_heap=(cases[0]['storage_sizes'][2]+7)&~7,additional_tasks=0,additional_signals=0),
        limits=dict(host_seconds=600,frames=30000,requests=4096,max_chain_hops=65535,cycle_one_byte_calls=2001,cycle_hops=8,cycle_physical_reads=4),
        commands=[f'python3 tools/test_mydos_files.py --case {m} --size {s} --output build/dos-slice6/final-{m}{s}' for m in ('raw','opt') for s in (128,256)])
    validate(r);return r
if __name__=='__main__':
    (ROOT/'docs/qualification/mydos-files.json').write_text(json.dumps(collect(),indent=2)+'\n');print('Validated MyDOS file matrix')
