"""Require complete emitted mount-lifetime, publication and rollback evidence."""
from library_paths import library_relative, record_input_paths
import json
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current
from test_dos_startup import VARIANTS
MODULES=tuple(library_relative(n) for n in ('fsboot.act','fsinit.act','fsmount.act','fsmux.act','fsmanager.act','fshandler.act','fsio.act','fsnames.act','fstypes.act','task-dos.inc','dosclient.act','doscalls.act','blockio.act'))
ARCHIVAL_MODULES=MODULES+('lib/io/task-sio.inc',)
MODULES+=('lib/io/sio-lifetime.inc','lib/exec/task-lifetime.inc','lib/fs/fsworker.act','lib/console/consoledriver.act')
ARCHIVAL_BACKEND_MODULES=('lib/fs/fsformats.act','lib/fs/fsbtypes.act','lib/fs/fsbackend.act','lib/mydos/fsmydos.act')
BACKEND_MODULES=ARCHIVAL_BACKEND_MODULES[:-1]+('lib/mydos/mydos.act','lib/mydos/mydostypes.act')
INPUTS=(*MODULES,*BACKEND_MODULES,'lib/io/siodriver.act','tests/programs/sio_deadline_ticks.act','tools/test_sio_deadline_ticks.py','tools/native_program.py','tools/generate_tasks.py','tools/generate_dos_mounts.py','config/dos-mounts.json','tools/test_dos_lifetime.py','tools/test_dos_startup.py','tools/test_dos_capacity.py','tools/test_dos_offline.py','tools/test_dos_publication.py','tools/dos_lifetime_record.py','platform/altirraos/sio.s','tools/sio_concurrent_trace.py','tests/programs/dos_service_lifetime.act','tests/programs/dos_mount_retry.act','tests/programs/dos_startup_fail.act','tests/programs/dos_capacity.act','tests/programs/dos_offline.act','tests/programs/dos_no_mounts.act','tests/programs/dosfaultcontrol.act','examples/dos-read.act','examples/dos-directory.act')
# Historical records retain their exact startup matrix. Fresh collectors also
# require only allocations that still exist after the MyDOS record migration.
ARCHIVAL_STARTUP=('service','admission','adapter','reply-port','transfer','buffer','workspace','operation','arrival','control-port','mount','parser-volume','block-volume','mount-port','owner','device-open','metadata-read','format','generation','duplicate-alias','duplicate-unit')
def validate(r):
    r=record_input_paths(r)
    require(r.get('schema_version') in (1,2,3,4,5),'Unknown DOS lifetime schema')
    variants=ARCHIVAL_STARTUP if r['schema_version']==1 else ARCHIVAL_STARTUP+('cancel-signal',) if r['schema_version']==2 else ARCHIVAL_STARTUP+('cancel-signal','backend-work','backend-volume') if r['schema_version']<5 else VARIANTS
    require(r['status']=='pass','Incomplete DOS lifetime')
    require(len(r['startup'])==2*len(variants) and {(c['build']['optimize'],c['fault']) for c in r['startup']}=={(m,f) for m in (False,True) for f in variants},'Missing startup failure')
    require(len(r['capacity'])==4 and {(c['build']['optimize'],c['application_children']) for c in r['capacity']}=={(m,n) for m in (False,True) for n in (6,7)},'Missing admission pressure')
    require(len(r['lifetime'])==6 and {(c['build']['optimize'],c['variant']) for c in r['lifetime']}=={(m,v) for m in (False,True) for v in ('auto','stop','retry')},'Missing mount/shutdown case')
    require(len(r['publication'])==6 and {(c['build']['optimize'],c['name']) for c in r['publication']}=={(m,n) for m in (False,True) for n in ('empty','read','directory')},'Missing ordinary application')
    require(len(r['offline'])==2 and {c['build']['optimize'] for c in r['offline']}=={False,True},'Missing offline mode')
    for group in ('startup','capacity','lifetime','publication','offline'):
        for c in r[group]:
            require(c['status']=='pass' and c['runtime']['guards']=='intact','Failed native execution')
            for p in (MODULES if r['schema_version']>=4 else ARCHIVAL_MODULES)+(BACKEND_MODULES if r['schema_version']>=5 else ARCHIVAL_BACKEND_MODULES if r['schema_version']>=3 else ()):require(c['build']['task_inputs'][p]==r['inputs'][p],'Mixed lifetime implementation: '+p)
            require(c['build']['revision']==r['compiler']['revision'] and not c['build']['override'],'Unpinned compiler')
            require(c['runtime']['status']==(0xff93 if group=='offline' else 0),'Wrong platform outcome')
            require(all(s['untouched_above_floor']>=0 for s in c['stacks']) and c['kernel_stack']['interrupt_reserve_bytes_touched']==0,'Interrupt headroom touched')
            if group!='offline':require(c['runtime']['live_tasks']==0,'Retained service/client task')
            else:
                require(c['checks']==[15],'Incomplete offline assertions')
                require(c['reset_required'] and c['hardware_offline'] and c['borrowed_pointers_clear'],'Unsafe platform return/buffer retention')
            if group=='startup':require(c['checks']==[8],'Missing retry and resource checks')
            if group=='publication' and c['name']=='empty':require(c['runtime']['created']==0,'Eager filesystem worker')
    require(r['transport']['status']=='pass' and all(r['transport']['inputs'][p]==r['inputs'][p] for p in ('lib/io/siodriver.act','platform/altirraos/sio.s','tools/sio_concurrent_trace.py')),'Stale transport refresh')
    require(len(r['arithmetic'])==2 and {c['build']['optimize'] for c in r['arithmetic']}=={False,True} and all(c['status']=='pass' and c['cases']>1400 and c['runtime']['guards']=='intact' and c['build']['task_inputs']['lib/io/siodriver.act']==r['inputs']['lib/io/siodriver.act'] for c in r['arithmetic']),'Missing deadline rounding evidence')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')
    require(len(r['client_regressions'])==2 and all(c['status']=='pass' for c in r['client_regressions']),'Missing context reuse regression')

def case(path):
    raw=json.loads((path/'results.json').read_text());require(raw['status']=='pass','Failed '+str(path));c=compact(raw)
    c['stacks']=raw['runtime']['stack_observations'];c['kernel_stack']=raw['runtime']['kernel_stack_observation']
    c['result_sha256']=sha256(path/'results.json')
    if 'hardware' in raw:
        h=bytes.fromhex(raw['hardware']);c['hardware_offline']=h[0]==h[45]==1;c['borrowed_pointers_clear']=h[12:15]==h[16:19]==bytes(3)
        c['reset_required']=raw['runtime'].get('platform_reset_required',False)
    return c

def collect():
    base=ROOT/'build/dos-slice9'
    startup=[case(base/f'final-startup-{m}-{f}') for m in ('raw','opt') for f in VARIANTS]
    capacity=[case(base/f'final-capacity-{m}-{n}') for m in ('raw','opt') for n in (6,7)]
    lifetime=[dict(case(base/f'final-lifetime-{m}-{v}'),variant=v) for m in ('raw','opt') for v in ('auto','stop','retry')]
    publication=[case(base/f'final-public-{m}-{n}') for m in ('raw','opt') for n in ('empty','read','directory')]
    offline=[case(base/f'final-offline-{m}') for m in ('raw','opt')]
    regressions=[]
    for m in ('raw','opt'):
        p=base/f'client-{m}'/'results.json';v=json.loads(p.read_text());require(v['status']=='pass','Failed context regression')
        reuse=next(c for c in v['cases'] if c['case']=='reuse');require(reuse['runtime']['created']>255,'Missing repeated task reuse')
        regressions.append(dict(mode=m,status=v['status'],created=reuse['runtime']['created'],result_sha256=sha256(p)))
    transport=json.loads((ROOT/'docs/qualification/sio-sectors.json').read_text())
    from sio_sector_record import validate as check_transport
    check_transport(transport)
    arithmetic=[case(base/f'deadlines-{m}') for m in ('raw','opt')]
    r=dict(schema_version=5,status='pass',scope='Ordinary read-only MyDOS publication, explicit mounts, two-unit lifecycle and unsafe serial-fault cleanup. Eight-slot stack layout; full eight-live-task DOS timing is the next gate.',inputs={p:sha256(ROOT/p) for p in INPUTS},compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text()),transport=dict(status=transport['status'],inputs=transport['inputs'],record_sha256=sha256(ROOT/'docs/qualification/sio-sectors.json')),arithmetic=arithmetic,startup=startup,capacity=capacity,lifetime=lifetime,publication=publication,offline=offline,client_regressions=regressions,bank_zero=current(),
       storage=dict(fixed_upper_delta=0,fixed_service_reserved=96,fixed_service_active=96,worker_signals=4,client_signals=1,foreground_scope_payload=44,foreground_scope_allocated=48,foreground_signals=1),
       limits=dict(startup_host_seconds=240,startup_frames=12000,lifetime_host_seconds=600,lifetime_frames=30000,serial_byte_us=80),
       lifecycle='All filesystem heap, ports, signals, objects and owning bindings are released. An already-started global SIO worker retains its existing warm lifetime until the last application exits; FS cleanup precedes SIO retirement. Unsafe SIO parks with status 0xff93 and requires platform reset.',
       transport_gate='docs/qualification/sio-sectors.json',
       source_scope='Filesystem/policy sources match across the lifecycle matrix. Each case retains its exact SIO source/image hashes. Later IRQ and deadline-preparation optimizations are qualified by the refreshed complete transport matrix and every timeout-quotient boundary; they do not alter filesystem ownership/rollback policy.',
       failed_experiments=['The refreshed raw eight-task transport measured 220827.30106191474 us post-to-next-start against 200000 us. Replacing the bounded linear timeout calculation with nine binary-division steps preserves rounding and reduces the measured maximum to 179322.1958924637 us; both modes also pass 1488 quotient-boundary cases.','Refreshed optimized eight-task transport first measured 101.99061432605137 us watchdog latency against its unchanged 100 us bound. The IRQ now skips disabled sources before slow POKEY reads; the previously failing image shape then measured 91.20653416579854 us. Full transport evidence is refreshed separately. The alarm oracle also distinguishes a ROM-induced temporary-enable edge cancelled after 0.5638734724315211 us; it still rejects the original late ISR.','Copied fault modules initially omitted an absolute include path; corrected before execution acceptance.','An initial raw offline test combined too many calls on its child stack and faulted before fault injection. Separating test phases restored the existing 256-byte interrupt reserve; no production stack reservation was enlarged.'],
       commands=[f'python3 tools/test_sio_deadline_ticks.py --case {m} --output build/dos-slice9/deadlines-{m}' for m in ('raw','opt')]+[f'python3 tools/test_dos_startup.py --case {m} --fault {f} --output build/dos-slice9/final-startup-{m}-{f}' for m in ('raw','opt') for f in VARIANTS]+[f'python3 tools/test_dos_lifetime.py --case {m} '+({'auto':'--auto ','stop':'','retry':'--retry '}[v])+f'--output build/dos-slice9/final-lifetime-{m}-{v}' for m in ('raw','opt') for v in ('auto','stop','retry')]+[f'python3 tools/test_dos_offline.py --case {m} --output build/dos-slice9/final-offline-{m}' for m in ('raw','opt')])
    validate(r);return r
if __name__=='__main__':
    (ROOT/'docs/qualification/dos-lifetime.json').write_text(json.dumps(collect(),indent=2)+'\n');print('Validated DOS lifetime and publication')
