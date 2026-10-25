#!/usr/bin/env python3
"""WB2: emitted logical editing and physical GEM interaction checks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data


def logical(out,reuse=False,paint=False,motion=False):
    out.mkdir(parents=True,exist_ok=True)
    probe_name='BasicPaint' if paint else 'BasicEditor'
    sources=[ROOT/('tests/programs/basic_paint.c' if paint else 'tests/programs/basic_editor.c'),ROOT/'examples/gem-basic/document.c',
             ROOT/'examples/gem-basic/editor.c',ROOT/'examples/gem-basic/editor-paint.c',ROOT/'examples/gem-basic/assist.c',ROOT/'examples/gem-basic/assist-ui.c',ROOT/'c/calypsi/exec.c']
    if not reuse:
        # Keep unused GUI entry points discardable in this key-only probe;
        # production painting/event behavior is covered by the loadable APP.
        f=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),True,
            roots=[probe_name+'Probe',probe_name+'Checks',*(['BasicPaintStats','BasicCopyStats','BasicPaintSizes'] if paint else [])],
            definitions={**{name:['--no-interprocedural-cross-jump'] for name in ('editor.c','editor-paint.c','assist-ui.c')},
                **({'basic_paint.c':['-DBASIC_MOTION_PROBE=1']} if motion else {})})
        (out/'c-image.json').write_text(json.dumps(f,indent=2)+'\n')
        source=out/'probe.act'
        source.write_text('MODULE BASICEDITOR\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
            '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%f['symbols'][probe_name+'Probe'])
        p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
            task_capacity=8,foreign_image=f,optimize=True,console=False,stack_checks=True)
    else:p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text())
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',tier='development',qualification=False,slice='WB2',case='motion and failure' if motion else 'emitted painter' if paint else 'logical keys',
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in sources},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
            report['machine']=verify_machine(b,rom,pin)
            runtime,_=execute(b,p,timeout=180,frame_limit=9000,timer_irq=True)
            observed=data(b,p['image'],'result',True)
            if paint and observed!=[0,0]:
                report['painter_failure']={name:b.peek16(f['symbols'][name]) for name in
                    ('invalid','locked','diagnostic','count')}
                for name,size in (('e',7296),('pixels',12800),('expected',12800)):
                    (out/(name+'.bin')).write_bytes(bytes(b.memdump(f['symbols'][name],size)))
            require(observed==[0,0],'Editor assertion line: '+str(observed))
            ownership(b,p,p['output'])
            report.update(status='pass',runtime=runtime,checks=b.peek16(f['symbols'][probe_name+'Checks']))
            if paint:
                names=('top_newline','top_join','middle_newline','middle_join','single_character',
                       'scroll_up','scroll_down','scroll_left','scroll_right','blank_newline')
                fields=('source_glyphs','status_glyphs','updates','empty_updates','paint_turns',
                        'total_glyphs','text_calls','full_row_clears')
                raw=bytes(b.memdump(f['symbols']['BasicPaintStats'],len(names)*len(fields)*4))
                values=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                report['drawing_work']={name:dict(zip(fields,values[i*8:(i+1)*8]))
                                        for i,name in enumerate(names)}
                raw=bytes(b.memdump(f['symbols']['BasicCopyStats'],len(names)*8))
                for i,name in enumerate(names):
                    report['drawing_work'][name].update(copies=int.from_bytes(raw[i*8:i*8+4],'little'),
                        copied_pixels=int.from_bytes(raw[i*8+4:i*8+8],'little'))
                raw=bytes(b.memdump(f['symbols']['BasicPaintSizes'],12))
                report['appearance_layout']=dict(zip(('refresh_payload','refresh_reserved','refresh_union',
                    'motion_payload','motion_reserved','editor_model'),[int.from_bytes(raw[i:i+2],'little') for i in range(0,12,2)]))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true');p.add_argument('--paint',action='store_true');p.add_argument('--motion',action='store_true');a=p.parse_args();logical(a.output.resolve(),a.from_build,a.paint or a.motion,a.motion)
