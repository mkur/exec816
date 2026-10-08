#!/usr/bin/env python3
"""Focused emitted loader cases: fragments, bounds and the live OS context."""
import argparse
import json
from pathlib import Path
import random
import struct

from banked_image import emit
from build_of816 import xex_segments
from generate_memory import layout,generate
from native_program import ROOT,require,sha256,xex_segment
from os_boundary import emulator,run_to
from test_banked import assemble_probe

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
ROM=ROOT/'build/firmware/altirraos-816.rom'
BRIDGE=ROOT/'build/shell-paced-bridge'


def fixture(folder,data,address=0x30000,probe=False):
    folder.mkdir(parents=True,exist_ok=True)
    memory=layout();generate(folder,memory)
    (folder/'hosted.bin').write_bytes(b'\xea')
    image=dict(entry=address,segments=[dict(address=address,bytes=list(data),executable=True)],zero_fill=[])
    raw,labels=emit(folder,image,memory,dict(start=0x7c00),probe=probe)
    return memory,labels,list(xex_segments(raw))


def check(folder,name,data,mutation=None,fragment=False,address=0x30000):
    memory,labels,segs=fixture(folder/name,data,address)
    c=memory['constants']
    setup,payload=segs[:6],segs[6:-1]
    if fragment:
        fragmented=[]
        for at in range(0,len(payload),2):
            _,record=payload[at]
            index,offset,count,kind,encoding=struct.unpack('<HHHBB',record[:8])
            if encoding:
                parts=[record[8:13],*[bytes([b]) for b in record[13:]]] if encoding==1 else [bytes([b]) for b in record[8:]]
                for number,part in enumerate(parts):
                    code=1 if encoding==1 and number==0 else 2
                    fragmented += [(c['STAGE'],struct.pack('<HHHBB',index,offset,len(part),kind,code)+part),payload[at+1]]
            else:fragmented += payload[at:at+2]
        payload=fragmented
    if mutation:
        payload=mutation(payload,c)
    guard=f'''.setcpu "65816"
.segment "CODE"
.export start,done
start:
 lda #$a5
 ldx #15
loop:
 sta f:${address-16:06x},x
 sta f:${address+len(data):06x},x
 dex
 bpl loop
 rts
done:
 jmp done
'''
    probe=assemble_probe(folder/name/'guard',guard,0x7c00)
    guard_bytes=(folder/name/'guard/probe.bin').read_bytes()
    done=probe['done']
    wire=setup+[(0x7c00,guard_bytes),(0x2e2,struct.pack('<H',probe['start'])),
                (0x2e2,struct.pack('<H',labels['loader_init']))]+payload
    # HOST_START parks at the first guard instruction after the full load.
    wire += [(0x7c00,b'\x4c'+struct.pack('<H',done)),segs[-1]]
    path=folder/name/'case.xex'
    path.write_bytes(b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in wire))
    with emulator(BRIDGE,ROM,folder/name/'run',pin=PIN) as b:
        b.boot(str(path));b.bp_set(labels['loader_start'])
        run_to(b,labels['loader_start'],3000,60)
        error=b.peek(labels['loader_error'])[0]
        require(error==(3 if mutation else 0),f'{name}: wrong error {error}')
        require(b.memdump(address-16,16)==b'\xa5'*16 and
                b.memdump(address+len(data),16)==b'\xa5'*16,f'{name}: destination guard changed')
        if not mutation:
            require(b.peek(labels['lz4_active'])==b'\0',f'{name}: unfinished block')
            require(b.memdump(address,len(data))==data,f'{name}: output mismatch')
    print(name,'passed',flush=True)
    return dict(name=name,status='pass',expected_error=error,bytes=len(data),xex_sha256=sha256(path),guards='intact')


def malformed(body,output=1024):
    def replace(payload,c):
        first=payload[0][1]
        record=first[:4]+struct.pack('<H',len(body)+4)+first[6:7]+b'\1'+struct.pack('<HH',output,len(body))+body
        return [(c['STAGE'],record),payload[1]]
    return replace


def context(folder):
    data=b'A'*24000
    memory,labels,segs=fixture(folder/'context',data,probe=True)
    c=memory['constants']
    record=next(d for a,d in segs if a==c['STAGE'] and int.from_bytes(d[4:6],'little'))
    source=f'''.setcpu "65816"
.a8
.i8
.segment "CODE"
.export start,done,observed,expected_sp
start:
 tsx
 stx expected_sp
 lda #$ab
 pha
 plb
 pea $1234
 pld
 cli
 lda #$be
 xba
 lda #$a9
 ldx #$35
 ldy #$67
 clv
 sed
 sec
 jsr ${labels['loader_init']:04x}
 php
 sta f:observed
 xba
 sta f:observed+1
 txa
 sta f:observed+2
 tya
 sta f:observed+3
 phb
 pla
 sta f:observed+4
 phd
 pla
 sta f:observed+5
 pla
 sta f:observed+6
 cld
 tsx
 txa
 clc
 adc #1
 sta f:observed+7
 pla
 sta f:observed+8
 cld
done:
 jmp done
expected_sp: .byte 0
observed: .res 9,0
'''
    probe=assemble_probe(folder/'context/caller',source,0x7c00)
    wire=[(a,d) for a,d in segs if a in (c['LOADER'],c['MANIFEST'])]
    wire += [(0x7c00,(folder/'context/caller/probe.bin').read_bytes()),(c['STAGE'],record),
             (0x2e0,struct.pack('<H',probe['start']))]
    path=folder/'context/case.xex';path.write_bytes(b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in wire))
    with emulator(BRIDGE,ROM,folder/'context/run',pin=PIN) as b:
        b.boot(str(path));b.bp_set(probe['start']);run_to(b,probe['start'],1000,30)
        b.bp_clear_all();b.bp_set(probe['done']);run_to(b,probe['done'],1000,30)
        actual=b.memdump(probe['observed'],9)
        expected=bytes.fromhex('a9be3567ab3412')+b.peek(probe['expected_sp'])+b'\x39'
        require(actual==expected,f'Caller context changed: {actual.hex()} != {expected.hex()}')
        require(b.peek(c['WORK']+9)==b'\1','No real VBI in compressed callback')
        require(b.peek(labels['loader_error'])==b'\0','Context callback failed')
    print('context passed',flush=True)
    return dict(name='context',status='pass',context=actual.hex(),vbi_during_callback=True,xex_sha256=sha256(path))


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    require(sha256(ROM)==PIN['rom']['sha256'] and
            sha256(BRIDGE/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned machine')
    report=dict(status='running',tier='development',pin=PIN,cases=[],
                observer_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=0))
    random_data=random.Random(816).randbytes(4096)
    try:
        for name,data,fragment,address in [
            ('maximum',b'A'*32768,False,0x30000),
            ('continuations',random_data*6,False,0x30000),
            ('byte-fragments',b'A'*1900+bytes(range(128))*3,True,0x30000),
            ('bank-boundary',random_data*3,False,0x1f000),
            ('raw-fallback',random_data[:64],False,0x30000)]:
            report['cases'].append(check(output,name,data,fragment=fragment,address=address))
        for name,body in [
            ('zero-offset',b'\x10A\0\0\x50abcde'),
            ('offset-before-output',b'\x10A\x02\0\x50abcde'),
            ('output-overrun',b'\x1fA\x01\0'+b'\xff'*5+b'\0\x50abcde'),
            ('length-overflow',b'\x1fA\x01\0'+b'\xff'*257+b'\0\x50abcde'),
            ('missing-final-literals',b'\x1cA\x01\0')]:
            report['cases'].append(check(output,name,b'A'*1024,mutation=malformed(body)))
        def orphan(payload,c):
            a,d=payload[0];return [(a,d[:7]+b'\2'+d[8:]),payload[1]]
        report['cases'].append(check(output,'orphan-continuation',b'A'*1024,mutation=orphan))
        report['cases'].append(context(output))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve())
