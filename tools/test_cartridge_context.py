#!/usr/bin/env python3
"""Mapped-cart display lifetime, callbacks, bank crossings and native handoff."""
import argparse
import json
from pathlib import Path
import struct
import zipfile

from build_cartridge import build
from build_boot_fast import segment
from native_program import require
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import boot_environment


def run(out,bundle):
    out.mkdir(parents=True,exist_ok=True)
    xex=out/'probe.xex'
    xex.write_bytes(b'\xff\xff'+segment(0x6100,b'\x60')+
        (segment(0x6400,bytes(range(256)))+segment(0x2e2,struct.pack('<H',0x6100)))*40+
        segment(0x6200,bytes.fromhex('4c0062'))+segment(0x2e0,struct.pack('<H',0x6200)))
    cart=build(xex,out/'cartridge');labels=cart['labels']
    pin,binary,rom=boot_environment(json.loads((bundle/'of816/of816.json').read_text()))
    cases=[]
    for variant in ('new','old'):
        folder=out/variant;folder.mkdir(exist_ok=True)
        with emulator(binary,rom,folder,pin) as b:
            b.boot(str(out/'cartridge'/f'probe-atarimax-8mbit-{variant}.car'))
            wait_at(b,labels['cart_bank_mapped'],(labels['cart_failed'],),60)
            require(int(b.regs()['P'].lstrip('$'),16)&4,'Initial cart mapping left IRQ enabled')
            require(b.peek(0xd013)==b'\1','Cart is not mapped at the observation')
            snapshot=folder/'mapped.altstate2';b.state_save(str(snapshot))
            with zipfile.ZipFile(snapshot) as z:
                objects=json.loads(z.read('savestate.json'))['objects']
                antic=next(o for o in objects if 'nmien' in o)
                require(antic['nmien']==0,'Initial cart mapping left NMI enabled')
                require(antic['dmactl']==0x22,'Cart reads blanked the OS display')
                memory=z.read('memory.bin')
                require(int.from_bytes(memory[0x230:0x232],'little')==0x9c20 and
                        int.from_bytes(memory[0x58:0x5a],'little')==0x9c40,
                        'Cart display overlaps its ROM window')
            for callback in range(40):
                wait_at(b,0x6100,(labels['cart_failed'],),60)
                require(not int(b.regs()['P'].lstrip('$'),16)&4,'INITAD did not receive ROM IRQ state')
                require(b.peek(0xd013)==b'\1' and b.peek(0x3fa)==b'\1',
                        'INITAD unmapped the cartridge')
                require(b.peek(0xd301)[0]&2 and b.peek16(0x2e5)==0x9c1f,
                        'Boot exposed native-only high RAM')
                require(b.peek16(0x230)==0x9c20 and b.peek16(0x58)==0x9c40 and
                        int(b.antic()['DMACTL'].lstrip('$'),16)==0x22,
                        'INITAD moved or blanked the cartridge-era display')
                require(b.peek16(labels['cart_calls'])==callback+1,'Lost callback order')
            wait_at(b,0x6200,(labels['cart_failed'],),60)
            require(b.peek(0xd013)==b'\0' and b.peek(0x3fa)==b'\0',
                    'RUNAD still has a mapped cartridge')
            require(b.peek16(0x2e5)==0xbc1f and b.peek16(0x230)==0xbc20 and
                    b.peek16(0x58)==0xbc40,'RUNAD did not prepare the native layout')
            require(b.peek16(labels['cart_calls'])==40,'Bank crossing lost callbacks')
            require(b.memdump(labels['cart_remaining'],3)==bytes(3),'Unread cart input')
            require(b.memdump(0x6400,256)==bytes(range(256)),'Cart payload differs')
            cases.append(dict(variant=variant,status='pass',callbacks=40,
                initial_irq_masked=True,initial_nmi_masked=True,callback_cart_mapped=True,
                boot_display_list=0x9c20,boot_screen=0x9c40,display_dma=0x22,
                native_cart_disabled=True,native_memtop=0xbc1f))
        folder=out/(variant+'-failure');folder.mkdir(exist_ok=True)
        with emulator(binary,rom,folder,pin) as b:
            b.boot(str(out/'cartridge'/f'probe-atarimax-8mbit-{variant}.car'))
            wait_at(b,labels['cart_bank_mapped'],(labels['cart_failed'],),60)
            b.memload(labels['cart_remaining'],b'\1\0\0')
            wait_at(b,labels['cart_failed_park'],(),60)
            require(b.peek(0xd013)==b'\1' and b.peek(0x3fa)==b'\1' and
                    b.peek16(0x230)==0x9c20 and b.peek16(0x58)==0x9c40 and
                    int(b.antic()['DMACTL'].lstrip('$'),16)==0x22,
                    'Failed cart boot lost the working ROM display')
            cases.append(dict(variant=variant,status='pass',failure='truncated stream',
                              cartridge_mapped=True,display_preserved=True))
    result=dict(status='pass',tier='development',qualification=False,cases=cases)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.bundle.resolve())
