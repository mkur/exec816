#!/usr/bin/env python3
"""WB2: emitted logical editing and physical GEM interaction checks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data


def logical(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/basic_editor.c',ROOT/'examples/gem-basic/document.c',
             ROOT/'examples/gem-basic/editor.c',ROOT/'c/calypsi/exec.c']
    if not reuse:
        f=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),True,
            roots=['BasicEditorProbe','BasicEditorChecks'])
        (out/'c-image.json').write_text(json.dumps(f,indent=2)+'\n')
        source=out/'probe.act'
        source.write_text('MODULE BASICEDITOR\nUSE CALYPSICALL\nLONGINT result\nPROC Main()\n'
            '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'%f['symbols']['BasicEditorProbe'])
        p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
            task_capacity=8,foreign_image=f,optimize=True,console=False,stack_checks=True)
    else:p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text())
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',tier='development',qualification=False,slice='WB2',case='logical keys',
        source_inputs={str(q.relative_to(ROOT)):sha256(q) for q in sources},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
            report['machine']=verify_machine(b,rom,pin)
            runtime,_=execute(b,p,timeout=180,frame_limit=9000,timer_irq=True)
            observed=data(b,p['image'],'result',True)
            require(observed==[0,0],'Editor assertion line: '+str(observed))
            ownership(b,p,p['output'])
            report.update(status='pass',runtime=runtime,checks=b.peek16(f['symbols']['BasicEditorChecks']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true');a=p.parse_args();logical(a.output.resolve(),a.from_build)
