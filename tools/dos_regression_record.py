"""Fail-closed selected native regressions and retained transport/fault evidence."""
from library_paths import record_input_paths
import json
from native_program import ROOT,require,sha256
from ports_budget import current

NAMES=('heap','ports','io','signals','tasks','lists-named','lists-shared','loader3')
INPUTS=('tools/test_dos_regressions.py','tools/dos_client_regressions.py','tools/dos_regression_record.py','tools/sio_adapter_trace.py')

def compact(raw):
    c=dict(raw);b=c['build'];c['build']={k:b[k] for k in ('revision','override','source_sha256','image_sha256','xex_sha256','optimize','binary_sha256','abi_sha256','platform_inputs','banked_inputs','task_inputs') if k in b}
    c['build']['kernel_bank']=b['memory']['constants']['KERNEL_BANK']
    c['runtime']={k:v for k,v in c['runtime'].items() if k in ('status','guards','created','live_tasks','native_nmi_count','native_irq_count','vbi_dispatches','switches','os_busy','fault_required')}
    c.pop('machine',None)
    return c

def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass','Incomplete DOS regressions')
    require(len(r['cases'])==16 and {(c['build']['optimize'],c['name']) for c in r['cases']}=={(m,n) for m in (False,True) for n in NAMES},'Missing native regression')
    for c in r['cases']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Failed native regression')
        require(c['build']['revision']==r['compiler']['revision'] and not c['build']['override'],'Unpinned compiler')
        for group in ('task_inputs','platform_inputs','banked_inputs'):
            for p,h in c['build'].get(group,{}).items():
                if p!='platform/altirraos/sio.s':require(r['inputs'][p]==h,'Changed retained kernel policy '+p)
        if c['name']=='tasks':require(c['runtime']['created']>255,'Missing Task reuse')
        if c['name']=='loader3':require(c['build']['kernel_bank']==3,'Missing loader placement')
        if c['name']=='lists-shared':require(c['program']['pendingProof']==[1,0] and min(c['program']['sites'])>0,'Missing shared-list checkpoints')
    for name in ('transport','lifetime'):
        d=r['dependencies'][name]
        require(d['status']=='pass' and d['record_sha256'] and all(r['inputs'][p]==h for p,h in d['production_inputs'].items()),'Stale '+name+' dependency')
    require(r['dependencies']['lifetime']['client_reuse_modes']==['raw','opt'] and r['dependencies']['lifetime']['offline_modes']==[False,True],'Missing context/offline regressions')
    require(len(r['oracle_replay'])==4 and {(c['mode'],c['capacity']) for c in r['oracle_replay']}=={(m,n) for m in ('raw','opt') for n in (4,8)} and all(c['status']=='identical' for c in r['oracle_replay']),'Changed wire oracle')
    control=r['tx_negative_control']
    require(control['verdict']=='fail' and {'TX gap','late TX refill'}<=set(control['violations']) and control['tx_refill']['max_us']>=control['byte_deadline_us'],'Missed real deadline control')
    require(r['bank_zero']['fixed_delta']==r['bank_zero']['per_task_delta']==0,'Bank-zero growth')

def collect():
    base=ROOT/'build/dos-slice10';cases=[]
    for mode in ('raw','opt'):
        for name in NAMES:
            folder=base/(f'loader3-{mode}' if name=='loader3' else f'regressions-{mode}')/name
            path=folder/'results.json';raw=record_input_paths(json.loads(path.read_text()))
            require(raw['status']=='pass','Failed '+str(path))
            if name.startswith('lists-'):raw=dict(raw['observed'],name=name,status=raw['status'])
            c=compact(raw);c['result_sha256']=sha256(path);cases.append(c)
    from sio_sector_record import validate as transport_validate
    from dos_lifetime_record import validate as lifetime_validate
    dependencies={};inputs={p:sha256(ROOT/p) for p in INPUTS}
    for c in cases:
        for group in ('task_inputs','platform_inputs','banked_inputs'):
            for p,h in c['build'].get(group,{}).items():
                if p!='platform/altirraos/sio.s':
                    require(sha256(ROOT/p)==h,'Changed retained kernel input '+p);inputs[p]=h
    for name,filename,check in [('transport','sio-sectors.json',transport_validate),('lifetime','dos-lifetime.json',lifetime_validate)]:
        path=ROOT/'docs/qualification'/filename;record=record_input_paths(json.loads(path.read_text()));check(record)
        production={p:h for p,h in record['inputs'].items() if p.startswith(('lib/','platform/','abi/')) and not (name=='lifetime' and p=='platform/altirraos/sio.s')}
        for p,h in production.items():require(sha256(ROOT/p)==h,'Changed retained dependency '+p)
        inputs.update(production)
        dependencies[name]=dict(status=record['status'],record='docs/qualification/'+filename,record_sha256=sha256(path),production_inputs=production)
        if name=='lifetime':
            dependencies[name]['client_reuse_modes']=[c['mode'] for c in record['client_regressions']]
            dependencies[name]['offline_modes']=[c['build']['optimize'] for c in record['offline']]
    r=dict(schema_version=1,status='pass',scope='Selected emitted raw/optimized kernel regressions after DOS integration. DOS startup failures, unsafe two-unit queued failure and context reuse retain slice-9 evidence with identical filesystem/kernel policy sources. The later SIO ISR refinement is qualified separately by the refreshed full transport profiles/recovery matrix and new DOS concurrency matrix; individual retained cases keep their original SIO source/image hashes. No claim that the DOS fault cases run at eight simultaneous DOS tasks.',
           compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),platform=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text()),inputs=inputs,cases=cases,dependencies=dependencies,bank_zero=current(),
           oracle_replay=json.loads((base/'trace-oracle-replay.json').read_text()),
           tx_negative_control=json.loads((base/'tx-deadline-negative-control.json').read_text()),
           failed_experiments=['The first regression wrapper omitted the screen argument when checking the loader result. Seven preceding native cases per mode passed and were retained; loader checks were rerun with the corrected host call.'],
           commands=[f'python3 tools/test_dos_regressions.py --case {m} --suite heap,ports,io,signals,tasks,lists-named,lists-shared --output build/dos-slice10/regressions-{m}' for m in ('raw','opt')]+[f'python3 tools/test_dos_regressions.py --case {m} --suite loader3 --output build/dos-slice10/loader3-{m}' for m in ('raw','opt')])
    validate(r);return r

if __name__=='__main__':
    (ROOT/'docs/qualification/dos-regressions.json').write_text(json.dumps(collect(),indent=2)+'\n')
    print('Validated DOS integration regressions')
