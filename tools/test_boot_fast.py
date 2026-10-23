#!/usr/bin/env python3
"""Emitted split-XEX takeover and independently paced real-firmware SIO."""
import argparse
import json
from pathlib import Path
import struct
import time

from build_boot_fast import wrap,segment
from fujinet_pc_peer import FujiNetPC
from native_program import ROOT,require,sha256
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import boot_environment


def fixture(output,policy='auto',pages=16,native_divisor=40,local=False,nmi_point=0):
    output.mkdir(parents=True,exist_ok=True)
    canonical=output/'canonical.xex'
    canonical.write_bytes(b'\xff\xff'+segment(0x6100,bytes.fromhex('ee0063d003ee016360'))+
        segment(0x6300,b'\0\0')+
        (b'\xff\xff'+segment(0x6400,bytes(range(256)))+segment(0x2e2,struct.pack('<H',0x6100)))*pages+
        segment(0x6200,bytes.fromhex('4c0062'))+segment(0x2e0,struct.pack('<H',0x6200)))
    record=wrap(canonical,output/'boot.xex',output/'reader',None,policy,native_divisor=native_divisor,callbacks=[0x6100] if local else None,options={'BOOT_NMI_POINT':nmi_point})
    return record


def run(output,bundle,firmware,policy='auto',pages=16,index=8,local=False,nmi_point=0):
    r=fixture(output,policy,pages,local=local,nmi_point=nmi_point);labels=r['labels']
    monitor=json.loads((bundle/'of816/of816.json').read_text());pin,binary,rom=boot_environment(monitor)
    with FujiNetPC(output/'peer',output/'boot.xex',firmware,readonly=True,hsio_index=index) as peer:
        with emulator(binary,rom,output/'emulator',pin=pin) as b:
            for k,v in [('diskemu','generic56k'),('siopatch','off'),('burstio','false'),('fastboot','false')]:b.config(k,v)
            b.device_set('custom',path=str(peer.script),hotreload=False,allowunsafe=True)
            b.cold_reset()
            try:wait_at(b,0x6200,(labels['reader_failed'],labels['reader_park']),180)
            except Exception:
                b.state_save(str(output/'failure.altstate2'))
                (output/'failure.json').write_text(json.dumps(dict(regs=b.regs(),state={k:b.peek(v)[0] for k,v in labels.items() if k.startswith(('bo_','reader_','take_'))}),indent=2)+'\n')
                raise
            if nmi_point:require(b.peek(labels['bo_nmi_done'])==b'\1','NMI checkpoint did not execute')
            require(b.peek(labels['take_selected'])==b'\1','PicoBoot fallback concealed a failed takeover')
            require(b.peek16(0x6300)==pages and b.peek16(labels['reader_callbacks'])==pages,'Incorrect callback count')
            require(b.memdump(0x6400,256)==bytes(range(256)),'Wrong final bytes')
            require(b.peek16(labels['bo_new_vectors'])!=b.peek16(0x20a),'Boot serial vector survived handoff')
            for k in ('reader_guard_low','reader_guard_high'):require(b.memdump(labels[k],16)==b'\xa5'*16,'Reader guard changed')
            r.update(status='pass',tier='development',qualification=False,pages=pages,index=index,
                     frame=b.eval_expr('@frame'),callbacks=b.peek16(labels['reader_callbacks']),guards='intact',engine={k:b.peek(v)[0] for k,v in labels.items() if k.startswith(('boot_index','boot_fast_fail','boot_query_error','bo_waittype','bo_txindex'))})
    require(not peer.error,str(peer.error))
    r['relay']=json.loads((output/'peer/relay.json').read_text())
    bulk=[c for c in r['relay']['commands'] if c['device']==0x31 and c['command']==0x52 and c['aux']>=371+r['prefix_bytes']//253]
    if policy=='auto' and index==8:
        require(bulk and all(c['host_baud']==57600 and not c['rate_mismatch'] for c in bulk),'Auto concealed standard-speed bulk loading')
    r['local_callbacks']=local
    r['nmi_point']=nmi_point

    (output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print({k:r[k] for k in ('status','pages','frame','callbacks','guards')},flush=True)
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bundle',type=Path,default=ROOT/'build/fujinet-split/demo');p.add_argument('--fujinet-pc',type=Path,default=Path.home()/'atari/fujinet-firmware/build/fujinet')
    p.add_argument('--policy',choices=('standard','auto'),default='auto');p.add_argument('--pages',type=int,default=16);p.add_argument('--index',type=int,default=8);p.add_argument('--local',action='store_true');p.add_argument('--nmi-point',type=int,choices=range(5),default=0)
    a=p.parse_args();run(a.output.resolve(),a.bundle.resolve(),a.fujinet_pc.resolve(),a.policy,a.pages,a.index,a.local,a.nmi_point)
