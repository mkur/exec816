#!/usr/bin/env python3
"""Check BASIC screen reclamation through the pinned ROM, plus bound rejection."""
import argparse
import json
from pathlib import Path
import struct
import subprocess

from native_program import ROOT, require, sha256
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import boot_environment


def run(out,bundle):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'probes/os-boundary/boot-platform.s'
    (out/'probe.cfg').write_text('MEMORY { RAM: start=$3000, size=$1000, file=%O; }\n'
                                'SEGMENTS { CODE: load=RAM, type=rw; }\n')
    subprocess.run(['ca65','-I',str(ROOT/'platform/altirraos'),'-o',str(out/'probe.o'),str(source)],check=True)
    subprocess.run(['ld65','-C',str(out/'probe.cfg'),'-o',str(out/'probe.bin'),
                    '-Ln',str(out/'probe.lbl'),str(out/'probe.o')],check=True)
    labels={p[2].lstrip('.'):int(p[1],16) for line in (out/'probe.lbl').read_text().splitlines()
            if len(p:=line.split())==3}
    raw=(out/'probe.bin').read_bytes()
    xex=out/'probe.xex';xex.write_bytes(struct.pack('<HHH',65535,0x3000,0x2fff+len(raw))+raw+
        struct.pack('<HHH',0x2e0,0x2e1,labels['start']))
    monitor=json.loads((bundle/'of816/of816.json').read_text());pin,binary,rom=boot_environment(monitor)
    with emulator(binary,rom,out/'emulator',pin) as b:
        b.boot(str(xex))
        wait_at(b,labels['start'],(),30)
        try:wait_at(b,labels['before_prepare'],(labels['failed'],),30)
        except Exception:
            (out/'failure.json').write_text(json.dumps(dict(regs=b.regs(),
                memtop=b.peek16(0x2e5),ramtop=b.peek(0x6a)[0],portb=b.peek(0xd301)[0],
                result=b.peek(labels['result'])[0],iocb=b.memdump(0x340,16).hex()),indent=2)+'\n')
            raise
        require(b.peek16(0x2e5)==0x9c1f,'Did not reproduce the low BASIC screen')
        before=dict(memtop=b.peek16(0x2e5),ramtop=b.peek(0x6a)[0],portb=b.peek(0xd301)[0])
        wait_at(b,labels['after_prepare'],(labels['failed'],),30)
        after=dict(memtop=b.peek16(0x2e5),screen=b.peek16(0x58),ramtop=b.peek(0x6a)[0],
                   portb=b.peek(0xd301)[0],basicf=b.peek(0x3f8)[0])
        print(dict(before=before,after=after,iocb=b.memdump(0x340,16).hex(),
                   saved_iocb=b.memdump(labels['saved_iocb'],16).hex()),flush=True)
        wait_at(b,labels['done'],(labels['failed'],),30)
        require(b.peek(labels['result'])==b'\1','Boot platform probe failed')
        result=dict(status='pass',tier='development',qualification=False,before=before,after=after,
                    unrelated_memtop_preserved=b.peek16(0x2e5),rom_sha256=sha256(rom),
                    emulator_sha256=sha256(binary/'AltirraBridgeServer'))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.bundle.resolve())
