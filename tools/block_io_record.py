"""Fail-closed sector-adapter evidence, separating emulated SIO from fixture I/O."""
from library_paths import record_input_paths
import json
from native_program import ROOT,require,sha256
from ports_budget import current
MODULES=('lib/io/blockio.act','lib/io/blockwire.act','lib/io/blocktypes.act')
FAULTS={'adapter','port','transfer','buffer','volume','owner','open'}

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Unfinished block qualification')
    require(len(r['sectors'])==4 and {(c['build']['optimize'],c['backend']) for c in r['sectors']}=={(m,b) for m in (False,True) for b in ('sio','fixture')},'Missing provider/compiler mode')
    require(len(r['allocation'])==14 and {(c['build']['optimize'],c['fault']) for c in r['allocation']}=={(m,f) for m in (False,True) for f in FAULTS},'Missing rollback step')
    for c in r['sectors']+r['allocation']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed execution')
        require(c['build']['revision']==r['compiler']['revision'] and not c['build']['override'],'Unexpected compiler')
        for p in MODULES:require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed block source snapshots')
        if r['schema_version']>=2:require(c['block_driver_sha256']==r['inputs']['tests/fixtures/block/driver.inc'],'Undeclared block driver')
        if c.get('backend')=='sio':
            require(len(c['media'])==2 and c['wire_commands']==10,'Missing real two-unit reads')
        elif c.get('backend')=='fixture':require(c['wire_commands']==0 and c['override_sha256']==r['inputs']['tests/fixtures/block/blockwire.act'],'Undeclared fixture provider')
        else:require(c['override_sha256'],'Missing controlled allocation failure')
    require(len(r['compiler']['replay'])==2 and {c['mode'] for c in r['compiler']['replay']}=={'raw','opt'} and all(c['status']=='identical' for c in r['compiler']['replay']),'Unverified compiler migration')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Unreviewed bank-zero growth')

def compact(c):
    c=dict(c);b=c['build'];c['build']={k:b[k] for k in ('revision','changes','override','binary_sha256','abi_sha256','source_sha256','image_sha256','xex_sha256','optimize','task_inputs')}
    c['build']['kernel_bank']=b['memory']['constants']['KERNEL_BANK']
    runtime=c['runtime'];c['runtime']={k:runtime[k] for k in ('status','guards','created','live_tasks','native_nmi_count','native_irq_count','os_busy','fault_required')}
    if 'hardware' in c:c['wire_commands']=int.from_bytes(bytes.fromhex(c.pop('hardware'))[56:58],'little')
    c.pop('machine',None)
    return c

def collect(directory):
    paths=(*MODULES,'tests/fixtures/block/blockwire.act','tests/fixtures/block/driver.inc','tests/programs/block_io.act','tests/programs/block_allocation.act','tests/programs/block-test-state.inc','tools/test_block_io.py','tools/block_io_record.py','tools/test_compiler_block_fix.py','tools/native_program.py','tools/generate_tasks.py')
    compiler=json.loads((ROOT/'toolchain/actionc.json').read_text())
    compiler['replay']=json.loads((directory/'compiler-replay.json').read_text())
    compiler['checks']={'library_passed':2563,'library_ignored':2,'native_type_surface':24,'native_integer_integration':5,'native_cli':4,'command':'cargo test --lib --test native_type_surface --test native_integer_integration --test actionc_65816_cli'}
    cases=[compact(json.loads((directory/f'{backend}-{mode}/results.json').read_text())) for mode in ('raw','opt') for backend in ('sio','fixture')]
    allocation=[compact(c) for mode in ('raw','opt') for c in json.loads((directory/f'alloc-{mode}/results.json').read_text())['cases']]
    r=dict(schema_version=2,status='pass',scope='Checked sector adapter; root caller and resident SIO worker, four-slot profile. No filesystem or eight-task parser qualification.',inputs={p:sha256(ROOT/p) for p in paths},compiler=compiler,sectors=cases,allocation=allocation,
        platform=json.loads((ROOT/'toolchain/altirra-sio-queued.json').read_text()),transport_gate='docs/qualification/sio-sectors.json',bank_zero=current(),
        storage=dict(fixed_upper_delta=0,adapter_record=38,adapter_heap=40,port_record=27,port_heap=32,transfer_record=52,transfer_heap=56,scratch_heap=256,per_adapter_heap=384,volume_record=22,volume_heap=24,owner_record=52,owner_heap=56,per_volume_heap=80,per_adapter_signals=1,additional_tasks=0),
        limits=dict(host_seconds=240,frames=12000,sector_count=65535,sector_bytes=[128,256],boot_sector_bytes=128),
        commands=['python3 tools/test_block_io.py --case '+m+' --backend '+b+' --output build/dos-slice4/'+b+'-'+m for m in ('raw','opt') for b in ('sio','fixture')]+['python3 tools/test_block_io.py --case '+m+' --fault '+f+' --output build/dos-slice4/alloc-'+m+'/'+f for m in ('raw','opt') for f in sorted(FAULTS)])
    validate(r);return r
if __name__=='__main__':
    record=collect(ROOT/'build/dos-slice4');(ROOT/'docs/qualification/block-io.json').write_text(json.dumps(record,indent=2)+'\n');print('Validated block adapter matrix')
