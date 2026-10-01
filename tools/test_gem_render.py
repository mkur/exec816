#!/usr/bin/env python3
"""G4: real service, upstream renderer and bounded driver pixel agreement."""
import argparse
import hashlib
import json
import sys
import re
from pathlib import Path
import adapter_state as adapter
from build_gem_vdi import build_render_probe
from gem_render_oracle import Raster,corpus,font_bytes,PENS,PALETTE
from gem_vdi_inputs import source_inputs
from native_program import ROOT,execute,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from stack_budget import stack_usage
from test_heap_api import clean_ownership
from test_cooperative import data
from test_large_stacks import observe

PIN=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())

def read_capture(b,address,size,program):
    """Bulk test read at paused native NMI entry. Preserve CPU and borrowed RAM.

    $6000-$6FFF is unused post-startup in the eight-Task memory profile. This
    observer masks IRQ/NMI while copying upper RAM; it is not a preemption test.
    No production reservation, aperture mapping or platform ABI changes.
    """
    require(program['build']['memory']['task_pools'][-1]['stack_base']+
            program['build']['memory']['task_pools'][-1]['stack_bytes']+16<=0x6000,'Observer overlaps idle')
    pc=b.eval_expr('@xpc');base=adapter.TEST_FAR_WRITE;buffer=0x6000
    require(pc==program['labels']['native_nmi'],'Observer requires NMI rendezvous')
    oldpc=b.memdump(pc,3);scratch=b.memdump(base,256);oldbuffer=b.memdump(buffer,4096)
    nmien=int(b.antic()['NMIEN'].lstrip('$'),16);b.hwpoke(0xd40e,0)
    output=bytearray()
    try:
        for offset in range(0,size,4096):
            count=min(4096,size-offset)
            require(count%2==0,'Observer requires even size')
            code=bytearray.fromhex('0878c23048daa20000')
            loop=len(code)
            code+=b'\xbf'+(address+offset).to_bytes(3,'little')
            code+=b'\x9f'+buffer.to_bytes(3,'little')+b'\xe8\xe8\xe0'+count.to_bytes(2,'little')
            code+=bytes([0x90,(loop-len(code)-2)&255])+bytes.fromhex('fa6828')
            done=base+len(code);code+=b'\x4c'+done.to_bytes(2,'little')
            b.memload(base,code);b.memload(pc,b'\x4c'+base.to_bytes(2,'little'))
            bp=b.bp_set(done)
            try: run_to(b,done,frame_limit=10,timeout=5)
            finally: b.bp_clear(bp)
            output+=b.memdump(buffer,count)
            b.memload(pc,oldpc);b.memload(done,b'\x4c'+pc.to_bytes(2,'little'))
            bp=b.bp_set(pc)
            try: run_to(b,pc,frame_limit=10,timeout=5)
            finally: b.bp_clear(bp)
    finally:
        b.memload(pc,oldpc);b.memload(base,scratch);b.memload(buffer,oldbuffer);b.hwpoke(0xd40e,nmien)
    return bytes(output)


def run(output,mode,replay=False,production=False):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='G4',mode=mode,cases=[],production_status_reads=production,test_harness_sha256=sha256(Path(__file__)))
    upstream=ROOT/'build/gem-vdi/upstream'
    source_inputs(upstream)
    sys.path.insert(0,str(upstream/'tools'))
    import vdiref
    font=font_bytes(upstream/'src/vdi/font8x8.c')
    require(len(font)==2048,'Invalid font strip')
    model=Raster(font); donor=vdiref.VDI()
    donor.fill_per=0
    try:
        if replay: program,foreign=read_build(output/'program'),json.loads((output/'c-image.json').read_text())
        else: program,foreign=build_render_probe(output,optimize=mode=='opt',instrument=not production)
        require(foreign['provenance']['status_read_instrumentation']==(not production),'Wrong status instrumentation')
        report.update(build=program['build'],font_sha256=hashlib.sha256(font).hexdigest(),provenance=foreign['provenance'],
            bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0),
            c_map=dict(segments=[dict(address=s['address'],bytes=len(s['bytes']),executable=s['executable']) for s in foreign['segments']],zero_fill=foreign['zero_fill'],reserved_upper_bytes=131072))
        symbols=foreign['symbols']; saved={}
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=PIN) as b:
            report['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            get=lambda key,n=2:int.from_bytes(b.memdump(symbols[key],n),'little')
            def put(key,value): b.memload(symbols[key],int(value).to_bytes(2,'little'))
            def rendezvous(n):
                marker=program['labels']['native_nmi']
                cond=f'(dw(${symbols["checkpoint"]:x})={n})&(db(${adapter.CURRENT:x})=0)'
                b.bp_clear_all(); b.bp_set(marker,condition=cond)
                run_to(b,marker,condition=cond,frame_limit=18000,timeout=180)
                b.bp_clear_all()
            sentinel=bytes((i*37+11)&255 for i in range(4096))
            def before(b):
                saved['os']=b.memdump(0x22f,3);saved['screen_at']=b.peek16(0x58);saved['screen']=b.memdump(saved['screen_at'],960)
                b.memload(0x8000,sentinel)
                rendezvous(1)
                require(get('failures')==0,'Startup failed')
                n=1
                for case in corpus():
                    if production and (case.get('fault') or case['name']=='invalidated'): continue
                    if production and case['name']=='reopen':
                        # Production control closes cleanly before opening again.
                        put('opcode',2);put('snapshot',0);put('gate',n);n+=1;rendezvous(n)
                    put('opcode',case['op']);put('subopcode',1 if case['op']==11 else 0)
                    put('pairs',len(case['points'])//2);put('words',len(case['ints']))
                    for key in ('points','ints'):
                        b.memload(symbols[key],b''.join((v&65535).to_bytes(2,'little') for v in case[key]))
                    put('boundary',case.get('boundary',0));put('batch',case.get('batch',0))
                    snapshot=not case.get('boundary') and case['op'] in (1,3,4,6,8,11) and not case.get('status')
                    put('snapshot',int(snapshot));put('inject',int(case.get('fault',False) and not case.get('batch')))
                    if not production: put('stopped',0)
                    put('gate',n);n+=1
                    if case['name']=='open':
                        placement=re.search(r"vbxe_font_changed in section 'farcode'\s+placed at address ([0-9a-f]+)-([0-9a-f]+)", (output/'link.lst').read_text())
                        low,high=(int(x,16) for x in placement.groups())
                        report['gem_preemption']=observe(b,program,[symbols['stage']],slots=(6,),code_bank=12,pc_range=(low,high+1))
                    rendezvous(n)
                    result=dict(case,answer=get('answer'),completed=get('completed'),reply_words=get('replyWords'))
                    report['cases'].append(result)
                    require(result['answer']==case.get('status',0),f'{case["name"]}: status {result["answer"]}')
                    if not case.get('status') and case['op']!=2:
                        require(result['completed']==1,'Wrong completed prefix')
                        if case['op']==1:
                            donor=vdiref.VDI();donor.fill_per=0
                            work=list(int.from_bytes(b.memdump(symbols['reply']+i*2,2),'little') for i in range(57))
                            require(work[0:2]==[639,239] and work[13:16]==[16,1,1] and work[40:45]==[0]*5,'False workstation capabilities')
                            result['workout']=work
                            actual_font=read_capture(b,symbols['fontMasks'],18432,program)
                            masks=bytearray()
                            for odd in (False,True):
                                for row in range(8):
                                    for glyph in range(256):
                                        pixels=[15 if font[row*256+glyph]&(128>>bit) else 0 for bit in range(8)]
                                        if odd: pixels=[0]+pixels+[0]
                                        masks.extend((x<<4)|y for x,y in zip(pixels[::2],pixels[1::2]))
                            require(actual_font==masks,'Font expansion changed')
                            result['font_masks_sha256']=hashlib.sha256(actual_font).hexdigest()
                            palette=bytearray(48)
                            for pen,hw in enumerate(PENS): palette[hw*3:hw*3+3]=PALETTE[pen*3:pen*3+3]
                            require(b.memdump(symbols['palette'],48)==palette,'Palette order changed')
                            result['palette_rgb']=palette.hex()
                        else:
                            donor.call(case['op'],case['points'],case['ints'],sub=1 if case['op']==11 else 0)
                        model.apply(case['op'],case['points'],case['ints'])
                        expected=model.packed()
                        require(expected==bytes(donor.dev.s.mem[:76800]),'Independent/upstream disagreement: '+case['name'])
                        if snapshot:
                            actual=read_capture(b,get('capture',4),76800,program)
                            (output/'actual.bin').write_bytes(actual);(output/'expected.bin').write_bytes(expected)
                            if actual!=expected:
                                diffs=[i for i,(a,e) in enumerate(zip(actual,expected)) if a!=e]
                                raise RuntimeError(f'{case["name"]}: {len(diffs)} wrong bytes, first {[(i,actual[i],expected[i]) for i in diffs[:8]]}')
                            result['pixels_sha256']=hashlib.sha256(actual).hexdigest()
                            previous=saved.get('pixels',bytes(76800))
                            changed=[(i%320*2+k,i//320) for i,(a,e) in enumerate(zip(previous,actual)) for k,mask in ((0,240),(1,15)) if (a&mask)!=(e&mask)]
                            result['changed_pixels']=len(changed)
                            result['changed_bounds']=[min(x for x,y in changed),min(y for x,y in changed),max(x for x,y in changed),max(y for x,y in changed)] if changed else None
                            saved['pixels']=actual
                        if case['op'] in (17,22,23,25,32):
                            require(result['reply_words']==1 and get('reply')==case['ints'][0],'Wrong setter reply')
                    elif case.get('fault'):
                        require(result['completed']==1 and result['reply_words']==1 and get('stopped')==1,'Fault falsely completed')
                    if case.get('screenshot'):
                        b.screenshot(str(output/'scene.png'))
                        (output/'scene.bin').write_bytes(saved['pixels'])
                        frame=b.rawscreen(str(output/'scanout.bgra'))
                        frame_pixels=(output/'scanout.bgra').read_bytes()
                        require((frame.width,frame.height)==(672,240),'Unexpected scanout geometry')
                        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
                        hardware=[None]*16
                        for pen,hw in enumerate(PENS): hardware[hw]=rgb[pen*3:pen*3+3][::-1]
                        scanout=b''.join(frame_pixels[y*frame.stride+16*4:y*frame.stride+656*4] for y in range(240))
                        # XRGB's fourth byte is not a color channel (VBXE stores luma there).
                        scanout=b''.join(scanout[i:i+3] for i in range(0,len(scanout),4))
                        expected_scanout=b''.join(hardware[v>>4]+hardware[v&15] for v in saved['pixels'])
                        require(scanout==expected_scanout,'Visible scanout/palette differs from VRAM')
                        result['scanout_sha256']=hashlib.sha256(scanout).hexdigest()
                        result['screenshot_sha256']=sha256(output/'scene.png')
                    require(get('failures')==0,'VRAM guard or readback failed')
                    require(b.memdump(0xd65e,2)==bytes(2),'Window open at reply')
                    print('Passed G4',mode,case['name'],flush=True)
                put('opcode',65535);put('gate',n)
            runtime,_=execute(b,program,before_run=before,frame_limit=4000,timeout=120)
            require(get('failures')==0 and get('finished')==1 and data(b,program['image'],'result',True)==[0],'Target incomplete')
            clean_ownership(b,program,program['output'])
            require(b.memdump(0x8000,4096)==sentinel,'CPU aperture modified')
            require(b.memdump(0x22f,3)==saved['os'] and b.memdump(saved['screen_at'],960)==saved['screen'],'OS display not restored')
            report.update(runtime=runtime,stack_usage=stack_usage(b,program['build']['memory']),checks=get('checks'))
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'Stack floor reached')
        report['status']='pass'
    except Exception as e: report.update(status='fail',error=str(e));raise
    finally: (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--production-control',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.replay,a.production_control)
