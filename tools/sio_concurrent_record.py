"""Fail closed when publishing concurrent SIO qualification."""
from library_paths import record_input_paths
from os_boundary import require


def validate(record):
    record=record_input_paths(record)
    require(record['schema_version']==1 and record['status']=='pass','Incomplete record')
    timing=set();functional=set();faults=set()
    for case in record['cases']:
        require(case['status']=='pass','Failed workload')
        b=case['build'];o=case['observed'];capacity=o['peakTasks']
        for name in ('lib/io/siodriver.act','platform/altirraos/sio.s','abi/sio.json'):
            require(b['task_inputs'][name]==record['inputs'][name],'Stale production input: '+name)
        require(capacity in (4,8) and o['submitted']==o['collected']==(capacity-2)*6,'Missing concurrent workload')
        require(o['peakOutstanding']>=2*(capacity-2),'Missing outstanding-client barrier')
        require(o['heapRounds']==o['registryRounds']==o['portRounds']==o['signalRounds']==o['workRounds']>0,'Missing background work')
        require(len(set(case['submission_order']))==o['submitted'] and sorted(case['submission_order'])==sorted(case['collection_order']),'Lost/duplicate request')
        bank=b['memory']['constants']['KERNEL_BANK'];mode=b['optimize']
        key=(capacity,mode,bank)
        if case['fault']:
            faults.add((capacity,mode,case['fault']))
            require(case['timing'] is None,'Fault run presented as normal timing')
        else:
            functional.add(key)
            require((case['speed']==2 or o['activeWork']>0) and case['runtime']['status']==0,'No active progress/clean exit')
            if case['timing']:
                require(case['timing']['verdict']=='pass' and not case['timing']['violations'],'Failed timing')
                require(case['replay']['status']=='identical','Missing unchanged-image replay')
                require(case['timing']['active_background_entries']>0,'Missing active background execution')
                require(case['key_during_active'],'Missing unowned keyboard IRQ')
                timing.add((capacity,mode,bank,case['speed']))
    require(timing=={(c,m,1,s) for c in (4,8) for m in (False,True) for s in (0,1,2)},'Incomplete timing matrix')
    require(functional=={(c,m,b) for c in (4,8) for m in (False,True) for b in (1,3)},'Incomplete bank/capacity matrix')
    require(faults=={(8,m,f) for m in (False,True) for f in ('queued','timeout')},'Incomplete functional fault matrix')
    require({c['name'] for c in record['negative_controls'] if c['status']=='rejected'}=={'rx','tx','phase'},'Missing failing timing controls')
    require(record['bank_zero']['fixed_delta']==record['bank_zero']['per_task_delta']==0,'Unreviewed bank-zero growth')


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    from native_program import ROOT,sha256
    from ports_budget import current
    from sio_concurrent_trace import LIMITS
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',action='append',type=Path,required=True)
    p.add_argument('--controls',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'docs/qualification/sio-concurrency.json')
    args=p.parse_args()
    paths=['tools/test_sio_concurrent.py','tools/sio_concurrent_trace.py','tools/sio_concurrent_record.py',
           'tools/sio_concurrent_faults.py','tests/programs/sio_concurrent.act','platform/altirraos/sio.s',
           'lib/io/siodriver.act','abi/sio.json','toolchain/altirra-sio-queued.json']
    record=dict(schema_version=1,status='pass',scope='Emulated queued SIO; kernel-bank-1 timing, kernel-bank-3 functional only',
        limits=LIMITS,bank_zero=current(),diagnostic_upper_reserved_bytes=512,
        inputs={p:sha256(ROOT/p) for p in paths},
        cases=[json.loads(p.read_text()) for p in args.input],
        negative_controls=json.loads(args.controls.read_text()),
        control_scope='Edited real observations test the RX/TX/phase deadline oracles; emitted IRQ-stall/overrun is in io-sio-regressions.json.',
        completion_limits=dict(frame_limit=30000,host_timeout_seconds=600),
        masked_scope='Resident and active intervals include idle SEI/WAI/CLI time while no IRQ is pending; actual arrival-to-service measurements include wake latency.',
        critic_scope='sio_start entry to sio_retire entry conservatively contains actual CRITIC ownership; observed maxima, not universal worst-case proofs.',
        media='Two disposable 720-sector ATRs: sector s byte i = i XOR (s*15), reduced to 8 bits; writes checked by subsequent reads.',
        profiles={'0':'FASTEST125 READ/PUT, 128 bytes','1':'STOCK810 READ/PUT, 128 bytes','2':'Happy1050 NONE/QUIET only'})
    validate(record)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('Validated',len(record['cases']),'concurrent qualification cases')
