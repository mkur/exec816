#!/usr/bin/env python3
"""Emitted screen-copy descriptors against an independent snapshot oracle.

The real typed driver and renderer routines execute on the 65816. Substitute
only admission, overlay and hardware I/O boundaries; replay captured BCBs
against host VRAM. MGVIEW supplies the real ownership check.
"""
import argparse
import json
import struct
from pathlib import Path

from calypsi_build import emit
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from os_boundary import run_to
from generate_vbxe_tables import generate as generate_tables
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
            entry=0, submit=0, status=0, fail=0):
        surface = (base, pitch, width, height)
        packet = struct.pack('<IHHHIHHH6H', *surface, *surface, *xy)
        result.append(dict(name=name, packet=packet, xy=xy, base=base, pitch=pitch,
                           direct=direct, entry=entry, submit=submit, status=status,fail=fail))
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
    for name,xy in (
        ('viewer-odd-up',(1,30,1,22,616,192)),
        ('viewer-odd-down',(1,22,1,30,616,192)),
        ('odd-right',(41,20,49,20,400,177)),('odd-left',(49,20,41,20,400,177)),
        ('odd-down-right',(41,20,49,28,400,177)),('odd-up-left',(49,28,41,20,400,177)),
        ('odd-down-left',(49,20,41,28,400,177)),('odd-up-right',(41,28,49,20,400,177)),
        ('left-edge-only',(1,22,1,30,615,192)),('right-edge-only',(2,30,2,22,615,192)),
        ('one-low-nibble',(1,0,3,0,1,240)),('one-high-nibble',(638,0,636,0,1,240)),
        ('two-edge-pixels',(1,0,1,8,2,232)),('last-pixel',(639,238,637,239,1,1)),
        ('full-height-odd',(1,0,3,0,636,240)),('odd-same',(1,0,1,0,638,240))):
        add(name,xy)
    add('busy-odd-before-admission',(1,22,1,30,616,192),entry=1,status=1)
    for name,fail in [('edge-capture-submit',1),('edge-capture-fence',2),
                      ('interior-submit',3),('edge-restore-submit',4),('final-fence',5)]:
        add('fault-'+name,(1,22,1,30,616,192),fail=fail,status=5)
    # Exercise the shared mask producer directly, including the height byte's
    # 256-row encoding, compact frame pitches and multi-bank chunk advances.
    def mask(name,bytes,rows,mode=0,ss=1280,ds=512,am=255,xm=0,repeats=1,fail=0):
        add('mask-'+name,(0,0,0,0,0,0),direct=2,fail=fail,status=5 if fail else 0)
        result[-1]['mask']=(0,0x60000,ss,ds,bytes,rows,repeats,am,xm,mode)
    for mode in (0,3,4,5):
        mask('height-256-mode-'+str(mode),1,256,mode)
    mask('exact-work',16,256)
    mask('tail-and-wide-steps',17,256)
    mask('masked-tail-and-wide-steps',17,256,3)
    mask('three-chunks',273,21,3)
    mask('full-width',512,256,3)
    mask('record-capacity',1,1,repeats=65)
    mask('work-capacity',16,256,repeats=2)
    mask('fault-second-list',512,11,3,fail=2)
    mask('stipple',7,91,4,ss=0,ds=32,am=0,xm=0xf0)
    mask('compact-copy',7,182,ss=16,ds=320)
    mask('low-edge-and',1,182,4,ss=0,ds=320,am=0,xm=0xf0)
    mask('low-edge-or',1,182,3,ss=16,ds=320,am=0x0f)
    mask('high-edge-and',1,182,4,ss=0,ds=320,am=0,xm=0x0f)
    mask('high-edge-or',1,182,3,ss=16,ds=320,am=0xf0)
    return result


def replay_mask(case,raw):
    status,enters,leaves,submits,unexpected,count,lists,reads,writes=struct.unpack_from('<9H',raw)
    require(status==case['status'] and not unexpected,'Mask status/guards: '+case['name'])
    require(enters==leaves==1 and not (submits or reads or writes),'Mask boundaries: '+case['name'])
    source,dest,ss,ds,width,height,repeats,am,xm,mode=case['mask']
    limit=min(256,8192//(width*(3 if mode else 2)))
    records=[];work=0;pending=0;expected_lists=0
    for repeat in range(repeats):
        y=0
        while y<height:
            rows=min(limit,height-y);cost=width*rows*(3 if mode else 2)
            if pending==64 or work+cost>8192:
                expected_lists+=1;work=0;pending=0
            records.append((source+y*ss,dest+y*ds,rows));work+=cost;y+=rows;pending+=1
    expected_lists+=1
    if not status:
        require(lists==expected_lists,'Mask list count: '+case['name'])
        require(count==len(records)+1,'Mask record count: '+case['name'])
    else:require(lists==case['fail'],'Mask failure did not stop at requested list')
    actual=bytearray((i*37+i//97)&255 for i in range(0x80000));wanted=actual.copy()
    def apply(value,prior):
        value=(value&am)^xm
        return value if mode==0 else prior|value if mode==3 else prior&value if mode==4 else prior^value
    for repeat in range(repeats):
        for y in range(height):
            for x in range(width):
                at=dest+y*ds+x
                wanted[at]=apply(wanted[source+y*ss+x],wanted[at])
    index=0
    for n in range(count):
        kind=struct.unpack_from('<H',raw,18+n*26)[0]
        if kind==5:continue
        require(kind==1,'Unexpected mask event')
        bcb=raw[20+n*26:41+n*26]
        src=int.from_bytes(bcb[:3],'little');dst=int.from_bytes(bcb[6:9],'little')
        rows=bcb[14]+1
        require((src,dst,rows)==records[index],'Mask address/height: '+case['name'])
        require(int.from_bytes(bcb[3:5],'little')==ss and int.from_bytes(bcb[9:11],'little')==ds and
                int.from_bytes(bcb[12:14],'little')+1==width and bcb[5]==bcb[11]==1 and
                (bcb[15],bcb[16],bcb[20])==(am,xm,mode) and not any(bcb[17:20]),'Mask BCB fields')
        for y in range(rows):
            for x in range(width):
                at=dst+y*ds+x
                actual[at]=apply(actual[src+y*ss+x],actual[at])
        index+=1
    if not status:require(actual==wanted,'Mask pixels/suffix: '+case['name'])
    return dict(name=case['name'],status=status,raw_lists=lists,records=index)


def replay(case, raw):
    """Interpret emitted byte-addressed BCBs, then compare to a whole snapshot."""
    if 'mask' in case:return replay_mask(case,raw)
    status,enters,leaves,submits,unexpected,count,lists,reads,writes=struct.unpack_from('<9H',raw)
    require(status == case['status'] and not unexpected, 'Status/descriptor mutation: '+case['name'])
    sx,sy,dx,dy,width,height = case['xy']
    edges=(sx&1)+((sx+width)&1)
    admitted=0 if case['direct'] or not height else 1
    if case['entry']:admitted=case['entry']
    require(enters==admitted and leaves==enters-bool(case['entry']),
            'Admission/retirement count: '+case['name'])
    expected_count = 0 if case['entry'] or status==6 or not width or not height or (sx==dx and sy==dy) or width==edges or (case['fail'] and case['fail']<3) else 3 if case['direct'] else 1
    require(submits == expected_count, 'Unexpected hardware unit count: '+case['name'])
    facts=dict(name=case['name'],status=status,enters=enters,leaves=leaves,
               typed_submissions=submits,raw_lists=lists,edge_reads=reads,edge_writes=writes)
    require(reads==writes==0,'Unexpected CPU edge transfer: '+case['name'])
    if status:return facts
    require(lists==2*bool(edges and height),'Unexpected mask-list count: '+case['name'])
    before = bytes((i*37+i//97)&255 for i in range(0x80000))
    wanted = bytearray(before)
    for y in range(height):
        for x in range(width):
            source=case['base']+(sy+y)*case['pitch']+(sx+x)//2
            dest=case['base']+(dy+y)*case['pitch']+(dx+x)//2
            pixel=(before[source]>>(0 if (sx+x)&1 else 4))&15
            shift=0 if (dx+x)&1 else 4
            wanted[dest]=(wanted[dest]&~(15<<shift))|(pixel<<shift)
    actual = bytearray(before)
    for n in range(count):
        kind=struct.unpack_from('<H',raw,18+n*26)[0]
        payload=raw[20+n*26:44+n*26]
        if kind==5:
            # Every release permits another renderer to replace scratch.
            actual[0x36000:0x36000+480]=bytes([0x9b])*480
            continue
        require(kind in (1,2),'Unexpected hardware event')
        bcb=payload[:21]
        source = int.from_bytes(bcb[:3],'little')
        dest = int.from_bytes(bcb[6:9],'little')
        ss,ds = (struct.unpack_from('<h',bcb,o)[0] for o in (3,9))
        xs,xd = (struct.unpack_from('<b',bcb,o)[0] for o in (5,11))
        columns = int.from_bytes(bcb[12:14],'little')+1
        rows = bcb[14]+1
        mode=bcb[20]
        require(bcb[17:20]==bytes(3) and mode in (0,3,4),'Unexpected raster recipe')
        if kind==1:require(columns*rows*(3 if mode else 2)<=8192,'Raw record exceeds work bound')
        else:require(bcb[15:]==bytes([255,0,0,0,0,0]),'Unexpected typed-copy recipe')
        for y in range(rows):
            for x in range(columns):
                src=source+y*ss+x*xs;dst=dest+y*ds+x*xd
                require(0<=src<len(actual) and 0<=dst<len(actual),'BCB outside VRAM')
                value=(actual[src]&bcb[15])^bcb[16]
                if mode==0:actual[dst]=value
                elif mode==3:actual[dst]|=value
                else:actual[dst]&=value
    actual[0x36000:0x36000+480]=wanted[0x36000:0x36000+480]
    require(actual == wanted, 'Snapshot/overlap mismatch: '+case['name'])
    return facts


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
    text=renderer.read_text()
    (out/'screen-copy-mask.inc').write_text(''.join(function(text,s) for s in
        ('static void drain(', 'void blit_mask(', 'void blit_and(')))
    tables=generate_tables(out/'gem-vbxe-tables.h')
    cases=corpus()
    header='#define SCREEN_COPY_CASES '+str(len(cases))+'\nstruct MaskCase { ULONG source,dest; UWORD ss,ds,bytes,rows,repeats; UBYTE am,xm,mode; };\nstruct ScreenCase { UBYTE packet[32]; UWORD direct,entryAt,submitStatus,failAt; struct MaskCase mask; };\nstatic const struct ScreenCase screenCases[]={\n'
    for c in cases:
        mask=c.get('mask',(0,)*10)
        header+='{{'+','.join(map(str,c['packet']))+'},%d,%d,%d,%d,{'%(c['direct'],c['entry'],c['submit'],c['fail'])
        header+=','.join(str(v)+('UL' if i<2 else '') for i,v in enumerate(mask))+'}},\n'
    (out/'screen-copy-cases.h').write_text(header+'};\n')
    foreign=emit(out,[ROOT/'tests/programs/screen_copy.c'],[ROOT/'c/calypsi/image-info.s'],(),True,
                 roots=['ScreenCopyProbe','ScreenCopyResults'])
    source=out/'probe.act'
    source.write_text('MODULE SCREENCOPYTEST\nUSE CALYPSICALL\nUSE EXEC\nUSE HEAPCORE\n'
        'CARD phase,go,index\nLONGINT result\nPROC Main()\n\n'
        '  FOR index=0 TO %d DO\n'
        '    result=CALYPSICALL.Invoke(ADDRESS($%x),LONGCARD(index))\n'
        '    IF result<>0 THEN\n      HEAPCORE.Abort($fa00)\n    FI\n'
        '    phase=index+1\n    WHILE go<>phase DO\n      EXEC.Yield()\n    OD\n'
        '  OD\n\nRETURN\nENDMODULE\n'%(len(cases)-1,foreign['symbols']['ScreenCopyProbe']))
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
            foreign_image=foreign,optimize=True,console=False,task_capacity=8)
    require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned observer')
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN)
        at=lambda name:next(d['address'] for d in p['image']['data'] if '_SCREENCOPYTEST_'+name.upper()+'_' in d['name'])
        facts=[]
        def before(bridge):
            marker=p['labels']['native_cop']
            for i,case in enumerate(cases):
                condition=f'(@xpc=${marker:x})&(dw(${at("phase"):x})={i+1})'
                bridge.bp_clear_all();bridge.bp_set(marker,condition=condition)
                for label in ('done','stack_overflow','heap_fault'):bridge.bp_set(p['labels'][label])
                run_to(bridge,marker,condition=condition,timeout=30,frame_limit=1000)
                facts.append(replay(case,bridge.memdump(foreign['symbols']['ScreenCopyResults'],3346)))
                bridge.poke16(at('go'),i+1)
            bridge.bp_clear_all()
        runtime,_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
        ownership(b,p,p['output'])
        require(data(b,p['image'],'result',True)==[0,0],'Incomplete emitted probe')
    report=dict(status='pass',tier='development',qualification=False,cases=facts,tables=tables,
        machine=machine,runtime=runtime,native_sha256=sha256(p['xex']),
        source_sha256={str(s.relative_to(ROOT)):sha256(s) for s in (driver,renderer,ROOT/'tests/programs/screen_copy.c')})
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Screen copy snapshot checks passed:',len(cases),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
