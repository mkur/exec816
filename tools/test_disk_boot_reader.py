#!/usr/bin/env python3
"""Emitted ROM boot: fragmented large XEX, callbacks and bounded bad media."""
import argparse
import json
from pathlib import Path
import shutil
import struct

from build_bootable_atr import build,Volume
from native_program import ROOT,require,sha256
from os_boundary import emulator
from test_bootable_atr import wait_at
from test_of816 import boot_environment,screen_text
from filesystem_audit import Audit


def segment(address,data):
    return struct.pack('<HH',address,address+len(data)-1)+data


def run(output,bundle,group='all'):
    output.mkdir(parents=True,exist_ok=True)
    source=output/'source';source.mkdir(exist_ok=True)
    (source/'NOTE.TXT').write_bytes(b'Boot-reader fixture\n')
    xex=output/'fixture.xex'
    callback=bytes.fromhex('ee0063d003ee016360')
    xex.write_bytes(b'\xff\xff'+segment(0x6100,callback)+segment(0x6300,b'\0\0')+
        (b'\xff\xff'+segment(0x6400,bytes(range(256)))+segment(0x2e2,struct.pack('<H',0x6100)))*300+
        segment(0x2e0,struct.pack('<H',0x6400)))
    base=output/'base.atr';report=build(base,source,xex,output/'reader')
    labels=report['reader']['disk-boot-reader.s']['labels']
    first=report['reader']['disk-boot-first.s']['labels']
    monitor=json.loads((bundle/'of816/of816.json').read_text())
    pin,binary,rom=boot_environment(monitor)
    cases=['fragmented-large'] if group=='large' else ['header','missing','truncated','zero-sector','map-cycle','reader-overwrite','first-guard','break','read-failure']
    if group=='all':cases=['fragmented-large',*cases]
    results=[]
    for case in cases:
        folder=output/case;folder.mkdir(exist_ok=True)
        volume=Volume(base.read_bytes());row,positions=volume.entry('EXEC816.XEX')
        first_map=int.from_bytes(row[1:3],'little');maps,pointers=volume.chain(first_map)
        def put16(at,value):struct.pack_into('<H',volume.image.data,at,value)
        expected=0
        if case=='fragmented-large':
            a,b=pointers[0],pointers[130]
            aa,bb=volume.image.offset(a),volume.image.offset(b)
            left,right=bytes(volume.image.data[aa:aa+256]),bytes(volume.image.data[bb:bb+256])
            volume.image.data[aa:aa+256]=right;volume.image.data[bb:bb+256]=left
            put16(volume.image.offset(maps[0])+4,b)
            put16(volume.image.offset(maps[1])+4+2*4,a)
            audit=Audit(volume.image.data);audit.sdfs()
            require(audit.files['EXEC816.XEX']==xex.read_bytes(),'Fragment fixture changed logical bytes')
        elif case=='header':volume.image.data[16+32]=0x20;expected=0xc1
        elif case=='missing':volume.image.data[positions[0]]|=0x10;expected=0xc3
        elif case=='truncated':
            for i,v in enumerate((3,0,0)):volume.image.data[positions[3+i]]=v
            expected=0xc4
        elif case=='zero-sector':put16(volume.image.offset(first_map)+4,0);expected=0xc2
        elif case=='map-cycle':put16(volume.image.offset(first_map),first_map);expected=0xc2
        elif case=='reader-overwrite':put16(volume.image.offset(pointers[0])+2,0x4000);expected=0xc5
        elif case=='first-guard':
            boot,_=volume.entry('BOOT.LDR');_,data=volume.chain(int.from_bytes(boot[1:3],'little'))
            volume.image.data[volume.image.offset(data[0])]=0;expected=-1
        elif case=='break':expected=0xc8
        elif case=='read-failure':expected=144
        image=folder/'exec816.atr';image.write_bytes(volume.image.data)
        with emulator(binary,rom,folder,pin=pin) as b:
            b.config('diskemu','generic56k');b.config('siopatch','off');b.config('burstio','false');b.config('fastboot','false')
            b.mount(0,str(image));b.cold_reset()
            if case in ('break','read-failure'):
                wait_at(b,labels['reader_start'],(first['first_failed'],),90)
                if case=='break':b.poke(0x11,0)
                else:b._cmd_ok('EJECT drive=0')
            target=labels['reader_run'] if not expected else first['first_failed'] if expected==-1 else labels['reader_failed']
            try:
                wait_at(b,target,tuple(x for x in (labels['reader_run'],labels['reader_failed'],first['first_failed']) if x!=target),180)
            except Exception:
                b.state_save(str(folder/'failure.altstate2'))
                (folder/'failure.json').write_text(json.dumps(dict(regs=b.regs(),state={k:b.peek(v)[0] for k,v in labels.items() if k.startswith(('bo_','reader_'))}),indent=2)+'\n')
                raise
            error=b.peek(labels['reader_error'])[0]
            if expected>0:
                # reader_failed is entered with the cause in A before storing it.
                error=b.eval_expr('@a')&255
                require(error==expected,f'{case}: wrong error ${error:02x}, expected ${expected:02x}')
            if not expected:
                require(b.peek16(0x6300)==300 and b.peek16(labels['reader_callbacks'])==300,
                        'INITAD callbacks lost their buffered file position')
                require(int.from_bytes(b.memdump(labels['file_offset'],3),'little')==xex.stat().st_size,
                        'Reader lost the 24-bit XEX length')
                require(b.memdump(0x6400,256)==bytes(range(256)),'XEX segment bytes differ')
            else:
                park=first['first_park'] if expected==-1 else labels['reader_park']
                wait_at(b,park,(),30)
                screen=screen_text(b.memdump(b.peek16(88),960))
                require(('Exec boot 1:' if expected==-1 else 'Exec disk boot failed:') in screen,
                        'Boot error did not reach the ROM screen')
                if expected>0:require(f'{expected:02X}' in screen,'Visible boot error lost its cause')
                require(b.peek(0x11)==b'\xff','Boot error retained BREAK and suppressed diagnostics')
            item=dict(case=case,status='pass',error=error,frame=b.eval_expr('@frame'),
                      callbacks=b.peek16(labels['reader_callbacks']),image_sha256=sha256(image))
            results.append(item);print(item,flush=True)
    result=dict(status='pass',tier='development',qualification=False,cases=results,
                reader=report,rom_sha256=sha256(rom),emulator_sha256=sha256(binary/'AltirraBridgeServer'))
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--group',choices=('all','large','failure'),default='all')
    a=p.parse_args();run(a.output.resolve(),a.bundle.resolve(),a.group)
