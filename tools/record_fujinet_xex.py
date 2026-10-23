#!/usr/bin/env python3
"""Freeze split-media FujiNet/PicoBoot development evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

from native_program import ROOT,require,sha256


def record(directory,destination):
    demo=directory/'demo';evidence={}
    for name,path in [('cold',directory/'cold/results.json'),
                      ('menu_reboot',directory/'cold/reboot-results.json'),
                      ('errors',directory/'errors/results.json')]:
        value=json.loads(path.read_text());require(value['status']=='pass','Incomplete '+name)
        summary={k:value[k] for k in ('xex_boot','persisted','media_before','work_after','cases') if k in value}
        if 'runtime' in value:
            require(value['runtime']['guards']=='intact','Native guards changed')
            summary.update(guards='intact',machine=value['machine'],rom=value['rom'])
            relay=value['firmware']['relay'];require(relay['error'] is None,'Relay failure')
            summary['firmware']=dict(path=value['firmware']['path'],sha256=value['firmware']['sha256'],
                scope=relay['scope'],commands=dict(Counter(str((c['device'],c['command'])) for c in relay['commands'])),
                bit_cycles=dict(Counter(str(c['bit_cycles']) for c in relay['commands'])))
        evidence[name]=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),summary=summary)
    cold=evidence['cold']['summary'];reboot=evidence['menu_reboot']['summary']
    require(reboot['xex_boot']['configuration_menu_option_boot'],'CONFIG was bypassed')
    require(reboot['media_before']['work.atr']==cold['work_after'],'WORK was reset before reboot')
    manifest=json.loads((demo/'demo-manifest.json').read_text());native=manifest['kernel']
    monitor=json.loads((demo/'of816/of816.json').read_text())
    for summary in (cold,reboot):
        require(summary['media_before']['Exec-of816.xex']==sha256(demo/'of816/Exec-of816.xex') and
                summary['media_before']['system.atr']==sha256(demo/'system.atr'),
                'Final boot/system images differ from tested media')
    require(monitor['boot_config']['system_drive']==2,'Wrong default system drive')
    host=(directory/'host.log').read_text();tests=re.search(r'Ran (\d+) tests',host)
    require(tests and host.rstrip().endswith('OK'),'Host checks incomplete')
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
    inputs={n.decode():sha256(ROOT/n.decode()) for n in names
            if n and (ROOT/n.decode()).is_file() and ROOT/n.decode()!=destination}
    result=dict(format='exec816-fujinet-split-xex-development-v1',date='2026-10-22',
        status='pass',tier='development',qualification=False,source_inputs=inputs,evidence=evidence,
        native=dict(revision=native['revision'],override=native['override'],optimized=native['optimize'],
                    compiler_sha256=native['binary_sha256'],build_sha256=sha256(demo/'build.json'),
                    c_reuse='Renderer and applications reused after input/product hash checks; native kernel and commands rebuilt'),
        host=dict(tests=int(tests[1]),log_sha256=sha256(directory/'host.log')),
        artifacts={n:dict(sha256=sha256(demo/n),bytes=(demo/n).stat().st_size)
                   for n in ('of816/Exec-of816.xex','system.atr','work.atr','exec816-demo.zip')},
        pin=manifest['pin'],mounts=manifest['mounts'],boot_config=monitor['boot_config'],
        guide_refresh=manifest.get('guide_refresh'),
        firmware_log_sha256=sha256(directory/'cold/peer/firmware.log'),
        firmware_config=(directory/'cold/peer/fnconfig.ini').read_text(),
        menu_snapshot_sha256=sha256(directory/'cold/menu-before-option.altstate2'),
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,per_public_task=[0]*12,idle=0,
            includes='Guards, alignment and unused capacity'),
        bank_zero_budget=native['memory']['bank_zero_budget'],
        loader=dict(reserved_bytes=4608,used_bytes=(demo/'loader.bin').stat().st_size,used_delta=96),
        source_archive='build/fujinet-split/exec816-fastbasic-source.zip; companion checksum and source-rebuild/results.json excluded to avoid self-hash cycles',
        limits=['Development checks, not full qualification','No physical hardware or UART timing qualification',
                'Original unnumbered user failure not reproduced under the pinned ROM/configuration'])
    destination.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=ROOT/'build/fujinet-split')
    p.add_argument('--output',type=Path,default=ROOT/'docs/development/fujinet-xex-boot.json')
    a=p.parse_args();record(a.directory.resolve(),a.output.resolve())
