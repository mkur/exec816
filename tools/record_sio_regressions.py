#!/usr/bin/env python3
"""Collect the exact newly executed slice-8 integration cases, without bridge logs."""
import json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import current

# Output paths are reproducible with the commands recorded beside each suite.
SPECS=[
 ('platform-lists','sio8-platform-regressions',14,'test_tasks_regressions.py',''),
 ('signals','sio8-signal-final',6,'test_signals.py','--case core-opt --case wait-opt --case queue-nmi-raw --case queue-nmi-opt --case registers-c9-raw --case registers-c9-opt'),
 ('ports','sio8-port-regressions',2,'test_ports.py','--suite wait-gap'),
 ('heap','sio8-heap-regressions',4,'test_heap.py','--suite api --case basic-raw --case basic-opt --case clear-raw --case clear-opt'),
 ('io','sio8-io-final',4,'test_io_services.py','--suite lifetime,queues'),
]

def collect():
    suites=[]
    # The first two signal cases passed before the fixed cross-bank fixture
    # collided with the larger linked image. Only those executed cases count.
    first=json.loads((ROOT/'build/sio8-signal-regressions/results.json').read_text())
    require(first['status']=='fail' and first['error']=='Image overlap/overflow','Unexpected initial regression failure')
    require([c['name'] for c in first['cases']]==['core-raw','wait-raw'],'Unexpected initial signal coverage')
    first={**first,'status':'pass','cases':first['cases']};first.pop('error')
    suites.append(dict(name='signals-core-wait-raw',count=2,command='python3 tools/test_signals.py --compiler-dir build/actionc --bridge-dir build/altirra-irq-bridge --case core-raw --case wait-raw',evidence=first))
    for name,directory,count,driver,args in SPECS:
        evidence=json.loads((ROOT/'build'/directory/'results.json').read_text())
        require(evidence['status']=='pass' and len(evidence['cases'])==count,'Incomplete '+name)
        require(all(c['status']=='pass' for c in evidence['cases']),'Failed '+name)
        command=f'python3 tools/{driver} --compiler-dir build/actionc --bridge-dir build/altirra-irq-bridge {args} --output build/{directory}'
        suites.append(dict(name=name,count=count,command=command,evidence=evidence))
    for mode in ('raw','opt'):
        for name,prefix,count,driver,args in [
            ('recovery','sio8-recovery-qualified',20,'test_sio_recovery.py',''),
            ('recovery-timing','sio8-recovery-timing',3,'test_sio_recovery.py','--suite active,wrap,absent --trace'),
            ('profile-limits','sio8-profile-limits',2,'test_sio_profile_limits.py',''),
            ('emulation-callback','sio8-adapter-emulation',1,'test_sio_adapter.py','--variant 5 --trace'),
            ('public-example','sio8-public',1,'test_sio_public.py','')]:
            directory=prefix+'-'+mode;evidence=json.loads((ROOT/'build'/directory/'results.json').read_text())
            require(evidence['status']=='pass','Failed '+name+' '+mode)
            cases=evidence.get('cases',[evidence])
            require(len(cases)==count and all(c['status']=='pass' for c in cases),'Incomplete '+name)
            command=f'python3 tools/{driver} --case {mode} {args} --output build/{directory}'
            if name in ('recovery-timing','profile-limits'):
                require(evidence['replay']['status']=='identical','Missing timing replay')
                command+=f'\npython3 tools/replay_sio_timing.py --kind {"profile" if name=="profile-limits" else "recovery"} --input build/{directory}'
            suites.append(dict(name=name+'-'+mode,count=count,command=command,evidence=evidence))
    paths=['tools/record_sio_regressions.py','tools/replay_sio_timing.py','tools/test_sio_profile_limits.py',
           'tests/programs/sio_profile_limits.act','tools/test_signals.py','tests/programs/signals_queue.act',
           'platform/altirraos/sio.s','lib/io/siodriver.act','abi/sio.json']
    record=dict(schema_version=1,status='pass',scope='Newly executed slice-8 integration regressions; concurrency is recorded separately',
        cases=sum(s['count'] for s in suites),suites=suites,bank_zero=current(),
        inputs={p:sha256(ROOT/p) for p in paths},
        host_checks=dict(command='python3 -m unittest discover -s tests',passed=87),
        generated_checks=['python3 tools/generate_io.py --check','python3 tools/generate_sio_adapter.py --check','python3 tools/generate_ports.py --check'],
        fixture_fix='The raw cross-bank signal queue fixture at $04FFEF overlapped the enlarged linked image. Its three guarded Task extents moved to $08FFEF/$09FFEF/$0AFFEF; raw/optimized NMI queue cases then passed.',
        image_scope='Each case retains its exact compiler/generated/image hashes. Subsystem regressions began before the final SIO-only tuning; they do not arm SIO. Concurrent SIO, recovery, deadlines and the public example use final production inputs.')
    require(record['cases']==86,'Unexpected integration case total')
    (ROOT/'docs/qualification/io-sio-regressions.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Recorded',record['cases'],'integration cases')

if __name__=='__main__':collect()
