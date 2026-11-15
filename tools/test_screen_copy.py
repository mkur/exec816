#!/usr/bin/env python3
"""Emitted screen-copy descriptors against an independent snapshot oracle.

The real typed driver and renderer routines execute on the 65816. Substitute
only admission, overlay and hardware submission boundaries; replay captured
BCBs against host VRAM. MGVIEW supplies the real hardware/ownership check.
"""
import argparse
import json
import struct
from pathlib import Path

from calypsi_build import emit
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace+1
    while depth:
        depth += (text[end] == '{')-(text[end] == '}')
        end += 1
    return text[start:end]+'\n'


def corpus():
    result = []
    def add(name, xy, direct=0, base=0, width=640, height=240, pitch=320,
            entry=0, submit=0, status=0):
        surface = (base, pitch, width, height)
        packet = struct.pack('<IHHHIHHH6H', *surface, *surface, *xy)
        result.append(dict(name=name, packet=packet, xy=xy, base=base, pitch=pitch,
                           direct=direct, entry=entry, submit=submit, status=status))
    for name, xy in (
        ('viewer-up',(8,30,8,22,488,192)),('viewer-down',(8,22,8,30,488,192)),
        ('left',(10,22,8,22,488,192)),('right',(8,22,10,22,488,192)),
        ('down-right',(8,22,10,30,488,192)),('up-left',(10,30,8,22,488,192)),
        ('full-width-up',(0,1,0,0,640,239)),('full-width-down',(0,0,0,1,640,239)),
        ('full-height-right',(0,0,2,0,638,240)),('full-height-left',(2,0,0,0,638,240)),
        ('last-row',(0,238,0,239,640,1)),('same',(0,0,0,0,640,240)),
        ('empty-height',(0,0,0,0,640,0)),('empty-width',(0,0,0,1,0,239))):
        add(name,xy)
    add('busy-before-admission',(8,30,8,22,488,192),entry=1,status=1)
    add('submit-fault',(8,30,8,22,488,192),submit=5,status=5)
    add('non-screen-fallback',(0,0,2,1,62,40),direct=1,base=0x3f000,width=64,height=64,pitch=64)
    add('invalid-screen-height',(0,0,0,1,640,240),direct=1,status=6)
    return result


def replay(case, raw):
    """Interpret emitted byte-addressed BCBs, then compare to a whole snapshot."""
    status, enters, leaves, submits, unexpected = struct.unpack_from('<5H', raw)
    require(status == case['status'] and not unexpected, 'Status/descriptor mutation: '+case['name'])
    admitted = not case['direct'] and bool(case['xy'][5])
    require(enters == admitted and leaves == (admitted and not case['entry']),
            'Admission/retirement count: '+case['name'])
    sx,sy,dx,dy,width,height = case['xy']
    expected_count = 0 if case['entry'] or status==6 or not width or not height or (sx==dx and sy==dy) else 3 if case['direct'] else 1
    require(submits == expected_count, 'Unexpected hardware unit count: '+case['name'])
    if status: return
    before = bytes((i*37+i//97)&255 for i in range(0x80000))
    wanted = bytearray(before)
    for y in range(height):
        source = case['base']+(sy+y)*case['pitch']+sx//2
        dest = case['base']+(dy+y)*case['pitch']+dx//2
        wanted[dest:dest+width//2] = before[source:source+width//2]
    actual = bytearray(before)
    for n in range(submits):
        bcb = raw[10+n*21:10+(n+1)*21]
        source = int.from_bytes(bcb[:3],'little')
        dest = int.from_bytes(bcb[6:9],'little')
        ss,ds = (struct.unpack_from('<h',bcb,o)[0] for o in (3,9))
        xs,xd = (struct.unpack_from('<b',bcb,o)[0] for o in (5,11))
        columns = int.from_bytes(bcb[12:14],'little')+1
        rows = bcb[14]+1
        require(bcb[15:]==bytes([255,0,0,0,0,0]), 'Unexpected copy recipe')
        for y in range(rows):
            for x in range(columns):
                actual[dest+y*ds+x*xd] = actual[source+y*ss+x*xs]
    require(actual == wanted, 'Snapshot/overlap mismatch: '+case['name'])


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    driver=ROOT/'platform/altirraos/vbxe.c'
    renderer=ROOT/'ports/gem4xe/adapter/gem-vbxe.c'
    text=driver.read_text()
    selected=''.join(function(text,s) for s in ('static UWORD extent(', 'UWORD VbxeBlitExtent(', 'static void word(', 'static UWORD surface('))
    start=text.index('struct CopySetup {');end=text.index('};',start)+2
    selected+=text[start:end]+'\n'
    selected+=''.join(function(text,s) for s in ('static UWORD prepare_copy(', 'static void copy_record(', 'UWORD VbxeOwnerCopyRect('))
    (out/'screen-copy-driver.inc').write_text(selected)
    (out/'screen-copy-renderer.inc').write_text(function(renderer.read_text(),'UWORD GemDrawingCopyBorrow('))
    cases=corpus()
    header='#define SCREEN_COPY_CASES '+str(len(cases))+'\nstruct ScreenCase { UBYTE packet[32]; UWORD direct,entryStatus,submitStatus; };\nstatic const struct ScreenCase screenCases[]={\n'
    for c in cases:
        header+='{{'+','.join(map(str,c['packet']))+'},%d,%d,%d},\n'%(c['direct'],c['entry'],c['submit'])
    (out/'screen-copy-cases.h').write_text(header+'};\n')
    foreign=emit(out,[ROOT/'tests/programs/screen_copy.c'],[ROOT/'c/calypsi/image-info.s'],(),True,
                 roots=['ScreenCopyProbe','ScreenCopyResults'])
    source=out/'probe.act'
    source.write_text('MODULE SCREENCOPYTEST\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
        '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%foreign['symbols']['ScreenCopyProbe'])
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
            foreign_image=foreign,optimize=True,console=False)
    require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned observer')
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN)
        runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        ownership(b,p,p['output'])
        require(data(b,p['image'],'result',True)==[0,0],'Incomplete emitted probe')
        raw=b.memdump(foreign['symbols']['ScreenCopyResults'],len(cases)*346)
        for i,case in enumerate(cases):replay(case,raw[i*346:(i+1)*346])
    report=dict(status='pass',tier='development',qualification=False,cases=[c['name'] for c in cases],
        machine=machine,runtime=runtime,native_sha256=sha256(p['xex']),
        source_sha256={str(s.relative_to(ROOT)):sha256(s) for s in (driver,renderer,ROOT/'tests/programs/screen_copy.c')})
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Screen copy snapshot checks passed:',len(cases),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
