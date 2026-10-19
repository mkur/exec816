#!/usr/bin/env python3
"""Pinned ARC original controls and emitted native personality checks."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from sdfs_reference import make,extract
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership


def crc16(raw):
    crc=0
    for value in raw:
        crc^=value
        for _ in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
    return crc


def archive(files):
    raw=bytearray()
    for name,data in files.items():
        raw+=b'\x1a\x02'+name.encode().ljust(13,b'\0')
        raw+=struct.pack('<IHHHI',len(data),(46<<9)|(10<<5)|18,(14<<11)|(32<<5)|7,crc16(data),len(data))
        raw+=data
    return bytes(raw)+b'\x1a\0'


def corpus():
    return {'ABC.BIN':b'abc','EMPTY.BIN':b'','ALL.BIN':bytes(range(256))}


LIST_CASES=[('LIST.OUT','L SAMPLE.ARC'),('VERBOSE.OUT','V SAMPLE.ARC'),
            ('MASK.OUT','L SAMPLE.ARC A*.BIN'),('EMPTY.OUT','V SAMPLE.ARC EMPTY.BIN')]


def reference(out,extraction=False,creation=False,store=False):
    source=out/'source';source.mkdir(parents=True,exist_ok=True)
    (source/'SAMPLE.ARC').write_bytes(archive(corpus()))
    commands=[f'ARC {args} >>{name}' for name,args in LIST_CASES]+['STOP.COM']
    if extraction:
        from arc_archive import codec_corpus
        raw,expected=codec_corpus()
        (source/'CODECS.ARC').write_bytes(raw)
        commands=['ARC XW CODECS.ARC >>EXTRACT.OUT','STOP.COM']
    if creation:
        from arc_archive import creation_corpus
        expected=creation_corpus()
        for name,value in expected.items():(source/name).write_bytes(value)
        commands=['ARC A NEW.ARC *.BIN >>CREATE.OUT','ARC V NEW.ARC >>LIST.OUT','STOP.COM']
    if store:commands=[c.replace('ARC A NEW.ARC','ARC AS NEW.ARC') for c in commands]
    (source/'AUTOEXEC.BAT').write_bytes(b'\x9b'.join(c.encode() for c in commands)+b'\x9b')
    (source/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
    (source/'STOP.COM').write_bytes(struct.pack('<HHH',65535,0x6000,0x6002)+b'\x4c\x00\x60'+struct.pack('<HHH',0x2e0,0x2e1,0x6000))
    make(out/'input.atr',source,1024,256,'ARCREF')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.mount(0,str(out/'input.atr'));b.bp_set(0x6000)
        b.boot(str(ROOT/'build/sdx-inputs/md5/SDX450_maxflash1.car'));b.resume()
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if int(b.regs()['PC'].lstrip('$'),16)==0x6000:break
            time.sleep(.05)
        else:
            b.pause();(out/'screen.png').write_bytes(b.screenshot());raise RuntimeError('Original ARC timed out')
        b.pause();(out/'screen.png').write_bytes(b.screenshot());time.sleep(3);b.regs();b._cmd_ok('EJECT drive=0')
    extract(out/'input.atr',out/'readback')
    outputs={p.name:p.read_bytes().hex() for p in (out/'readback').glob('*.OUT')}
    if store:
        assert not (out/'readback/NEW.ARC').exists()
        assert (out/'readback/NEW.XAR').exists()
        for name,value in expected.items():assert (out/'readback'/name).read_bytes()==value
        return dict(status='pass',tier='development',scope='Reproduced original S failure; no successful creation claimed',commands=commands,outputs=outputs,machine=machine,pin=PIN)
    if creation:
        from arc_archive import read
        files,entries=read((out/'readback/NEW.ARC').read_bytes())
        assert files==expected
        return dict(status='pass',tier='development',commands=commands,outputs=outputs,machine=machine,pin=PIN,entries=entries)
    if extraction:
        for name,value in expected.items():assert (out/'readback'/name).read_bytes()==value,name
        return dict(status='pass',tier='development',commands=commands,outputs=outputs,machine=machine,pin=PIN,files={k:hashlib.sha256(v).hexdigest() for k,v in expected.items()})
    assert set(outputs)=={name for name,_ in LIST_CASES}
    for name in ['LIST.OUT','VERBOSE.OUT']:
        value=outputs[name]
        raw=bytes.fromhex(value)
        assert all(name.encode() in raw for name in corpus()),raw
    return dict(status='pass',tier='development',scope='Original SDX output; exit codes not captured',commands=commands,outputs=outputs,machine=machine,pin=PIN)


def fixture(out,extraction=False):
    names=['ARC.COM','ARCLST.OVL']+(['ARCEXT.OVL'] if extraction else [])
    files={name:(ROOT/'build/sdx-inputs/arc'/name).read_bytes() for name in names}
    expected={}
    if extraction:
        from arc_archive import codec_corpus,member,crc16
        files['CODECS.ARC'],expected=codec_corpus()
        files['CRC.ARC']=member('BAD.BIN',b'abc',checksum=crc16(b'abc')^1)+b'\x1a\0'
        files['TRUNC.ARC']=member('TRUNC.BIN',b'abc')[:-2]+b'\x1a\0'
        files['METHOD.ARC']=member('UNSUP.BIN',b'abc',9)+b'\x1a\0'
        over=bytearray(member('OVER.BIN',b'abc'));over[25:29]=struct.pack('<I',1)
        files['OVER.ARC']=bytes(over)+b'\x1a\0'
        large=bytes((i*37+i//251)&255 for i in range(65537))
        files['LARGE.ARC']=member('LARGE.BIN',large)+b'\x1a\0'
        expected['LARGE.BIN']=large
    else:files['SAMPLE.ARC']=archive(corpus())
    payload=bytearray();setup=[];verify=[]
    for name,raw in files.items():
        at=0x300000+len(payload);payload+=raw
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
    for name,raw in expected.items():
        at=0x300000+len(payload);payload+=raw
        verify.append(f'  Verify(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)},1)')
    source=out/'probe.act'
    calls=[f'  Run({i},BYTE POINTER(c"{args}"),{len(args)},0,0)' for i,(_,args) in enumerate(LIST_CASES)]
    template='sdx_arc_extract.act' if extraction else 'sdx_arc.act'
    source.write_text((ROOT/'tests/programs'/template).read_text()
        .replace('SETUP_FILES','\n'.join(setup)).replace('RUN_CASES','\n'.join(calls)).replace('VERIFY_FILES','\n'.join(v for v in verify if 'LARGE.BIN' not in v)).replace('VERIFY_LARGE','\n'.join(v for v in verify if 'LARGE.BIN' in v)))
    return source,[(0x300000,bytes(payload))]


def native(out,extraction=False):
    source,payload=fixture(out,extraction)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=16384 if extraction else 12288
    (out/'memory-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,image_data=payload,dos_mounts=[dict(alias='RAM',format=3)],memory_profile=out/'memory-profile.json')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,program,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ['checks','currentCase','primary','secondary','reason','guestBank']},flush=True)
            context=b.memdump(0x287a00,512);bank=context[0x108]*65536
            (out/'guest-context.bin').write_bytes(context)
            (out/'guest-bank.bin').write_bytes(b.memdump(bank,65536))
            print('event',int.from_bytes(context[0x106:0x108],'little'),'guestS',hex(int.from_bytes(context[0x104:0x106],'little')),flush=True)
            raise
        ownership(b,program,out)
        counts=bytes(data(b,program['image'],'counts'));raw=bytes(data(b,program['image'],'actual'))
        checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
        outputs={name:raw[i*1024:i*1024+int.from_bytes(counts[i*4:i*4+4],'little')].hex()
                 for i,name in enumerate(([n for n,_ in LIST_CASES]+['MISSING.OVL','CORRUPT.OVL','RECOVERY.OUT']) if not extraction else ['EXTRACT.OUT','DECLINE.OUT','OVERWRITE.OUT','CRC.OUT'])}
    (out/'outputs.json').write_text(json.dumps(outputs,indent=2)+'\n')
    if extraction:
        original=json.loads((ROOT/'build/sdx-arc/reference-extract/results.json').read_text())
        assert outputs['EXTRACT.OUT']==original['outputs']['EXTRACT.OUT'],bytes.fromhex(outputs['EXTRACT.OUT'])
        assert b'Overwrite (Y/N/A)? N' in bytes.fromhex(outputs['DECLINE.OUT'])
        assert b'Overwrite (Y/N/A)? Y' in bytes.fromhex(outputs['OVERWRITE.OUT'])
        assert b'fails CRC' in bytes.fromhex(outputs['CRC.OUT'])
        return dict(status='pass',tier='development',checks=checks,outputs=outputs,runtime=runtime,machine=machine,build=program['build'])
    (out/'outputs.json').write_text(json.dumps(outputs,indent=2)+'\n')
    original=json.loads((ROOT/'build/sdx-arc/reference/results.json').read_text())
    expected={**original['outputs'],'MISSING.OVL':'','CORRUPT.OVL':'','RECOVERY.OUT':original['outputs']['LIST.OUT']}
    assert outputs==expected,{k:bytes.fromhex(v) for k,v in outputs.items()}
    return dict(status='pass',tier='development',checks=checks,outputs=outputs,runtime=runtime,machine=machine,build=program['build'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=['reference','reference-extract','reference-create','reference-store','a1','a2'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running');started=time.monotonic()
    try:result=reference(out,args.group=='reference-extract',args.group in ('reference-create','reference-store'),args.group=='reference-store') if args.group.startswith('reference') else native(out,args.group=='a2')
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ARC',args.group,result['status'],result.get('checks',''),flush=True)


if __name__=='__main__':main()
