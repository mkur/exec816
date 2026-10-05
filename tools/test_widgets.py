#!/usr/bin/env python3
"""Focused emitted AES admission, donor walks, form selection and context checks."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from extract_gem_aes import extract,PORT
from generate_widgets import expected_layout,layout
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine,read_build
from os_boundary import emulator
from stack_budget import stack_usage
from test_cooperative import data
from test_heap_api import clean_ownership


def build_model(out,optimize,state=False,input_probe=False):
    extraction=extract(out/'selected')
    sources=[ROOT/'c/calypsi/exec.c',PORT/'widgets-model.c',PORT/'widgets-graf.c',
        *(out/'selected'/n for n in ('aes-objects.c','aes-graf.c','aes-form.c')),
        ROOT/'tests/programs/widgets_model.c',ROOT/'tests/programs/widgets_native.c']
    if state or input_probe:sources += [PORT/'widgets-state.c']
    if state:sources += [ROOT/'tests/programs/widgets_state.c']
    if input_probe:sources += [PORT/'widgets-input.c',ROOT/'tests/programs/widgets_input.c']
    foreign=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],
        ['WidgetWorker'],optimize=optimize,includes=[PORT,out/'selected'],
        probes=[(PORT/'widget-layout.c',expected_layout())],
        definitions={'widgets_native.c':(['-DWIDGET_STATE_PROBE'] if state else [])+(['-DWIDGET_INPUT_PROBE'] if input_probe else []),
                     'widgets-state.c':['-DWIDGET_STATE_TESTS']} if state or input_probe else {})
    foreign['provenance'].update(aes_extraction=extraction,
        source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in sources})
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    checks='\n'.join(f'  IF SIZEOF(WIDGETTYPES.{n})<>{v["size"]} THEN\n    result=1\n    RETURN\n  FI\n' for n,v in layout().items())
    source=out/'launcher.act'
    source.write_text('MODULE WIDGETPROBE\nUSE WIDGETTYPES\nCARD FUNC POINTER cMain()\nCARD result\nPROC Main()\n\n'+checks+
        f'  LET entry=ADDRESS POINTER(@cMain)\n  entry^=${foreign["symbols"]["main"]:x}\n  result=cMain()\n\nRETURN\n\nENDMODULE\n')
    program=build(compiler(ROOT/'build/actionc'),source,out/'program',optimize=optimize,
        tasks=True,task_capacity=8,console=False,foreign_image=foreign)
    return program,foreign


def run(out,mode,replay=False,state=False,input_probe=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    report=dict(slice='AW4' if input_probe else ('AW2' if state else 'AW0'),tier='development',status='running',mode=mode)
    try:
        p,f=(read_build(out/'program'),json.loads((out/'c-image.json').read_text())) if replay else build_model(out,mode=='opt',state,input_probe)
        pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
        binary=ROOT/pin['mouse_input']['tooling']['binary'];rom=ROOT/'build/firmware/altirraos-816.rom'
        require(sha256(binary)==pin['mouse_input']['tooling']['sha256'],'Wrong AES emulator')
        require(sha256(rom)==pin['rom']['sha256'],'Wrong AES ROM')
        memory=p['build']['memory']
        before=json.loads((ROOT/'build/desktop/mp-baseline/program/build.json').read_text())['memory']
        for key in ('bank_zero_budget','task_pools','regions'):
            require(memory[key]==before[key],'Changed bank-zero '+key)
        with emulator(binary.parent,rom,out,pin=pin) as b:
            report['machine']=verify_machine(b,rom,pin)
            runtime,_=execute(b,p,frame_limit=6000,timeout=180)
            read=lambda n:int.from_bytes(b.memdump(f['symbols'][n],2),'little')
            report.update(checks=read('widgetChecks'),failures=read('widgetFailures'),
                failure_at=read('widgetFailureAt'),progress=read('progress'),runtime=runtime,
                stack_usage=stack_usage(b,memory))
            if state:report.update(state_checks=read('WidgetStateChecks'),state_failures=read('WidgetStateFailures'))
            if input_probe:report.update(input_checks=read('WidgetInputChecks'),input_failures=read('WidgetInputFailures'))
            require(data(b,p['image'],'result',True)==[0],'Native AES call/layout failed')
            require(report['failures']==0 and report['progress']==32 and report.get('state_failures',0)==0 and report.get('input_failures',0)==0,'AES target assertion: '+str(report['failure_at']))
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'AES stack floor')
            clean_ownership(b,p,p['output'])
        report.update(status='pass',pin=pin,xex_sha256=sha256(p['xex']),
            build_sha256=sha256(out/'program/build.json'),c_image_sha256=sha256(out/'c-image.json'),
            compiler=p['build']['revision'],extraction=f['provenance']['aes_extraction'],
            layouts=f['provenance']['checked_layout'],bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AES',mode,'passed',report['checks'],'checks',flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true')
    p.add_argument('--state',action='store_true');p.add_argument('--input',action='store_true')
    a=p.parse_args();run(a.output,a.mode,a.replay,a.state,a.input)
