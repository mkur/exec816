#!/usr/bin/env python3
"""Repeatable production VDI text benchmark; coarse ticks and independent scanout."""
import argparse
import json
import sys
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract, PORT
from gem_vdi_inputs import local_inputs
from library_paths import read_source
from generate_gem_vdi import expected_layout
from native_program import ROOT, build, compiler, sha256
root=ROOT

def build_benchmark(output, optimize=True):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True);src=out/'selected/src'
    extraction=extract(out/'selected');service=PORT/'service';adapter=PORT/'adapter'
    sources=[root/'c/calypsi/exec.c',root/'c/calypsi/display.c',root/'c/calypsi/input.c',
        root/'platform/altirraos/vbxe.c',service/'gem-validation.c',service/'gem-service.c',
        service/'gem-client.c',src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',
        src/'vdi/dev_vbxe.c',adapter/'gem-vbxe.c',root/'tests/programs/gem_text_benchmark.c']
    foreign=emit(out,sources,[root/'c/calypsi/gateway.s',root/'c/calypsi/display.s',root/'c/calypsi/input.s',
        root/'c/calypsi/image-info.s',root/'platform/altirraos/vbxe-map.s',root/'tests/programs/gem_text_marks.s'],['GemServiceWorker'],
        optimize=optimize,includes=[src,service,adapter],
        definitions={'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_']},
        probes=[(service/'gem-layout.c',expected_layout())])
    foreign['provenance'].update(purpose='Text-only throughput, no cursor or disk, production renderer and hardware reads',
        extraction=extraction,local_inputs=local_inputs(),
        source_inputs={str(p.relative_to(root)):sha256(p) for p in sources})
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=out/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n' for name in ('main','stage','ExecDisplayEntries','ExecInputEntries')))
    source=out/'launcher.act'
    template=root/'tests/programs/gem_text_launcher.act'
    source.write_text(read_source(template,{'c-image.inc':include,
        '../../c/calypsi/display-bridge.inc':root/'c/calypsi/display-bridge.inc',
        '../../c/calypsi/input-bridge.inc':root/'c/calypsi/input-bridge.inc'}))
    program=build(compiler(root/'build/actionc'),source,out/'program',optimize=optimize,
        tasks=True,task_capacity=8,console=False,foreign_image=foreign)
    return program,foreign

import adapter_state as adapter
from native_program import read_build,execute,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_heap_api import clean_ownership
from stack_budget import stack_usage
from gem_render_oracle import Raster,font_bytes
from test_gem_interactive import pixels


def run(output, mode='opt', replay=False, observe=False):
    from gem_text_trace import observation, summarize
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    if not replay: build_benchmark(out, mode=='opt')
    p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text());sy=f['symbols']
    require(p['build']['optimize']==(mode=='opt'),'Replay optimization differs')
    report=dict(status='running',tier='development',mode=mode,scope='Production VDI text, fill and driver copy, no cursor or disk; built-in 8x8, repeated strings, complete 80x30 screen. Phase 0 has no pointer capture; phase 1 retains an idle ST lease.',
        xex_sha256=sha256(p['xex']),build=p['build'],foreign_provenance=f['provenance'],pin=PIN,
        source_inputs={str(q.relative_to(root)):sha256(q) for q in (root/'tests/programs/gem_text_benchmark.c',root/'tests/programs/gem_text_launcher.act',root/'tests/programs/gem_text_marks.s',root/'tools/gem_text_trace.py',Path(__file__))},
        observed=observe,timing='Target DisplayTicks around complete GemCall loop, 20 ms tick granularity; font initialization, clearing and host scanout checks excluded.',
        bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0),cases=[])
    try:
        with observation(out,f,observe) as marks, emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned bridge')
            report['machine']=verify_machine(b,ROM,PIN)
            b._cmd_ok('MOUSE ST')
            def get(name):return b.peek16(sy[name])
            def reach(condition):
                marker=p['labels']['native_nmi'];b.bp_clear_all();b.bp_set(marker,condition=condition)
                run_to(b,marker,condition=condition,frame_limit=18000,timeout=180)
                b.bp_clear_all()
            def before(b):
                if observe:b.profile_start()
                for i in range(26):
                    reach(f'(dw(${sy["checkpoint"]:x})={i+1})&(db(${adapter.CURRENT:x})=0)')
                    require(get('failures')==0,'Failed target operation')
                    raw=b.memdump(sy['results']+i*16,16)
                    values=[int.from_bytes(raw[j:j+2],'little') for j in range(0,16,2)]
                    case=dict(zip(('phase','kind','glyphs','calls','start','end','ticks','status'),values))
                    require(case['status']==0,'Invalid benchmark result')
                    case.update(seconds=case['ticks']/50,glyphs_per_second=case['glyphs']*50/case['ticks'] if case['ticks'] else None,
                        milliseconds_per_call=case['ticks']*20/case['calls'])
                    # Wait for the last drawn scanline outside the timed interval.
                    reach(f'@frame>{b.eval_expr("@frame")+1}')
                    r=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
                    chars=[65+j%26 for j in range(64)];kind=case['kind']
                    if kind==5:
                        for row in range(30):
                            r.apply(8,[0,row*8+6],chars)
                            r.apply(8,[512,row*8+6],chars[:16])
                    elif kind==11:r.apply(11,[0,0,639,239])
                    elif kind!=12:
                        if kind==6:chars=[32]*64
                        if kind==7:chars=[ord('W')]*64
                        if kind==8:chars=[32 if j%2 else 65+j%26 for j in range(64)]
                        if kind==10:r.apply(22,ints=[0])
                        r.apply(8,[-3 if kind==9 else 33 if kind==4 else 32,64],
                                chars[:[1,8,32,64,64,0,64,64,64,8,64][kind]])
                    folder=out/f'case-{i}';folder.mkdir(exist_ok=True)
                    expected=r.packed() if kind!=12 else bytes(((y+8 if y<232 else y)%16)*17
                                                                         for y in range(240) for x in range(320))
                    case['pixels_sha256']=pixels(b,folder,expected)
                    case['status']='pass';report['cases'].append(case)
                    print(json.dumps(case),flush=True)
                    b.memload(sy['gate'],(i+1).to_bytes(2,'little'))
            runtime,_=execute(b,p,before_run=before,frame_limit=4000,timeout=120)
            if observe:b.profile_stop()
            require(get('failures')==0 and get('finished')==1,'Target incomplete')
            clean_ownership(b,p,p['output'])
            report.update(runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']),checks=get('checks'))
        if observe:
            report['observation']=summarize(out/'emulator.log',marks)
            require(len(report['observation'])==len(report['cases']),'Missing measured cases')
        report['status']='pass'
        if observe:(out/'observed-results.json').write_text(json.dumps(report,indent=2)+'\n')
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--replay',action='store_true')
    p.add_argument('--observe',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.replay,a.observe)
