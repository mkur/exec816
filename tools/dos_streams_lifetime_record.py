#!/usr/bin/env python3
"""Freeze slice 5 execution evidence and reject incomplete ownership gates."""
from image_data_usage import used as image_data_used
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import account
NAMES={'lifetime-bank1','lifetime-bank3','console-only','stream-removal-guard','headless',
       'serial-128','serial-256','direct-console-clean','direct-console-guard','filesystem-lifetime','filesystem-retry'}
FAULTS={'checksum':0,'device':0,'short':0xff93,'firstcause':0xff93,'framing':0xff93,'protocol':0xff93}


def validate(r):
    require(r['status']=='pass' and len(r['cases'])==22 and
        {(c['mode'],c['name']) for c in r['cases']}=={(m,n) for m in ('raw','opt') for n in NAMES},'Incomplete lifetime matrix')
    for c in r['cases']:
        require(c['bank_zero']==r['baseline_bank_zero'],'Bank-zero reservation changed')
        require(c['compiler_revision']==r['compiler']['revision'] and not c['override'],'Unqualified compiler')
        expected=4 if c['name'] in ('stream-removal-guard','direct-console-guard') else 0
        runtimes=[c['runtime']] if c['runtime'] else [x['runtime'] for x in c['faults']]
        if c['name'].startswith('serial-'):
            require({x['name'] for x in c['faults']}==set(FAULTS),'Missing causal serial fault')
            for x in c['faults']:
                unsafe=bool(FAULTS[x['name']])
                require(x['status']=='pass' and x['runtime']['status']==FAULTS[x['name']],'Wrong causal fault outcome')
                cleanup=x['runtime']['streams_cleanup']
                require(cleanup['unsafe_retained']==unsafe,'Unsafe shutdown misreported as cleanup')
                registry=bytes.fromhex(cleanup['registry']);instance=bytes.fromhex(cleanup['console_instance'])
                require(registry[0]==(2 if unsafe else 0) and bool(int.from_bytes(registry[1:4],'little'))==unsafe,
                        'Wrong endpoint lifetime on shutdown')
                require(bool(int.from_bytes(instance[:3],'little'))==unsafe,'Wrong console lifetime on shutdown')
                hardware=bytes.fromhex(x['hardware'])
                require(hardware[45]==int(unsafe) and hardware[12:15]==hardware[16:19]==bytes(3),'Retained serial caller pointers')
                require(int.from_bytes(hardware[56:58],'little')==(1 if unsafe else 2),'Lost/duplicate terminal post')
        else:require(c['runtime']['status']==expected,'Wrong lifetime result')
        for rt in runtimes:
            require(rt['guards']=='intact','Damaged lifetime guards')
            require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel reserve touched')
            require(all(s['untouched_above_floor']>=0 for s in rt['stack_observations']),'Task reserve touched')
        if c['name'] in ('lifetime-bank1','lifetime-bank3','console-only'):
            require(c['checks']['childChecks']==3 and c['checks']['checks']=={'lifetime-bank1':170,'lifetime-bank3':172,'console-only':144}[c['name']],'Incomplete lifetime assertions')
            require(c['checkpoints']==[1,2,6,5,3,4,3,3],'Missing deterministic race checkpoint')
            require(set(c['hooks'])=={'dosraw','doscalls'},'Missing private hook hashes')
            require(c['kernel_bank']==(3 if c['name']=='lifetime-bank3' else 1),'Missing kernel-bank coverage')
            require(c['runtime']['created']=={'lifetime-bank1':6,'lifetime-bank3':7,'console-only':4}[c['name']],'Unexpected worker count')
        if c['name']=='headless':
            o=c['observations'];require(o['checks']==41 and o['no_payload_access'] and o['access_negative_control']=='stopped','Missing headless gate')
        if c['name']=='stream-removal-guard':
            require(c['checks']==dict(checks=1,childChecks=0),'Stream removal failed before opening its handle')
    require(r['bank_zero_fixed_delta']==r['bank_zero_per_task_delta']==0,'Bank-zero growth')


def collect(out):
    report=json.loads((out/'results.json').read_text());require(report['status']=='pass','Incomplete run')
    baseline=json.loads((ROOT/'docs/qualification/dos-streams-raw.json').read_text())
    r=dict(schema_version=1,status='pass',suite='lifetime',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
        baseline_bank_zero=baseline['baseline_bank_zero'],bank_zero_fixed_delta=0,bank_zero_per_task_delta=0,
        scope='Deterministic private checkpoint/failure fixtures, real console lifetime and filesystem regressions; real 128/256-byte fault responders with an open RAW endpoint, safe cleanup versus unsafe retention.',
        inputs={},cases=[],result_path=str(out.relative_to(ROOT)/'results.json'),result_sha256=sha256(out/'results.json'))
    for item in report['cases']:
        path=ROOT/item['result'];result=json.loads(path.read_text());require(result['status']=='pass','Failed case')
        b=result['build']
        for name,digest in {**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Source changed: '+name);r['inputs'][name]=digest
        image=json.loads((path.parent/'program.a816.json').read_text())
        near=image_data_used(image,b['memory'])
        r['cases'].append(dict(mode=item['mode'],name=item['name'],compiler_revision=b['revision'],override=b['override'],
            image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],source_sha256=b['source_sha256'],
            kernel_bank=b['memory']['constants']['KERNEL_BANK'],bank_zero=account(b['memory']),near_image_used=near,
            runtime=result.get('runtime'),faults=result.get('cases'),machine=result.get('machine'),
            checks=result.get('checks'),checkpoints=result.get('checkpoints'),hooks=result.get('hooks'),observations=result.get('observations'),
            limits=result.get('limits'),result_path=item['result'],result_sha256=sha256(path),generated=b.get('task_generated')))
    for name in ('tests/programs/dstreamprobe.act','tests/programs/dos_streams_lifetime.act',
                 'tools/test_dos_streams_lifetime.py','tools/test_dos_streams_lifetime_suite.py','tools/dos_streams_recovery.py','tools/dos_streams_lifetime_record.py'):
        r['inputs'][name]=sha256(ROOT/name)
    validate(r);return r

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('directory',type=Path);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    require(not args.output.exists(),'Keep existing evidence');args.output.write_text(json.dumps(collect(args.directory.resolve()),indent=2)+'\n')
    print('Recorded passing DOS stream lifetime gate')
