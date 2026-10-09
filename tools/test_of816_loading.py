#!/usr/bin/env python3
"""Focused emitted checks for a monitor paused inside a live XEX loader."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from native_program import ROOT, read_build, require, sha256, xex_segment
from os_boundary import emulator, run_to
from test_banked import assemble_probe
from test_of816 import boot_environment, check_boot_guards, check_loading_paused
from test_of816 import enter_forth, press, screen_text
from build_of816 import xex_segments
from banked_image import extents, emit, reserved_banks


def return_probe(folder,record,depth,base,masked=False):
    """Keep a real host frame above two different synthetic caller depths."""
    source=f'''.setcpu "65816"
.a8
.i8
.segment "CODE"
.export start,done,calling,observed,host_stack
start:
    php
    pha
    xba
    pha
    phx
    phy
    phb
    phd
    tsx
    stx host_stack
    ldx #${depth:02x}
    txs
    pea $1234
    pld
    lda #$ab
    pha
    plb
    ldx #$35
    ldy #$67
    lda #$be
    xba
    lda #$a9
    clv
    sed
    sec
    {'sei' if masked else 'cli'}
calling:
    jsr ${record['labels']['of_start']:04x}
    php
    pha
    xba
    pha
    phx
    phy
    phb
    phd
    phk
    plb
    cld
    tsx
    txa
    clc
    adc #8
    sta f:observed+8
    ldy #0
copy:
    lda f:$0101,x
    sta a:observed,y
    inx
    iny
    cpy #8
    bne copy
    pea $0000
    pld
    phk
    plb
done:
    jmp done
host_stack: .byte 0
observed: .res 9,0
'''
    return assemble_probe(folder,source,base)


def check_return(out,record,program,depth,manual=False,masked=False):
    folder=out/f'return-{depth:02x}-{"manual" if manual else "masked" if masked else "auto"}'
    folder.mkdir(parents=True,exist_ok=True)
    c=program['build']['memory']['constants']
    base=c['LOADER']+c['LOADER_BYTES']-512
    labels=return_probe(folder,record,depth,base,masked)
    probe=(folder/'probe.bin').read_bytes()
    require(c['LOADER']+len((program['output']/'loader.bin').read_bytes())<=base and
            base+len(probe)<=c['LOADER']+c['LOADER_BYTES'],'Return probe overlaps live boot code')
    segments=list(xex_segments((program['output']/'of816/Exec-of816.xex').read_bytes()))
    stop=record['loading']['monitor_init_segment']
    raw=b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in segments[:stop])
    raw+=xex_segment(base,probe)+xex_segment(0x2e2,struct.pack('<H',labels['start']))
    raw+=xex_segment(0x2e0,struct.pack('<H',record['labels']['of_park']))
    image=folder/'return.xex';image.write_bytes(raw)
    pin,binary,rom=boot_environment(record)
    with emulator(binary,rom,folder,pin=pin) as b:
        b.boot(str(image));b.bp_set(labels['calling']);run_to(b,labels['calling'],3000,90)
        caller=b.memdump(0x100+depth+1,255-depth)
        b.bp_clear_all()
        b.bp_set(record['labels']['of_autoboot']);run_to(b,record['labels']['of_autoboot'],1000,30)
        require(b.peek16(record['labels']['of_os_stack'])==0x100+depth-10,'Incorrect OS stack anchor')
        check_loading_paused(b,record,program)
        if manual:
            enter_forth(b,record['labels'],delay=240,hold=60)
            for character in 'decimal 6 7 * .\n':press(b,record['labels'],character)
            require('42 ' in screen_text(b.memdump(b.peek16(88),960)),'Return probe arithmetic failed')
            for character in 'exec816':press(b,record['labels'],character)
            press(b,record['labels'],'\n',record['labels']['of_handoff'])
        else:
            b.bp_clear_all();b.bp_set(record['labels']['of_handoff'])
            run_to(b,record['labels']['of_handoff'],300,15)
        check_boot_guards(b,record['layout'])
        require(b.peek16(record['labels']['of_nmis'])>0,'No VBI while caller frame was live')
        b.bp_clear_all();b.bp_set(labels['done']);run_to(b,labels['done'],120,15)
        observed=b.memdump(labels['observed'],9)
        require(observed==bytes([0x34,0x12,0xab,0x67,0x35,0xbe,0xa9,0xb9|(4 if masked else 0),depth]),
                'INITAD caller context changed: '+observed.hex())
        require(b.memdump(0x100+depth+1,255-depth)==caller,'Paused loader frame changed')
    return dict(case=folder.name,status='pass',xex_sha256=sha256(image),
                caller_context=observed.hex(),caller_frame='intact',vbi=True,
                diagnostic_scratch=dict(loader_bytes=len(probe),extra_reservations=0))


def snapshot_image(b,program,folder):
    """Copy upper-RAM chunks to existing staging, preserving the live loader.

    Observer transfers mask NMI; interrupt coverage is provided separately.
    The entire staging range and the unused loader scratch are restored.
    """
    c=program['build']['memory']['constants'];pc=program['labels']['loader_start']
    base=c['LOADER']+c['LOADER_BYTES']-512
    require(c['LOADER']+len((program['output']/'loader.bin').read_bytes())<=base,
            'Snapshot scratch overlaps loader')
    original=b.memdump(pc,3);scratch=b.memdump(base,512);staging=b.memdump(c['STAGE'],1024)
    nmien=int(b.antic()['NMIEN'].lstrip('$'),16)
    spans=extents(program['image'],program['build']['memory']);checks=[];copies={}
    b.hwpoke(0xd40e,0)
    try:
        for address,payload,size,kind,_ in spans:
            expected=bytes(size) if kind==1 else payload
            actual=bytearray()
            for offset in range(0,size,1024):
                at=address+offset;n=min(1024,size-offset)
                code=f'''.setcpu "65816"
.smart
.segment "CODE"
.export start,done
.a8
.i8
start:
    php
    sei
    clc
    xce
    rep #$30
    pha
    phx
    phy
    phd
    phb
    lda #0
    tcd
    lda #{n-1}
    ldx #${at&65535:04x}
    ldy #${c['STAGE']:04x}
    mvn #${at>>16:02x},#$00
    plb
    pld
    ply
    plx
    pla
    sep #$30
    sec
    xce
    plp
done:
    jmp done
'''
                key=(at>>16,n)
                if key not in copies:
                    code=code.replace('.export start,done','.export start,done,source')
                    code=code.replace('    ldx #','source:\n    ldx #',1)
                    location=folder/f'snapshot-{key[0]:02x}-{n}'
                    labels=assemble_probe(location,code,base)
                    copies[key]=(labels,(location/'probe.bin').read_bytes())
                labels,copy=copies[key]
                b.memload(base,copy)
                b.memload(labels['source']+1,struct.pack('<H',at&65535))
                b.memload(pc,b'\x4c'+struct.pack('<H',base))
                b.bp_clear_all();b.bp_set(labels['done']);run_to(b,labels['done'],10,5)
                actual+=b.memdump(c['STAGE'],n)
                b.memload(pc,original)
                b.memload(labels['done'],b'\x4c'+struct.pack('<H',pc))
                b.bp_clear_all();b.bp_set(pc);run_to(b,pc,10,5)
            require(actual==expected,f'Loaded native extent differs: ${address:06x}, kind {kind}')
            checks.append(dict(address=address,bytes=size,kind=kind,
                               sha256=hashlib.sha256(actual).hexdigest()))
    finally:
        b.memload(pc,original);b.memload(base,scratch);b.memload(c['STAGE'],staging)
        b.hwpoke(0xd40e,nmien);b.bp_clear_all()
    return dict(extents=checks,bytes=sum(s['bytes'] for s in checks),
                diagnostic_scratch=dict(loader_bytes=512,staging_bytes=1024,restored=True,
                                        extra_reservations=0))


def check_image(out,record,program):
    folder=out/'payload';pin,binary,rom=boot_environment(record)
    with emulator(binary,rom,folder,pin=pin) as b:
        b.boot(str(program['output']/'of816/Exec-of816.xex'))
        b.bp_set(record['labels']['of_start']);run_to(b,record['labels']['of_start'],3000,90)
        check_loading_paused(b,record,program)
        screen=b.peek16(88);marker='Earlier boot message'
        from test_console_display import glyph
        b.memload(screen,bytes(map(glyph,marker.encode('ascii'))))
        b.poke(84,1);b.poke16(85,2)
        b.bp_clear_all();b.bp_set(record['labels']['of_handoff'])
        run_to(b,record['labels']['of_handoff'],1000,30)
        require(marker in screen_text(b.memdump(screen,960)),'OF816 cleared earlier screen text')
        check_boot_guards(b,record['layout'])
        b.bp_clear_all();b.bp_set(program['labels']['loader_start'])
        run_to(b,program['labels']['loader_start'],3000,90)
        report=snapshot_image(b,program,folder)
        text=screen_text(b.memdump(screen,960))
        require('Loading Exec816 ' in text,'Missing resumed loading message')
    return dict(case='native-payload',status='pass',screen_preserved=True,**report)


def check_feedback(out,record,program,name,size,zero=False,failure=None):
    """Small real record streams cover rounding, zero-fill and guarded failure."""
    folder=out/name;folder.mkdir(parents=True,exist_ok=True)
    memory=program['build']['memory'];c=memory['constants']
    for include in ('memory.inc','boot-config.inc'):
        shutil.copyfile(program['output']/include,folder/include)
    finish=assemble_probe(folder/'finish','''.setcpu "65816"
.segment "CODE"
.export start
start: jmp start
''',0x7800)['start']
    bank=next(b for b in memory['usable_banks'] if b not in reserved_banks(memory))
    address=bank<<16
    data=bytes((i*29+7)&255 for i in range(size))
    image=dict(entry=address,segments=[dict(address=address,bytes=list(data if not zero else data[:1]),
                                          executable=True)],zero_fill=[])
    if zero:image['zero_fill']=[dict(address=address+1,size=size-1)]
    (folder/'hosted.bin').write_bytes(b'\xea')
    raw,labels=emit(folder,image,memory,dict(start=finish))
    segments=list(xex_segments(raw))
    segments.insert(1,(0x7800,(folder/'finish/probe.bin').read_bytes()))
    if failure=='record':
        at=next(i for i,(a,d) in enumerate(segments) if a==c['STAGE'] and len(d)>8)
        a,d=segments[at];segments[at]=(a,d[:7]+b'\1'+d[8:])
    elif failure=='incomplete':
        at=next(i for i,(a,d) in enumerate(segments) if a==c['STAGE'] and len(d)>8)
        segments=segments[:at+2]
    path=folder/'feedback.xex'
    path.write_bytes(b'\xff\xff'+b''.join(xex_segment(a,d) for a,d in segments))
    pin,binary,rom=boot_environment(record)
    with emulator(binary,rom,folder,pin=pin) as b:
        b.boot(str(path))
        if failure=='bounds':
            b.bp_set(labels['loader_init']);run_to(b,labels['loader_init'],1000,30)
            b.poke16(0x2e7,0x0801);b.bp_clear_all()
        target=labels['loader_done'] if failure else finish
        b.bp_set(labels['loader_start']);run_to(b,labels['loader_start'],3000,90)
        b.bp_clear_all()
        b.bp_set(target);run_to(b,target,3000,90)
        text=screen_text(b.memdump(b.peek16(88),960))
        if failure:
            require(b.peek(labels['loader_error'])!=b'\0' and b.peek(c['ENTERED'])==b'\0',
                    'Failed stream entered the kernel')
            require(text.count('Exec816 load failed')==1,'Missing/repeated load failure message')
            dots=0
        else:
            expected='Loading Exec816 '+'.'*((size+16383)//16384)
            require(expected in text and expected+'.' not in text,'Incorrect progress rounding: '+text)
            require(text.count('Exec816 boot')==1,'Boot banner repeated')
            require(b.peek(labels['loader_error'])==b'\0','Valid progress stream failed')
            require(b.peek16(labels['loader_progress_bytes'])==0 and
                    b.peek(labels['loader_progress_stage'])==b'\0','Stage was not completed')
            dots=(size+16383)//16384
            if zero:
                sample=dict(output=folder,image=image,build=dict(memory=memory),
                            labels={**labels,'loader_start':finish})
                snapshot_image(b,sample,folder)
    return dict(case=name,status='pass',bytes=size,dots=dots,zero_fill=zero,
                rejected=failure,xex_sha256=sha256(path))


def run(bundle,out,case='all'):
    program=read_build(bundle);record=json.loads((bundle/'of816/of816.json').read_text())
    require(sha256(bundle/'of816/Exec-of816.xex')==record['xex_sha256'],'Changed boot XEX')
    out.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',boot=record,
                observer_sha256=sha256(Path(__file__)),cases=[])
    try:
        if case in ('all','return'):
            for depth,manual,masked in [(0xd0,False,False),(0xb0,False,False),
                                        (0xb0,True,False),(0xd0,False,True)]:
                report['cases'].append(check_return(out,record,program,depth,manual,masked))
        if case in ('all','payload'):
            report['cases'].append(check_image(out,record,program))
        if case in ('all','feedback'):
            for name,size,zero,failure in [('small',1,False,None),('exact',16384,False,None),
                                         ('remainder',16385,False,None),('zero',16384,True,None),
                                         ('bad-record',1024,False,'record'),
                                         ('incomplete',2048,False,'incomplete'),
                                         ('bounds',1,False,'bounds')]:
                report['cases'].append(check_feedback(out,record,program,name,size,zero,failure))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=('all','return','payload','feedback'),default='all')
    args=parser.parse_args()
    run(args.bundle.resolve(),args.output.resolve(),args.case)
    print('OF816 caller frames, context, screen and native payload passed')
