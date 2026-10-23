#!/usr/bin/env python3
"""Time the exact packaged split XEX through CONFIG up to native entry."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

from fujinet_pc_peer import FujiNetPC
from native_program import ROOT,read_build,require,sha256
from os_boundary import emulator
from test_fujinet_xex import XexBoot
from test_of816 import boot_environment


def run(bundle,output,firmware,manual=False,fault=None):
    output.mkdir(parents=True,exist_ok=True)
    media=output/'media';media.mkdir(exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as z:
        for name in ('Exec-of816.xex','system.atr','work.atr'):
            (media/name).write_bytes(z.read('exec816-demo/'+name))
    monitor=json.loads((bundle/'of816/of816.json').read_text());pin,binary,rom=boot_environment(monitor)
    require(sha256(media/'Exec-of816.xex')==monitor['xex_sha256'],'Packaged XEX differs')
    program=read_build(bundle)
    mounts=[(1,media/'Exec-of816.xex',True),(2,media/'system.atr',True),(8,media/'work.atr',False)]
    boot=XexBoot(bundle,output,menu=True,manual=manual);start=time.monotonic()
    with FujiNetPC(output/'peer',media/'Exec-of816.xex',firmware,mounts=mounts,configuration_menu=True,
                   fault=fault,fault_query=3) as peer:
        boot.peer=peer
        with emulator(binary,rom,output/'emulator',pin=pin) as b:
            for k,v in [('diskemu','generic56k'),('siopatch','off'),('burstio','false'),('fastboot','false')]:b.config(k,v)
            b.device_set('custom',path=str(peer.script),hotreload=False,allowunsafe=True)
            if fault:
                try:boot(b,program)
                except RuntimeError:
                    l=monitor['boot_sio']['labels']
                    cause=b.eval_expr('@a')&255
                    require(cause==0x8f and b.eval_expr('@xpc')==l['reader_failed'],'Incorrect post-monitor failure')
                    require(b.peek(program['build']['memory']['constants']['ENTERED'])==b'\0','Entered failed native image')
                    boot.report.update(post_monitor_failure=cause,native_entered=False)
                else:raise RuntimeError('Fault did not stop the load')
            else:boot(b,program)
    require(not peer.error,str(peer.error))
    relay=json.loads((output/'peer/relay.json').read_text())
    if fault:require(relay['fault_events'],'Post-monitor fault not exercised')
    result=dict(status='pass',tier='development',qualification=False,boot=boot.report,
                canonical_sha256=monitor['canonical_xex_sha256'],xex_sha256=monitor['xex_sha256'],
                policy=monitor['boot_sio']['policy'],host_elapsed_seconds=time.monotonic()-start,
                guest_seconds=boot.report.get('native_handoff_frame',0)/50,
                relay=relay,manual=manual,rom_sha256=sha256(rom),
                emulator_sha256=sha256(binary/'AltirraBridgeServer'),firmware_sha256=sha256(firmware),
                scope='CONFIG and exact native image/context/guard handoff; Tasks/filesystem/EXIT are covered separately')
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('relay','boot')},flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fujinet-pc',type=Path,default=Path.home()/'atari/fujinet-firmware/build/fujinet');p.add_argument('--manual',action='store_true')
    p.add_argument('--fault',choices=('read-checksum',));a=p.parse_args()
    run(a.bundle.resolve(),a.output.resolve(),a.fujinet_pc.resolve(),a.manual,a.fault)
