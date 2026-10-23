#!/usr/bin/env python3
"""Direct emulator XEX loading must retain its ordinary INIT/RTS path."""
import argparse
import json
from pathlib import Path

from native_program import ROOT,require
from os_boundary import emulator
from test_boot_fast import fixture
from test_bootable_atr import wait_at
from test_of816 import boot_environment


def run(output,bundle):
    monitor=json.loads((bundle/'of816/of816.json').read_text());pin,binary,rom=boot_environment(monitor)
    results=[]
    for case in ('absent','unrelated'):
        folder=output/case;r=fixture(folder,'auto',2);l=r['labels']
        with emulator(binary,rom,folder/'emulator',pin=pin) as b:
            b.config('siopatch','off')
            if case=='unrelated':b.mount(0,str(bundle/'system.atr'))
            b.boot(str(folder/'boot.xex'))
            wait_at(b,0x6200,(l['reader_park'],),90)
            require(b.peek(l['take_selected'])==b'\0','Direct boot took over an unrelated source')
            require(b.peek16(0x6300)==2,'Direct boot lost callbacks')
            require(b.memdump(0x6400,256)==bytes(range(256)),'Direct bytes differ')
            require(b.peek16(0x20a)!=l['bo_rx'],'Direct probe retained its vector')
            item=dict(case=case,status='pass',frame=b.eval_expr('@frame'),callbacks=2)
            results.append(item);print(item,flush=True)
    (output/'results.json').write_text(json.dumps(dict(status='pass',tier='development',cases=results),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path,default=ROOT/'build/boot-fast/demo');a=p.parse_args()
    run(a.output.resolve(),a.bundle.resolve())
