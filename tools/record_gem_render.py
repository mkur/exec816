#!/usr/bin/env python3
"""Record the completed G4 development corpus and its focused controls."""
import json
import re
from pathlib import Path
from native_program import ROOT,require,sha256


def record():
    base=ROOT/'build/gem-vdi'
    names=['g4-final-'+p+m for p in ('','production-') for m in ('raw','opt')]
    runs={name:json.loads((base/name/'results.json').read_text()) for name in names}
    controls={name:json.loads((base/name/'results.json').read_text())
              for name in ('g4-final-display-raw','g4-final-display-opt')}
    of816=json.loads((base/'g4-of816-results.json').read_text())
    for name,r in {**runs,**controls,'of816':of816}.items():
        require(r['status']=='pass','Incomplete run: '+name)
    baseline=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
    audited={}
    observer_changes={}
    for name,r in runs.items():
        memory=r['build']['memory']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key]==baseline[key],'G4 changed '+key)
        sources={**r['provenance']['source_inputs'],**r['build']['platform_inputs'],**r['build']['task_inputs']}
        for path,digest in sources.items():
            actual=sha256(ROOT/path)
            if actual!=digest:
                require(path=='tools/test_gem_render.py','Target source changed after emission: '+path)
                observer_changes[name]=dict(path=path,at_build=digest,at_run=actual,
                    reason='Host-only scanout observer uses file transfer to avoid bridge response timeouts and compares the defined RGB channels, excluding the XRGB non-color byte; target code is unchanged.')
            audited[path]=actual
        require(r['test_harness_sha256']==sha256(ROOT/'tools/test_gem_render.py'),'Changed runner after final execution')
        image=json.loads((base/name/'c-image.json').read_text())
        require(image['provenance']==r['provenance'],'C provenance differs from run')
        workout=[0]*57
        for index,value in {0:639,1:239,3:372,4:372,5:1,6:1,7:1,10:1,13:16,14:1,15:1,25:3,35:1,37:1,39:16}.items(): workout[index]=value
        workout[45:53]=[8,8,8,8,1,0,1,0]
        for c in r['cases']:
            if c['op']==1: require(c['workout']==workout,'Workstation advertised unsupported capabilities')
            require(c['answer']==c.get('status',0),'Unexpected response in '+name)
            if c.get('status') in (1,2,3): require(c['completed']==0,'Rejected command claimed completion')
        require(any(c.get('scanout_sha256') for c in r['cases']),'No exact visible scene check')
    source_paths=[ROOT/'tools/record_gem_render.py',ROOT/'ports/gem4xe/selection.json',ROOT/'ports/gem4xe/inputs.json',
                  ROOT/'abi/gem-vdi.json',ROOT/'abi/display.json',ROOT/'toolchain/altirra-gem-vdi.json']
    audited.update({p.relative_to(ROOT).as_posix():sha256(p) for p in source_paths})
    host_log=base/'g4-host.log'
    host_text=host_log.read_text()
    require('OK (skipped=4)' in host_text,'Host checks incomplete')
    peak={}
    for r in runs.values():
        for slot,usage in r['stack_usage'].items():
            peak[slot]=max(peak.get(slot,0),usage['peak'])
    report=dict(format='exec816-gem-vdi-g4-development-v1',status='pass',date='2026-10-02',base_revision='314031c',
        tier='development',qualification=False,
        scope='Real selected GEM rendering through the G2 service and bounded G3 VBXE adapter; G5 combined renderer/peer/physical-SDFS workload remains pending.',
        bank_zero=dict(fixed_delta_bytes=0,per_public_task_delta_bytes=[0]*8,private_idle_delta_bytes=0,
            runtime_reserved_including_os_bytes=baseline['bank_zero_budget']['runtime_including_os'],
            budget=baseline['bank_zero_budget'],accounting='Full reservations include guards, alignment and unused stack/aperture capacity.'),
        cpu=dict(reserved_c_banks=[12,13],reserved_c_bytes=131072,dp_workspace_bytes=20,
            staging_page_used_bytes=4096,additional_reserved_bank_bytes=0,
            test_only_readback_heap_bytes=76800,test_only_font_copy_bytes=18432,
            upper_memory_note='C map entries include diagnostic fixture data and code. Production staging fits the already reserved complete data bank; no new CPU bank reservation.'),
        vram=json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text()),
        maximum_observed_stack_bytes=peak,
        observations=['Both compiler modes use exact source/ROM/emulator pins.',
            'Entire screen agrees byte-for-byte with two pixel oracles after each observed drawing operation.',
            'Visible scene scanout also agrees with pixels and the quantized hardware palette.',
            'All 256 glyphs, both font parities, clipped text, all pens, limits and cross-page operations are exercised.',
            'NMI saved S/D/PC is sampled inside selected GEM font code; all native guards and final restoration checks pass.',
            'One completed setter precedes a failing blit in the injected two-command batch; only that prefix is reported.',
            'Invalid batches have no drawing effect; close/reopen rebuilds defaults and clears pixels.',
            'Signed 13-bit stride boundary and invalid blit dimensions/extents are checked through emitted code.',
            'Bulk test readback temporarily borrows/restores unreserved $6000-$6FFF plus profile diagnostic code scratch with IRQ/NMI masked. This observer is not preemption qualification.',
            'Original hardware status reads run with snapshot/guard observers; G3 controls run the original C and mapping assembly.'],
        limitations=['Measured C stack peaks are path-specific; Calypsi adds no automatic frame checks.',
            'Synchronous single BCBs and the 4 KiB staging cache are correctness-first; no throughput/frame-rate claim.',
            'No AES, virtual workstations, external fonts, input, raster copies, GEMDOS or dynamic loader.',
            'No full hosted-system or real-hardware qualification.'],
        host_tests=dict(tests=int(re.search(r'Ran (\d+) tests',host_text)[1]),skipped=4,log_sha256=sha256(host_log)),
        generated_bindings=['display','gem-vdi','calypsi'],
        shared_c_bridge_and_elf_reader_changed=False,
        runs=runs,display_controls=controls,of816=of816,
        source_audit=audited,host_observer_changes_after_emission=observer_changes)
    path=ROOT/'docs/development/gem-vdi-g4.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('Recorded',len(runs),'G4 runs and',len(controls),'display controls:',path)
    return report

if __name__=='__main__': record()
