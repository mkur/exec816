#!/usr/bin/env python3
"""One frame, one occluder and selected subtrees through the real GEM binding."""
import argparse
import json
import os
import re
import shutil
from pathlib import Path
from unittest.mock import patch

from build_gem_desktop import build_desktop
from generate_desktop import layout as desktop_layout
from generate_gem_objects import layout as gem_layout
from library_paths import read_source
from native_program import ROOT, command, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from stack_budget import stack_usage
from sio_transaction_trace import read_events
from gem_render_oracle import font_bytes, PENS, DESKTOP_PALETTE
from magic_frame_raster import model, decode


def pixels(out,cache,result):
    font=font_bytes(cache/'selected/src/vdi/font8x8.c')
    rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
    colours={hardware:rgb[i*3:i*3+3][::-1] for i,hardware in enumerate(PENS)}
    for phase in result['phases']:
        raster=model(font,phase['windows'],phase['focus'])
        raw=Path(phase['screen']).read_bytes()
        x,y,w,h=decode(phase['windows'][0])['overall']
        count=0
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                offset=yy*phase['stride']+(xx+16)*4
                want=colours[raster.pixels[yy*640+xx]]
                actual=raw[offset:offset+3]
                require(actual==want,'Frame pixel differs at '+str((phase['stage'],xx,yy))+
                        ': '+actual.hex()+' != '+want.hex())
                count+=1
        phase['verified_pixels']=count


def build(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    foreign = json.loads((cache/'c-image.json').read_text())
    provenance=foreign['provenance'];tools=provenance['tools']
    changed=[]
    for name,digest in provenance['source_inputs'].items():
        if sha256(ROOT/name)!=digest:changed.append(name)
    for name,digest in provenance['header_inputs'].items():
        require(sha256(ROOT/name)==digest,'Changed cached C header: '+name)
    # A focused renderer edit needs one recompiled object. All other source,
    # header, compiler and linker inputs remain the checked provider inputs.
    require(all(n=='ports/gem4xe/adapter/gem-vbxe.c' for n in changed),
            'Rebuild the provider for these inputs: '+str(changed))
    objects=list(provenance['link_objects'])
    for name in changed:
        target=out/'gem-vbxe.o'
        includes=[ROOT/'c/include',ROOT/'platform/altirraos',cache/'drawing',
            cache/'selected/src',ROOT/'ports/gem4xe/adapter']
        include_args=[v for path in includes for v in ('-I',path)]
        command([tools['cc65816']['path'],*provenance['compiler_flags'],
            *provenance['source_options']['gem-vbxe.c'],*include_args,'-c',
            '--list-file',out/'gem-vbxe.lst','-o',target,ROOT/name])
        index=next(i for i,p in enumerate(objects) if Path(p).stem.endswith('-gem-vbxe'))
        objects[index]=str(target)
        provenance['source_inputs'][name]=sha256(ROOT/name)
    # Invoke's public contract is LONG __simple_call(ULONG). Pointer-taking
    # GEM routines use Calypsi's regular ABI. Three test-only wrappers bridge
    # that boundary; relink verified objects instead of rebuilding the provider.
    bridge=out/'frame-call.c'
    bridge.write_text('''#include <gem.h>
#include <exec816/aes.h>
LONG EXEC_CALL FrameAttach(ULONG value) {
    return ExecAESAttach((struct MsgPort *)value);
}
LONG EXEC_CALL FramePB(ULONG value) {
    AESPB *pb=(AESPB *)value;
    aes_call(pb);return pb->int_out[0];
}
LONG EXEC_CALL FrameDetach(ULONG value) {
    (void)value;return ExecAESDetach();
}
''')
    obj=out/'frame-call.o'
    command([tools['cc65816']['path'],*provenance['compiler_flags'],'-I',ROOT/'c/include',
             '-c','--list-file',out/'frame-call.lst','-o',obj,bridge])
    header=(cache/'drawing/link.lst').read_text().split('Module summary')[0]
    roots=re.findall(r'--root-symbol\s+(\w+)', ' '.join(l.strip('# ') for l in header.splitlines()))
    require('ConsoleBitmapEntry' in roots and 'GEMDesktopStart' in roots,'Missing original C roots')
    root_args=[arg for name in (*roots,'FrameAttach','FramePB','FrameDetach') for arg in ('--root-symbol',name)]
    overrides=[arg for name in provenance['runtime_source_overrides']['symbol_overrides']
               for arg in ('--override',name)]
    attributes=[arg for name,value in provenance['runtime_attributes'].items()
                for arg in ('--rtattr',name+'='+value)]
    elf=out/'frame-provider.elf'
    command([tools['ln65816']['path'],'--hosted','--program-root','main','--program-start','main',
        *root_args,*attributes,*overrides,'--no-data-init-table-section',
        '--no-automatic-placement-rules','--list-file',out/'frame-provider.lst','-o',elf,
        *objects,obj,ROOT/'c/calypsi/layout.scm'])
    from calypsi_image import read_image
    foreign=read_image(elf,[])
    foreign['provenance']={**provenance,**foreign['provenance'],
        'test_bridge_sha256':sha256(bridge),'reused_objects_from':str(cache),
        'link_objects':[*objects,str(obj)],'root_symbols':roots+['FrameAttach','FramePB','FrameDetach']}
    symbols = out/'frame-symbols.inc'
    symbols.write_text('\n'.join('CONST C_'+target+'=$%x'%foreign['symbols'][name]
        for target,name in [('AES_ATTACH','FrameAttach'),('AES_CALL','FramePB'),
                            ('AES_DETACH','FrameDetach')])+'\n')
    source = out/'frame-tree.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_frame_tree.act',
                                  {'frame-symbols.inc':symbols}))
    with patch('build_gem_desktop.drawing', lambda *a, **kw: foreign):
        build_desktop(out, source=source, build_applications=False,
            release_compiler=True, system_mount='D1',
            dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,
                             profile=4,format=2)])
    return foreign


def run(out, cache, reuse=False):
    out=out.resolve();cache=cache.resolve()
    foreign=json.loads((out/'c-image.json').read_text()) if reuse else build(out,cache)
    p=read_build(out/'program');sy=foreign['symbols']
    result=dict(status='running',tier='development',qualification=False,phases=[])
    at=lambda module,name:next(r['address'] for r in p['image']['data']
        if '_'+module+'_'+name.upper()+'_' in r['name'])
    marker=sy['frame_object']
    saved=os.environ.get('EXEC816_LATENCY_PCS')
    os.environ['EXEC816_LATENCY_PCS']=f'{marker:x}'
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for name,value in PIN['configuration'].items():
                b.config(name,str(value).lower() if isinstance(value,bool) else value)
            shutil.copyfile(cache/'system.atr',out/'system.atr')
            b.mount(0,str(out/'system.atr'))
            result['machine']=verify_machine(b,ROM,PIN)
            number=lambda a,n=2:int.from_bytes(b.memdump(a,n),'little')
            def reach(condition):
                pc=p['labels']['native_cop'];condition=f'(@xpc=${pc:x})&({condition})'
                b.bp_clear_all();b.bp_set(pc,condition=condition)
                faults=[p['labels'][n] for n in ('heap_fault','stack_overflow','arithmetic_fault','done')]
                for fault in faults:b.bp_set(fault)
                original=b.regs
                def registers():
                    regs=original()
                    if b.eval_expr('@xpc') in faults:
                        import adapter_state as adapter
                        result['guest_fault']=dict(status=number(adapter.STATE),
                            checks=number(at('GEMFRAMETREETEST','checks')),
                            pb=b.memdump(at('GEMFRAMETREETEST','pb'),114).hex(),regs=regs)
                        raise RuntimeError('Frame guest stopped: '+str(result['guest_fault']))
                    return regs
                b.regs=registers
                try:run_to(b,pc,condition=condition,timeout=180,frame_limit=12000)
                finally:b.regs=original
            def before(bridge):
                for stage in range(1,6):
                    reach(f'dw(${at("GEMFRAMETREETEST","phase"):x})={stage}')
                    reach('@frame>=%d'%(b.eval_expr('@frame')+3))
                    if stage==1:b.profile_start()
                    desktop=number(at('DESKSTATE','service'),3)
                    df=desktop_layout()['Service']['fields'];wf=desktop_layout()['Window']['fields']
                    windows=[]
                    for slot in range(6):
                        address=number(desktop+df['windows']+slot*3,3)
                        if not address:continue
                        raw=b.memdump(address,desktop_layout()['Window']['size'])
                        frame=raw[wf['frame']:wf['frame']+gem_layout()['Frame']['size']]
                        windows.append(dict(address=address,raw=raw.hex(),frame=frame.hex()))
                    screen=out/f'phase-{stage}.bgra'
                    display=b.rawscreen(str(screen))
                    result['phases'].append(dict(stage=stage,tick=b.eval_expr('@clk')&0xffffffff,
                        windows=windows,focus=number(desktop+df['focus'],4),screen=str(screen),
                        stride=display.stride,stack=stack_usage(b,p['build']['memory'])))
                    b.poke16(at('GEMFRAMETREETEST','go'),stage)
                b.profile_stop()
                b.bp_clear_all()
            try:
                result['runtime'],_=execute(b,p,before_run=before,timeout=300,frame_limit=30000)
            except Exception:
                result['stopped_checks']=number(at('GEMFRAMETREETEST','checks'))
                result['stopped_pb']=b.memdump(at('GEMFRAMETREETEST','pb'),114).hex()
                raise
            ownership(b,p,p['output'])
            result['checks']=number(at('GEMFRAMETREETEST','checks'))
        events=read_events(out/'emulator.log',kinds={'cpu'})
        visits=[(t,int(e[5],16)) for t,e in events if int(e[4],16)==marker]
        for previous,current in zip(result['phases'],result['phases'][1:]):
            current['visits']=[obj for tick,obj in visits if previous['tick']<tick<=current['tick']]
        for stage,wanted in [(2,{9,10}),(3,{13,14})]:
            actual=result['phases'][stage-1]['visits']
            require(actual and set(actual)==wanted,'Unexpected selected subtree visits: '+str(actual))
        pixels(out,cache,result)
        result['status']='pass'
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:
        if saved is None:os.environ.pop('EXEC816_LATENCY_PCS',None)
        else:os.environ['EXEC816_LATENCY_PCS']=saved
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Frame tree passed:',result['checks'],'binding checks',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--provider-cache',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    run(args.output,args.provider_cache,args.reuse)
