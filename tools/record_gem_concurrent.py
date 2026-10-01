#!/usr/bin/env python3
"""Freeze passing G5 evidence without rewriting earlier slice records."""
import json
from native_program import ROOT, require, sha256
from test_gem_concurrent import CASES


def record():
    base=ROOT/'build/gem-vdi'
    runs={}
    sources={}
    peaks={}
    for mode in ('raw','opt'):
        folder=base/('g5-final-'+mode)
        run=json.loads((folder/'results.json').read_text())
        require(run['status']=='pass' and not run['production'],'Incomplete '+mode)
        require([c['name'] for c in run['cases']]==CASES,'Missing G5 cases')
        require(run['harness_sha256']==sha256(ROOT/'tools/test_gem_concurrent.py'),'Changed runner')
        image=json.loads((folder/'c-image.json').read_text())
        inputs={**image['provenance']['source_inputs'],**run['build']['platform_inputs'],**run['build']['task_inputs']}
        for path,digest in inputs.items():
            require(sha256(ROOT/path)==digest or path=='tools/test_gem_concurrent.py','Changed build input: '+path)
        sources.update(inputs)
        require(sha256(folder/'program/program.xex')==run['xex_sha256'],'Changed XEX')
        for case in run['cases']:
            require(case['status']=='pass','Failed case')
            for slot,usage in case.get('stack_usage',{}).items():
                peaks[slot]=max(peaks.get(slot,0),usage['peak'])
        run['provenance']=image['provenance']
        run['observer_update']='The host runner checks root DP 8..15 only: the Action launcher legitimately uses its other lower-DP bytes. Both C workers preserve unused bytes 20..127; their live callee registers need not return to entry values before RemTask. Target code is unchanged.'
        runs[mode]=run
    log=base/'g5-host.log'
    require('OK (skipped=4)' in log.read_text(),'Host checks incomplete')
    sources['tools/record_gem_concurrent.py']=sha256(ROOT/'tools/record_gem_concurrent.py')
    report=dict(format='exec816-gem-vdi-g5-development-v1',status='pass',tier='development',
        date='2026-10-02',base_revision='95bc3f4',qualification=False,
        scope='Real selected VDI service, two large C Tasks, cold physical SDFS read and lifecycle failure cleanup.',
        bank_zero=dict(fixed_delta_bytes=0,per_public_task_delta_bytes=[0]*8,private_idle_delta_bytes=0,
            accounting='Complete reservations, including guards, alignment and unused capacity; compared to the larger-stack baseline.'),
        workload=dict(commands=12,glyphs=768,file_bytes=2048,task_capacity=8,
            large_stack_bytes=[2560,2560],public_task_upper_bound=6,
            text='Twelve 64-glyph rows at (64,24+16*row); glyph=32+(64*row+column)%96.',
            timing='Target VBI ticks from submit to exact collection, including physical read and diagnostic readback. Each service round trip is one request and one reply; DOS traffic is separate.',
            instrumentation='Only diagnostic builds substitute busy reads, count completed real blits, hash VRAM after the last command and wait on a host-released start rendezvous at borrowed $6000. No bank-zero production reservation is added.'),
        observations=['Both modes observe renderer and non-yielding peer progress between active physical IRQ samples with unchanged SIO terminal-post count.',
            'Cold metadata/data reads cannot be supplied by a warm cache; every file byte and nonzero native IRQ counts are checked.',
            'Full saved S/D/PC frames, deterministic peer checksum, lower DP patterns, stack/domain guards and stack headroom pass.',
            'Both large Tasks are admitted before small DOS/console workers; console stop acknowledgement precedes graphics acquisition.',
            'Accepted queued and active batches finish before STOP; the pending packet cannot be disposed before exact collection.',
            'Real heap exhaustion covers worker port/scratch, client port/packet and stop port/packet. Stop allocation failure preserves an active usable graphics session.',
            'Large-pool and root-signal exhaustion roll back and then successfully restart.',
            'Recoverable device failure invalidates the session and permits reopen; permanently busy hardware parks with live display, Task leases, port, scratch and pending request.',
            'Normal cases restore the CPU aperture, MEMAC, OS display and console; final allocator ownership equals the boot manifest.'],
        unchanged_prerequisites={name:sha256(ROOT/'docs/development'/name) for name in
            ('gem-vdi.json','gem-vdi-g1.json','gem-vdi-g2.json','gem-vdi-g3.json','gem-vdi-g4.json')},
        vram=json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text()),
        maximum_observed_stack_bytes=peaks,source_inputs=sources,runs=runs,
        host_checks=dict(tests=272,skipped=4,log_sha256=sha256(log)),
        limitations=['Measured workload and pinned emulator only; no general stack bound, full hosted qualification or physical hardware claim.',
            'No AES, input, desktop, GEMDOS, virtual workstations or concurrent GUI clients.',
            'Diagnostic timing includes readback; G6 records the optional artifact without these hooks.'])
    path=ROOT/'docs/development/gem-vdi-g5.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(path)

if __name__=='__main__': record()
