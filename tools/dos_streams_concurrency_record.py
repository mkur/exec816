#!/usr/bin/env python3
"""Freeze the seven-workload DOS streams timing/capacity qualification."""
from image_data_usage import used as image_data_used
from library_paths import record_input_paths
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import account
from sio_concurrent_trace import LIMITS
from sio_transaction_trace import BASE_HZ
NAMES={'target128-raw','target128-opt','target256-raw','target256-opt','stock128-opt','bank3-raw','bank3-opt'}


def guards(rt):
    require(rt['status']==0 and rt['guards']=='intact','Failed native execution')
    require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel interrupt reserve touched')
    require(rt['stack_observations'] and all(s['untouched_above_floor']>=0 for s in rt['stack_observations']),'Task interrupt reserve touched')


def validate(r):
    r=record_input_paths(r)
    require(r['status']=='pass' and len(r['cases'])==7 and {c['name'] for c in r['cases']}==NAMES,'Incomplete streams timing matrix')
    for c in r['cases']:
        require(c['compiler_revision']==r['compiler']['revision'] and not c['override'],'Wrong compiler')
        require(c['optimize']==c['name'].endswith('-opt'),'Missing raw/optimized coverage')
        require(c['bank_zero']==r['baseline_bank_zero'],'Bank-zero reservation changed')
        require(c['kernel_bank']==(3 if c['name'].startswith('bank3') else 1),'Wrong kernel bank')
        live=c['case'];guards(live['runtime'])
        expected=70003 if c['name'].startswith('target256') else 777
        require(live['sector_bytes']==(256 if expected==70003 else 128) and live['speed']==int(c['name'].startswith('stock')),'Wrong media/speed matrix')
        for execution in [live]+([c['replay']] if c['replay'] else []):
            guards(execution['runtime']);counts=execution['counters']
            require(counts['expected']==counts['verified']==expected,'Wrong complete file payload')
            require(counts['collected']==counts['visible']==8 and counts['duringRead']>0,'Missing concurrent keyboard')
            require(counts['allocations']==counts['signals']==counts['messages'] and counts['allocations']>0 and counts['floods']==30,'Missing independent work')
            require(execution['runtime']['created']==7,'Unexpected worker creation')
            require(len(execution['observations'])==3 and all(o['live']==8 and o['created']==7 and len(o['contexts'])==8 and all(o['contexts']) for o in execution['observations'][:2]),'Eight live Tasks not demonstrated')
        if not c['name'].startswith('bank3'):
            require(c['replay'] and c['replay']['schedule']==live['schedule'],'Missing identical input replay')
            require(c['replay']['observations'][-1]['screen_sha256']==live['observations'][-1]['screen_sha256'],'Replay display changed')
            t=c['timing'];require(t['verdict']=='pass' and not t['violations'],'Failed byte/timing oracle')
            require(t['deadline_misses']==dict(rx=0,tx=0,tx_gaps=0),'Serial deadline miss')
            deadline=(930 if c['name'].startswith('stock') else 140)/BASE_HZ*1e6
            require(abs(t['rx_byte_deadline_us']-deadline)<.00001,'Baud deadline changed')
            require(t['forbid']['max_us']<=LIMITS['forbid_max_us'],'Forbid limit changed')
            for alarm in t['alarms'].values():
                require(all(v['max_us'] is None or v['max_us']<=100 for v in alarm.values()),'Alarm/watchdog limit changed')
            s=c['stream_timing'];require(s['endpoint_forbid']['count']==103,'Missing endpoint lifetime/transfer intervals')
            require(s['endpoint_forbid']['max_us']<=t['forbid']['max_us']+.00001,'Incorrect endpoint Forbid attribution')
            require(s['active_cpu_masked_max'] and s['active_idle_masked_max'],'Mask work/idle classification missing')
    require(len(r['tx'])==2 and {v['mode'] for v in r['tx']}=={'raw','opt'},'Missing TX qualification')
    for tx in r['tx']:
        require(len(tx['cases'])==2 and tx['cases'][0]['schedule']==tx['cases'][1]['schedule'],'Missing TX replay')
        for c in tx['cases']:guards(c['runtime'])
        t=tx['cases'][0]['timing'];require(t['verdict']=='pass' and not t['violations'],'Failed TX byte oracle')
        require(LIMITS['write_delay_us'][0]<=t['write_delay_us']<=LIMITS['write_delay_us'][1],'TX turnaround changed')
    require(len(r['overhead'])==2 and {v['mode'] for v in r['overhead']}=={'raw','opt'},'Missing call-cost comparison')
    for cost in r['overhead']:
        require(len(cost['cases'])==2,'Missing overhead replay')
        for c in cost['cases']:
            guards(c['runtime']);require(c['counts']==dict(edges=40,writes=18),'Incomplete fixed overhead workload')
        for api in ('Direct','Dos'):
            for stage,n in (('Open',1),('First',1),('Steady',8)):
                require(cost['cases'][0]['timing'][api][stage]['count']==n,'Missing overhead samples')
    controls=r['negative_controls']
    require(controls['status']=='pass' and {c['name'] for c in controls['cases']}=={'missing-key','late-rx','wrong-payload'},'Missing timing/payload controls')
    require(all(c['expected_violation'] in c['violations'] for c in controls['cases']),'Corrupted observation accepted')
    require(r['bank_zero_fixed_delta']==r['bank_zero_per_task_delta']==0,'Bank-zero growth')
    require(r['recovery']['status']=='pass' and r['recovery']['current_production_inputs_match'],'Stale recovery reference')


def collect(out):
    baseline=json.loads((ROOT/'docs/qualification/dos-streams-raw.json').read_text())
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
        platform_pin=json.loads((ROOT/'toolchain/altirra-console.json').read_text()),baseline_bank_zero=baseline['baseline_bank_zero'],
        bank_zero_fixed_delta=0,bank_zero_per_task_delta=0,inputs={},cases=[],tx=[],overhead=[],
        scope='Eight live Tasks plus idle: public DOS RAW streams, physical keys/display, single MyDOS Read, memory/messages/signals; bank-1 byte timing and identical replay, bank-3 functionality, direct transport TX and fixed direct-Exec/DOS cost comparison.')
    def provenance(b):
        for name,digest in {**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs']}.items():
            require(sha256(ROOT/name)==digest,'Production source changed: '+name);r['inputs'][name]=digest
        require(b['revision']==r['compiler']['revision'] and not b['override'],'Unqualified compiler')
        require(account(b['memory'])==r['baseline_bank_zero'],'Bank-zero reservation changed')
    for name in sorted(NAMES):
        p=out/name/'results.json';v=json.loads(p.read_text());require(v['status']=='pass','Incomplete '+name)
        b=v['build'];provenance(b)
        for path,digest in v['source_inputs'].items():
            require(sha256(ROOT/path)==digest,'Workload source changed: '+path);r['inputs'][path]=digest
        image=json.loads((p.parent/'program.a816.json').read_text())
        near=image_data_used(image,b['memory'])
        traces={str(f.relative_to(ROOT)):sha256(f) for f in (p.parent/'observed/trace.log',) if f.exists()}
        r['cases'].append(dict(name=name,compiler_revision=b['revision'],override=b['override'],optimize=b['optimize'],kernel_bank=b['memory']['constants']['KERNEL_BANK'],
            image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],source_sha256=b['source_sha256'],bank_zero=account(b['memory']),near_image_used=near,
            case=v['case'],replay=v.get('replay'),timing=v.get('timing'),stream_timing=v.get('stream_timing'),marks=v['marks'],limits=v['limits'],
            traces=traces,result_path=str(p.relative_to(ROOT)),result_sha256=sha256(p)))
    for group in ('tx','overhead'):
        for mode in ('raw','opt'):
            p=out/(group+'-'+mode+('-final' if group=='overhead' else ''))/'results.json';v=json.loads(p.read_text());require(v['status']=='pass','Incomplete '+group)
            b=v['build'];provenance(b)
            require(b['optimize']==(mode=='opt'),'Wrong TX/cost compiler mode')
            r[group].append(dict(mode=mode,image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],source_sha256=b['source_sha256'],
                cases=v['cases'],limits=v['limits'],scope=v.get('scope'),result_path=str(p.relative_to(ROOT)),result_sha256=sha256(p)))
    p=out/'qualified-controls/results.json';r['negative_controls']=json.loads(p.read_text());r['negative_controls']['result_sha256']=sha256(p)
    path=ROOT/'docs/qualification/dos-streams-lifetime.json';previous=record_input_paths(json.loads(path.read_text()))
    require(previous['status']=='pass','Recovery qualification did not pass')
    for name,digest in previous['inputs'].items():
        if name.startswith(('lib/','platform/','abi/')):require(sha256(ROOT/name)==digest,'Recovery production input changed: '+name)
    r['recovery']=dict(status='pass',record='docs/qualification/dos-streams-lifetime.json',sha256=sha256(path),current_production_inputs_match=True,
        scope='Slice-5 raw/optimized real 128/256-byte fault responders with live RAW endpoints; unchanged admission/teardown/transport production sources.')
    for name in ('tests/programs/dos_streams_overhead.act','tools/test_dos_streams_overhead.py','tools/test_dos_streams_concurrent.py',
                 'tools/test_dos_streams_trace.py','tools/dos_streams_timing.py','tools/console_concurrent_trace.py','tools/dos_streams_concurrency_record.py'):
        r['inputs'][name]=sha256(ROOT/name)
    validate(r);return r

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('directory',type=Path);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    require(not args.output.exists(),'Keep existing evidence');args.output.write_text(json.dumps(collect(args.directory.resolve()),indent=2)+'\n')
    print('Recorded passing DOS streams concurrency')
