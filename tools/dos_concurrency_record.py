"""Require the complete native DOS geometry, capacity and placement matrix."""
import json
from itertools import product
from native_program import ROOT,require,sha256
from block_io_record import compact
from ports_budget import current,account
from sio_concurrent_trace import LIMITS

INPUTS=('tests/programs/dos_concurrent.act','tools/test_dos_concurrent.py','tools/dos_concurrent_trace.py','tools/dos_concurrency_record.py','tools/sio_adapter_trace.py','tools/sio_concurrent_trace.py','tools/sio_transaction_trace.py','tools/test_signal_concurrency.py','tools/test_dos_stack.py','tools/native_program.py','tools/generate_tasks.py','tools/generate_dos_mounts.py','tests/test_sio_command_trace.py','tests/test_dos_concurrent_trace.py')
MATRIX=set(product((False,True),(128,256),(4,8),(1,3)))

def validate(r):
    require(r['status']=='pass','Incomplete DOS concurrency')
    cases=r['matrix'];require(len(cases)==16 and {(c['build']['optimize'],c['sector_bytes'],c['capacity'],c['kernel_bank']) for c in cases}==MATRIX,'Missing compiler/geometry/capacity/placement')
    require(len(r['stock'])==2 and {c['build']['optimize'] for c in r['stock']}=={False,True},'Missing stock-speed regression')
    for c in cases+r['stock']:
        cap=c['capacity'];size=c['sector_bytes'];o=c['observed'];runtime=c['runtime']
        require(c['status']=='pass' and runtime['status']==0 and runtime['guards']=='intact' and runtime['live_tasks']==0 and not runtime['fault_required'],'Native failure or task leak')
        require(runtime['created']==cap-1,'Missing simultaneous worker/client admissions')
        require(runtime['native_nmi_count']>0 and c['vbi_dispatches']>0,'Missing OS/VBI coexistence')
        require(c['build']['revision']==r['compiler']['revision'] and not c['build']['override'],'Unpinned compiler')
        require(c['build']['source_sha256']==r['inputs']['tests/programs/dos_concurrent.act'],'Mixed workload')
        require(c['build']['kernel_bank']==c['kernel_bank'] and c['ordinary_dos'] and len(c['mounts'])==2,'Wrong packaging/placement')
        for p,h in c['build']['task_inputs'].items():require(r['inputs'][p]==h,'Mixed production input '+p)
        require(o['peakTasks']==cap and o['clientsDone']==cap-3,'Not simultaneously full')
        require(o['activeWork']>0 and o['heapRounds']==o['portRounds']==o['signalRounds']==o['workRounds']>0,'Missing background progress')
        require(o['totalBytes']==(cap-3)*801+(69226 if size==256 else 0),'Missing complete-file content verification')
        require(c['bus_released'] and c['ownership_restored'] and c['media_unchanged'],'Resource/media failure')
        require(c['media']==[r['fixtures'][str(size)]]*2,'Unqualified media')
        require(len(c['stacks'])==cap+1 and all(s['untouched_above_floor']>=0 for s in c['stacks']) and c['kernel_stack']['interrupt_reserve_bytes_touched']==0,'Interrupt headroom touched')
        require(c['bank_zero']==r['bank_zero']['after']['four' if cap==4 else 'eight'],'Bank-zero reservation mismatch')
        require(c['native_helper_active']==r['storage']['native_helper_active']<=r['storage']['native_helper_reserved'],'Native helper reservation exceeded')
        limit=c['limits'];require(limit['host_seconds']>0 and limit['sectors']==(1200 if size==256 else 512),'Missing finite limits')
        require(limit['guest_seconds']==int(limit['sectors']*((2 if c['speed'] else 1)+0.3)+60) and 0<c['wire_commands']<=limit['sectors'],'Workload completion bound')
        if c in r['stock']:require(size==128 and cap==8 and c['speed']==1 and c['timing'] is None,'Incorrect stock profile')
        else:require(c['speed']==0,'Wrong fast profile')
        if c['timing'] is not None:
            t=c['timing'];p=t['packets']
            require(c['kernel_bank']==1 and c['key_during_active'] and t['verdict']=='pass' and not t['violations'],'Failed observed timing')
            require(c['replay']['status']=='identical' and c['replay']['xex_sha256']==c['build']['xex_sha256'],'Missing unchanged replay')
            require(p['count']==21*(cap-3)+2 and len(p['caller_dps'])==cap-2,'Missing packet/caller correlation')
            require(t['active_background_entries']>0 and t['verified_file_bytes']==o['totalBytes'] and t['elapsed_seconds']<=limit['guest_seconds'],'Incomplete timed workload')
            require(t['rx_service']['max_us']<t['rx_byte_deadline_us'] and t['tx_refill']['max_us']<t['byte_deadline_us'] and t['rx_byte_deadline_us']<80,'Missed byte deadline')
            for name,bound in [('post_to_worker',LIMITS['post_to_worker_max_us']),('critic_deferral_bound',LIMITS['critic_max_us']),('forbid',LIMITS['forbid_max_us'])]:require(t[name]['max_us']<=bound,'Missed '+name+' bound')
            for alarm in t['alarms'].values():require(alarm['max_us']<=LIMITS['alarm_lateness_us'],'Late alarm')
            require(p['turnaround']['max_us']<=limit['guest_seconds']*1e6 and t['file_bytes_per_second']>0,'Unbounded packet time')
        elif c not in r['stock']:require(c['kernel_bank']==3,'Missing bank-1 timing')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')
    for name in ('transport','lifetime','regressions'):require(r['dependencies'][name]['status']=='pass','Missing '+name+' gate')

def case(path):
    raw=json.loads((path/'results.json').read_text());require(raw['status']=='pass','Failed '+str(path));c=compact(raw)
    c.update(stacks=raw['runtime']['stack_observations'],kernel_stack=raw['runtime']['kernel_stack_observation'],vbi_dispatches=raw['runtime']['vbi_dispatches'],
             bank_zero=account(raw['build']['memory']),ordinary_dos=raw['build']['dos_system'] and not raw['build']['dos_test'],mounts=raw['build']['dos_mounts'],
             ownership_restored=True,media_unchanged=True,result_sha256=sha256(path/'results.json'),native_helper_active=(path/'hosted.bin.signals').stat().st_size)
    h=bytes.fromhex(raw['hardware']);c['bus_released']=h[0]==h[1]==h[45]==0 and h[12:15]==h[16:19]==bytes(3)
    image=json.loads((path/'program.a816.json').read_text())
    selected=('M_FSWORKER_WORKER_','M_SIODRIVER_WORKER_','M_DOSCONCURRENT_CLIENTENTRY_','M_DOSCONCURRENT_OPENFILE_','M_DOSCLIENT_NEWCLIENT_')
    c['frames']=[{k:r[k] for k in ('name','fixed_frame','local_stack_peak')} for r in image['routines'] if r['name'].startswith(selected)]
    c.pop('marks',None)
    return c

def collect():
    base=ROOT/'build/dos-slice10';cases=[]
    for mode,size,cap,bank in product(('raw','opt'),(128,256),(4,8),(1,3)):
        folder=f'{mode}-{size}-{cap}-bank{bank}'
        cases.append(case(base/folder))
    stock=[case(base/f'stock-{mode}-128-8') for mode in ('raw','opt')]
    inputs={p:sha256(ROOT/p) for p in INPUTS}
    for c in cases+stock:
        for p,h in c['build']['task_inputs'].items():require(h==sha256(ROOT/p),'Stale built input '+p);inputs[p]=h
    from sio_sector_record import validate as validate_transport
    from dos_lifetime_record import validate as validate_lifetime
    from dos_regression_record import validate as validate_regressions
    dependencies={}
    for name,file,check in [('transport','sio-sectors',validate_transport),('lifetime','dos-lifetime',validate_lifetime),('regressions','dos-regressions',validate_regressions)]:
        path=ROOT/f'docs/qualification/{file}.json';v=json.loads(path.read_text());check(v)
        dependencies[name]=dict(status=v['status'],record=str(path.relative_to(ROOT)),record_sha256=sha256(path))
    r=dict(schema_version=1,status='pass',scope='Ordinary read-only DOS on independent original-MyDOS images, real emulated POKEY/SIO; eight simultaneously live tasks are root, FS, SIO and five applications. Bank 1 observes serial/packet timing and replays each identical image without instrumentation; bank 3 is functional-only. Physical hardware and filesystem writes are unqualified.',
           compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text()),inputs=inputs,
           fixtures={str(size):sha256(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr') for size in (128,256)},matrix=cases,stock=stock,dependencies=dependencies,bank_zero=current(),
           storage=dict(fixed_upper_delta=0,service_reserved=96,service_active=90,worker_heap=760,per_mount_heap=200,per_client_heap=104,per_file_or_lock_heap=112,worker_signals=2,client_signals=1,test_static_upper=2272,native_helper_reserved=8192,native_helper_active=6484,native_helper_active_delta=39),
           limits=dict(transport=LIMITS,serial_target_baud=125000,actual_rx_period_base_cycles=140,sd_sector_bound=512,dd_sector_bound=1200,derivation='Each finite fixture path/chain plus all queued whole operations fits the sector bound. Every sector allows the 1s FASTEST125 or 2s STOCK810 active deadline plus 0.3s preparation/recovery and 60s total CPU/setup margin. Packet turnaround is bounded conservatively by the full workload. Host watchdogs are separate from guest and wire acceptance.',stack='Touched-byte watermarks are lower-bound observations, combined with native frame/domain and DP/stack guard checks. The existing 256-byte interrupt reserve is retained.'),
           failed_experiments=['Initial raw client fixture nested lazy DOS creation beneath larger helper frames and tripped the native stack guard. Splitting selection, open, readiness and directory phases reduced the test call chain; production stack reservations and interrupt headroom were unchanged.','The first raw eight-task SD trace completed all file assertions but refilled one command byte exactly 140 base cycles after ready, idling the shifter for one bit. The alarm handler now checks TX-ready once after starting a transfer, avoiding a full IRQ return/re-entry. The oracle groups COMMAND by its line edges so the idle edge cannot omit the late refill from statistics. The original trace remains a rejecting control. The complete final matrix is rebuilt after the fix.','Restarting an ad-hoc host queue initially reused several still-active output directories. Those runs and artifacts were discarded, all stale processes stopped, and a new queue refuses existing output directories. No reused-directory result is accepted.'],
           commands=[f'python3 tools/test_dos_concurrent.py --case {m} --size {s} --capacity {c} --bank {b} '+('--trace --key ' if b==1 else '')+f'--output build/dos-slice10/{m}-{s}-{c}-bank{b}' for m,s,c,b in product(('raw','opt'),(128,256),(4,8),(1,3))]+[f'python3 tools/test_dos_concurrent.py --case {m} --size 128 --capacity 8 --speed 1 --output build/dos-slice10/stock-{m}-128-8' for m in ('raw','opt')])
    validate(r);return r

if __name__=='__main__':
    (ROOT/'docs/qualification/dos-concurrency.json').write_text(json.dumps(collect(),indent=2)+'\n')
    print('Validated complete DOS concurrency matrix')
