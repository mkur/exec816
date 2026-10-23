#!/usr/bin/env python3
"""Emitted XEX rejection preserves loader bounds and prints concrete diagnostics."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,require,sha256
from test_loader_compression import fixture,PIN,ROM,BRIDGE
from native_program import xex_segment
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import screen_text


def check(output):
    output.mkdir(parents=True,exist_ok=True);results=[]
    for name,field,value,expected in [('memlo',0x2e7,0x0a01,1),('memtop',0x2e5,0x8fff,1),('manifest',None,None,2)]:
        folder=output/name;memory,labels,segments=fixture(folder,b'A'*1024)
        path=folder/'case.xex';path.write_bytes(b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in segments))
        with emulator(BRIDGE,ROM,folder/'emulator',pin=PIN) as b:
            b.boot(str(path));wait_at(b,labels['loader_init'],(),30)
            if field is not None:b.poke16(field,value)
            else:b.poke(memory['constants']['MANIFEST'],b.peek(memory['constants']['MANIFEST'])[0]^1)
            low,top=b.peek16(0x2e7),b.peek16(0x2e5)
            wait_at(b,labels['loader_return'],(),30)
            require(b.peek(labels['loader_error'])[0]==expected,'Wrong rejection')
            wait_at(b,labels['loader_start'],(),30)
            wait_at(b,labels['loader_done'],(),30)
            text=screen_text(b.memdump(b.peek16(88),960))
            require(f'Exec816 load failed ${expected:02X}' in text,'Missing numeric boot error')
            # Text wraps naturally at the ROM display width.
            compact=text.replace(' ','')
            require(f'MEMLO=${low:04X}' in compact and f'MEMTOP=${top:04X}' in compact,'Missing memory bounds')
            require(b.peek16(0x2e7)==low and b.peek16(0x2e5)==top,'Failure changed OS bounds')
        results.append(dict(case=name,status='pass',error=expected,memlo=low,memtop=top,xex_sha256=sha256(path)))
    result=dict(status='pass',tier='development',qualification=False,cases=results,
                reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,per_public_task=[0]*12,idle=0))
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(check(args.output.resolve()))
