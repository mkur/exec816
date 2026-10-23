#!/usr/bin/env python3
"""Freeze focused boot-only SIO evidence without a qualification claim."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from build_boot_fast import INPUTS
from native_program import ROOT,require,sha256


def record(directory,destination):
    directory=directory.resolve();demo=directory/'demo';atr=directory/'atr-demo'
    monitor=json.loads((demo/'of816/of816.json').read_text())
    manifest=json.loads((demo/'demo-manifest.json').read_text())
    native=json.loads((demo/'build.json').read_text())
    selected={'split_save':directory/'final-split/results.json',
              'split_manual_reboot':directory/'final-split/reboot-results.json',
              'standard':directory/'final-standard/results.json',
              'first_auto':directory/'full-auto/results.json',
              'first_standard':directory/'full-standard/results.json',
              'atr_save':atr/'atr-fujinet-boot-results.json',
              'atr_reboot':atr/'atr-fujinet-reboot-results.json',
              'reader':directory/'reader-final-all/results.json',
              'errors':directory/'errors-final/results.json',
              'direct':directory/'direct-final/results.json',
              'post_monitor_error':directory/'post-monitor-error/results.json',
              'manual_forth':directory/'manual-complete/results.json'}
    for i in (1,2):
        for policy in ('standard','auto'):
            selected[f'cohort_{i}_{policy}']=directory/f'cohort-{i}-{policy}/results.json'
    for i in range(1,5):selected[f'nmi_{i}']=directory/f'nmi-{i}-delivery/results.json'
    evidence={};values={}
    def summarize(value):
        result={k:value[k] for k in ('status','case','cause','frame','pages','callbacks','nmi_point','guards',
                'policy','canonical_sha256','xex_sha256','boot','xex_boot','atr_boot','persisted',
                'media_before','work_after','initial_media_sha256','media_sha256',
                'boot_code_locator_and_protection','scope') if k in value}
        if 'cases' in value:result['cases']=[summarize(c) for c in value['cases']]
        relay=value.get('relay',value.get('firmware',value.get('fujinet_pc',{})).get('relay'))
        if relay is not None:
            require(relay['error'] is None,'Transport error')
            result['transport']=dict(commands=dict(Counter(str(c['command']) for c in relay['commands'])),
                endpoint_rates=dict(Counter(f"{c['host_baud']}/{c['peripheral_baud']}" for c in relay['commands'])),
                rate_mismatches=sum(bool(c['rate_mismatch']) for c in relay['commands']),
                faults=relay['fault_events'],scope=relay['scope'])
        return result
    for name,path in selected.items():
        value=json.loads(path.read_text());require(value['status']=='pass','Incomplete: '+name)
        values[name]=value;evidence[name]=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),summary=summarize(value))
    saved,reboot,standard=(values[k] for k in ('split_save','split_manual_reboot','standard'))
    require(saved['media_before']['Exec-of816.xex']==monitor['xex_sha256']==reboot['media_before']['Exec-of816.xex'],'Changed split boot image')
    require(reboot['media_before']['work.atr']==saved['work_after'] and reboot['persisted'],'Split persistence was not continuous')
    require(standard['canonical_sha256']==monitor['canonical_xex_sha256'],'Unmatched timing payloads')
    require(values['atr_save']['initial_media_sha256']==sha256(atr/'of816/exec816.atr'),'Changed packaged ATR')
    require(saved['media_before']['system.atr']==sha256(demo/'system.atr'),'Changed packaged SYS')
    require(values['atr_reboot']['initial_media_sha256']==values['atr_save']['media_sha256'],'ATR persistence was not continuous')
    host=(directory/'host-final.log').read_text();tests=re.search(r'Ran (\d+) tests',host)
    require(tests and host.rstrip().endswith('OK'),'Host suite incomplete')
    files=list(INPUTS)+['tools/record_boot_fast.py','tools/test_boot_fast.py','tools/test_boot_fast_errors.py',
        'tools/test_boot_fast_direct.py','tools/measure_boot_fast.py','tools/test_disk_boot_reader.py',
        'tools/test_fujinet_xex.py','tools/test_bootable_atr.py','tools/boot_forth_check.py',
        'tools/fujinet_pc_peer.py','tools/test_of816.py','probes/boot-sio/forth-status.s',
        'tools/build_demo.py','tools/build_of816.py','tools/package_demo.py','tools/package_fastbasic_source.py',
        'toolchain/actionc.json','toolchain/altirra.json','toolchain/of816.json',
        'docs/reference/boot-loading.md','docs/reference/platform.md',
        'docs/guides/fujinet-split-boot.md','docs/guides/bootable-system-atr.md',
        'docs/history/boot-only-fast-sio.md','docs/plans/boot-only-fast-sio-implementation-plan.md',
        'docs/fujinet-split-distribution.txt','docs/bootable-atr-distribution.txt']
    fw=Path(saved['firmware']['path'])
    fw_root=fw.parent.parent
    fw_sources=('lib/bus/sio/sio.cpp','lib/bus/sio/NetSIO.cpp','lib/device/sio/disk.cpp')
    rom_sources=Path.home()/'atari/AltirraSDL/src/Kernel/source/Shared'
    result=dict(format='exec816-boot-only-fast-sio-development-v1',date='2026-10-23',status='pass',
        tier='development',qualification=False,source_inputs={n:sha256(ROOT/n) for n in files},
        evidence=evidence,host=dict(tests=int(tests[1]),log_sha256=sha256(directory/'host-final.log')),
        compiler={k:native[k] for k in ('revision','override','binary_sha256','optimize')},
        canonical=dict(bytes=(demo/'of816/Exec-core.xex').stat().st_size,sha256=monitor['canonical_xex_sha256']),
        reader=monitor['boot_sio'],rom=monitor['rom'],emulator_pin=manifest['pin'],
        configuration=manifest['configuration'],
        firmware=dict(binary_sha256=sha256(fw),revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=fw_root,text=True).strip(),
            configuration=(directory/'final-split/peer/fnconfig.ini').read_text(),
            protocol_sources={n:sha256(fw_root/n) for n in fw_sources}),
        rom_protocol_sources={n:sha256(rom_sources/n) for n in ('interrupt.s','interrupt816.s','syscall816.s','sio.s')},
        performance=dict(standard_frames=standard['boot']['native_handoff_frame'],
            auto_frames=saved['xex_boot']['native_handoff_frame'],
            full_boot_ratio=standard['boot']['native_handoff_frame']/saved['xex_boot']['native_handoff_frame'],
            limitations='Guest PAL time includes CONFIG, prefix, negotiation, OF816 and interleaved transfer/decode. Host waits pause emulation; no physical UART claim.'),
        artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha256(p)) for p in
            (demo/'exec816-demo.zip',demo/'of816/Exec-of816.xex',demo/'system.atr',atr/'exec816-demo.zip',atr/'of816/exec816.atr')},
        physical_uart_qualified=False,release_matrix_run=False)
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=ROOT/'build/boot-fast')
    p.add_argument('--output',type=Path,default=ROOT/'docs/development/boot-only-fast-sio.json');a=p.parse_args()
    record(a.directory,a.output.resolve())
