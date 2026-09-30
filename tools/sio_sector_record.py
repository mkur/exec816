"""Validate and compact the 256-byte transport gate before publication."""
from library_paths import record_input_paths
import hashlib,json,re,subprocess
from os_boundary import require

PRODUCTION=('lib/io/siodriver.act','platform/altirraos/sio.s','abi/sio.json')
RECOVERY={'queued','preparing','active','terminal','absent','checksum','short','extra'}
SECTORS=[1,2,3,4,720,1024,32768,65535]
INPUTS=(*PRODUCTION,'tools/test_sio_sectors.py','tools/test_sio_concurrent.py','tools/sio_concurrent_trace.py','tools/sio_adapter_trace.py','tools/test_sio_recovery.py','tools/sector_images.py','tools/sio_sector_record.py','tests/programs/sio_sectors.act','tests/programs/sio_concurrent.act','tests/programs/sio_recovery.act','toolchain/altirra-sio-sectors.json','toolchain/patches/altirra-sio-sector-faults.patch','tests/test_sio_alarm_observer.py','tests/test_sio_command_trace.py')

def snapshot_inputs(root):
    return {path:hashlib.sha256((root/path).read_bytes()).hexdigest() for path in INPUTS}

def validate_current_inputs(record,root):
    require(record['inputs']==snapshot_inputs(root),'Qualification sources changed after execution')

def fresh_inputs(suites,root):
    inputs=snapshot_inputs(root)
    for suite in suites:
        require(suite.get('inputs')==inputs,'Missing or stale execution input snapshot')
    return inputs

def validate_historical_inputs(record,provenance,root,git_root=None):
    """Verify exact retained Git blobs, without asserting today's sources ran."""
    git_root=root if git_root is None else git_root
    require(provenance['schema_version']==1,'Unknown input provenance schema')
    require(provenance['record']=='docs/qualification/sio-sectors.json','Wrong historical record')
    require(hashlib.sha256((root/provenance['record']).read_bytes()).hexdigest()==provenance['record_sha256'],'Historical record changed')
    require(set(provenance['inputs'])==set(record['inputs']),'Incomplete historical input provenance')
    for path,digest in record['inputs'].items():
        item=provenance['inputs'][path]
        require(re.fullmatch('[0-9a-f]{40}',item['commit']) is not None and re.fullmatch('[0-9a-f]{40}',item['blob']) is not None,'Invalid Git identity')
        try:
            blob=subprocess.check_output(['git','rev-parse',f"{item['commit']}:{path}"],cwd=git_root,stderr=subprocess.PIPE,text=True).strip()
            data=subprocess.check_output(['git','cat-file','blob',item['blob']],cwd=git_root,stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            raise RuntimeError('Missing historical Git objects; fetch full history for '+path) from error
        require(blob==item['blob'] and hashlib.sha256(data).hexdigest()==digest==item['sha256'],'Historical input mismatch: '+path)

def validate(record):
    record=record_input_paths(record)
    require(record['schema_version']==1 and record['status']=='pass','Incomplete sector record')
    modes=set()
    for suite in record['suites']:
        require(suite['status']=='pass','Failed suite')
        mode=suite['optimize'];require(mode not in modes,'Duplicate mode');modes.add(mode)
        cases={c['name']:c for c in suite['cases']}
        require(set(cases)=={'boundaries','concurrent-4','concurrent-8','recovery','regression-0','regression-1','regression-2'},'Incomplete sector suite')
        for case in cases.values():
            require(case['status']=='pass' and case['build']['optimize']==mode,'Failed/mixed build')
            for name in PRODUCTION:
                require(case['build']['task_inputs'][name]==record['inputs'][name],'Stale sector input: '+name)
        b=cases['boundaries']
        require(b['sectors']==SECTORS and b['sector_bytes']==256 and b['runtime']['guards']=='intact','Missing boundary coverage')
        require(int.from_bytes(bytes.fromhex(b['hardware'])[56:58],'little')==8,'Unexpected wire requests')
        for capacity in (4,8):
            c=cases[f'concurrent-{capacity}'];o=c['observed'];t=c['timing']
            require(c['sector_size']==256 and c['speed']==0 and not c['fault'],'Wrong transport workload')
            count=(capacity-2)*6
            require(o['peakTasks']==capacity and o['peakOutstanding']>=2*(capacity-2),'Missing concurrency')
            require(o['submitted']==o['collected']==count and o['activeWork']>0,'Missing progress/completion')
            require(len(set(c['submission_order']))==count and sorted(c['submission_order'])==sorted(c['collection_order']),'Lost request identity')
            require(t['verdict']=='pass' and not t['violations'] and t['rx_bytes']==count*259,'Missing byte timing')
            require(t['rx_service']['max_us']<t['rx_byte_deadline_us'] and t['active_background_entries']>0,'Missed RX deadline/background work')
            require(c['key_during_active'] and c['replay']['status']=='identical','Missing IRQ/replay coverage')
            require(c['replay']['xex_sha256']==c['build']['xex_sha256'],'Replay changed image')
        recovery=cases['recovery']
        require(recovery['sector_size']==256 and {c['name'] for c in recovery['cases']}==RECOVERY,'Incomplete recovery matrix')
        for c in recovery['cases']:
            hardware=bytes.fromhex(c['hardware'])
            require(c['status']=='pass' and c['runtime']['guards']=='intact','Failed recovery')
            require(hardware[12:15]==hardware[16:19]==bytes(3),'Retained caller pointer')
        for speed in range(3):
            c=cases[f'regression-{speed}']
            require(c['runtime']['status']==0 and c['runtime']['guards']=='intact','Profile regression')
    require(modes=={False,True},'Missing raw/optimized execution')
    require(record['bank_zero']['fixed_delta']==record['bank_zero']['per_task_delta']==0,'Unreviewed bank-zero growth')

def compact(case):
    c=dict(case)
    b=c['build']
    c['build']={k:b[k] for k in ('revision','changes','override','binary_sha256','abi_sha256','abi_assembly_sha256','source_sha256','image_sha256','xex_sha256','optimize','task_inputs','platform_inputs')}
    c['build']['kernel_bank']=b['memory']['constants']['KERNEL_BANK']
    def runtime(r):
        return {k:r[k] for k in ('status','native_nmi_count','native_irq_count','os_busy','fault_required','switches','gateway_calls','os_calls','vbi_count','live_tasks','guards')}
    if 'runtime' in c:c['runtime']=runtime(c['runtime'])
    if 'cases' in c:
        c['cases']=[{**s,'runtime':runtime(s['runtime'])} for s in c['cases']]
    return c

if __name__=='__main__':
    import argparse
    from pathlib import Path
    from native_program import ROOT,sha256
    from ports_budget import current
    from sio_concurrent_trace import LIMITS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/qualification/sio-sectors.json')
    args=parser.parse_args()
    suites=[json.loads(p.read_text()) for p in args.input]
    inputs=fresh_inputs(suites,ROOT)
    for suite in suites:suite['cases']=[compact(c) for c in suite['cases']]
    record=dict(schema_version=1,status='pass',scope='Pinned emulated FASTEST125 READ: 128-byte boot sectors, 256-byte data sectors; no physical-hardware claim',
        inputs=inputs,bank_zero=current(),limits=LIMITS,suites=suites,
        commands=['python3 tools/test_sio_sectors.py --case '+('opt' if suite['optimize'] else 'raw')+' --suite --output '+str(path.parent.relative_to(ROOT) if path.is_absolute() else path.parent) for suite,path in zip(suites,args.input)],
        completion_limits=dict(boundaries_and_each_recovery=dict(host_seconds=240,frames=12000),concurrent=dict(host_seconds=600,frames=30000)),
        profile_pin='toolchain/altirra-sio-sectors.json',
        media='Deterministic ATRs; sectors 1-3 are 128 bytes, later sectors 256; byte i of sector s is (i XOR (s*15)) modulo 256. Boundary image has 65535 sectors; concurrent images have 720.',
        timing_scope='Kernel bank 1, four/eight public tasks. Passive observer plus identical uninstrumented replay. Masked duration includes idle SEI/WAI/CLI; RX arrival-to-service is the deadline metric.',
        storage=dict(fixed_bank_zero_delta=0,per_task_bank_zero_delta=0,fixed_upper_delta=0,per_client_buffer_bytes=512,sector_fixture_guarded_bytes=320))
    validate(record)
    validate_current_inputs(record,ROOT)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('Validated raw/optimized sector qualification')
