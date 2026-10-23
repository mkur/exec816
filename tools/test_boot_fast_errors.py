#!/usr/bin/env python3
"""Focused emitted boot recovery, cancellation, identity and framing cases."""
import argparse
import json
from pathlib import Path

from fujinet_pc_peer import FujiNetPC
from native_program import ROOT,require,sha256
from os_boundary import emulator
from test_boot_fast import fixture
from test_bootable_atr import wait_at
from test_of816 import boot_environment,screen_text

CASES={'disabled':(40,None,0),'unsupported':(16,None,0),
       'query-lost':(8,'query-lost',0),'query-checksum':(8,'query-checksum',0),
       'read-checksum':(8,'read-checksum',0x8f),'read-error':(8,'read-error',0x90),
       'terminal-error':(8,'terminal-error',0x90),'nak':(8,'nak',0x8b),
       'disconnect':(8,'disconnect',0x8a),'bounds':(8,None,0xc9),
       'break':(8,None,0xc8),'source-changed':(8,None,0xcd),
       'native-incompatible':(40,None,0xcc),'metadata':(8,None,0xca),
       'truncated':(8,None,0xc4),'partial-data':(8,'partial-data',0x8a),
       'chain-self':(8,'chain-self',0xc2),'chain-zero':(8,'chain-zero',0xc4),
       'chain-count':(8,'chain-count',0xc2)}


def run(output,bundle,firmware,cases=None):
    output.mkdir(parents=True,exist_ok=True)
    monitor=json.loads((bundle/'of816/of816.json').read_text());pin,binary,rom=boot_environment(monitor)
    results=[]
    for case in cases or CASES:
        folder=output/case;index,fault,expected=CASES[case]
        r=fixture(folder,'auto',2,native_divisor=8 if case=='native-incompatible' else 40);l=r['labels']
        if case=='truncated':
            path=folder/'boot.xex';path.write_bytes(path.read_bytes()[:r['prefix_bytes']+100])
        with FujiNetPC(folder/'peer',folder/'boot.xex',firmware,readonly=True,hsio_index=index,fault=fault) as peer:
            with emulator(binary,rom,folder/'emulator',pin=pin) as b:
                for k,v in [('siopatch','off'),('burstio','false'),('fastboot','false')]:b.config(k,v)
                b.device_set('custom',path=str(peer.script),hotreload=False,allowunsafe=True);b.cold_reset()
                wait_at(b,l['reader_start'],(),90)
                vectors=b.memdump(0x20a,6)
                if case=='metadata':b.poke(l['take_descriptor']+8,0)
                if case=='bounds':b.memload(0x2e5,bytes.fromhex('1f9c'))
                if case=='break':
                    wait_at(b,l['xex_start'],(l['reader_failed'],),90);b.poke(0x11,0)
                if case=='source-changed':
                    wait_at(b,0x6100,(l['reader_failed'],),90)
                    raw=bytearray((folder/'boot.xex').read_bytes());raw[r['descriptor_offset']+14]^=1
                    (folder/'boot.xex').write_bytes(raw)
                target=l['reader_failed'] if expected else 0x6200
                wait_at(b,target,(0x6200,) if expected else (l['reader_failed'],),120)
                if expected:
                    require(b.eval_expr('@a')&255==expected,f'{case}: incorrect cause {b.regs()}')
                    wait_at(b,l['reader_park'],(),30)
                    text=screen_text(b.memdump(b.peek16(88),960))
                    require(f'{expected:02X}' in text,'Missing visible failure cause')
                    require(b.peek(0x11)==b'\xff','BREAK suppressed diagnostic')
                else:require(b.peek16(0x6300)==2,'Recovery lost callback/stream state')
                require(b.memdump(0x20a,6)==vectors,'Serial vectors retained')
                require(b.peek(0xd303)[0]&8,'COMMAND remained active')
                require(not (b.peek(0x10)[0]&0x38),'Serial IRQ remained enabled')
                for n in ('reader_guard_low','reader_guard_high'):require(b.memdump(l[n],16)==b'\xa5'*16,'Guard changed')
                item=dict(case=case,status='pass',cause=expected,frame=b.eval_expr('@frame'),guards='intact')
        relay=json.loads((folder/'peer/relay.json').read_text());require(not relay['error'],str(relay['error']))
        if fault:require(relay['fault_events'],'Fault was not exercised')
        if case in ('query-lost','query-checksum','unsupported'):
            require(any(c['rate_mismatch'] and c.get('no_response') for c in relay['commands']),
                    'Rate mismatch was hidden by fixture')
        item['relay']=relay;results.append(item);print({k:v for k,v in item.items() if k!='relay'},flush=True)
    report=dict(status='pass',tier='development',qualification=False,cases=results,
                rom_sha256=sha256(rom),emulator_sha256=sha256(binary/'AltirraBridgeServer'))
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bundle',type=Path,default=ROOT/'build/boot-fast/demo')
    p.add_argument('--fujinet-pc',type=Path,default=Path.home()/'atari/fujinet-firmware/build/fujinet')
    p.add_argument('--case',choices=CASES,action='append');a=p.parse_args()
    run(a.output.resolve(),a.bundle.resolve(),a.fujinet_pc.resolve(),a.case)
