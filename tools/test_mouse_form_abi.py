#!/usr/bin/env python3
"""Small raw/optimized MFORM field and word access, with public VDI layouts."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from generate_vdi_client import expected_layout
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,mode):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/gem_mouse_form_abi.c'
    foreign=emit(out/'c',[source],[ROOT/'c/calypsi/image-info.s'],(),mode=='opt',
        includes=[ROOT/'c/calypsi'],roots=['FormProbe','FormChecks'],
        probes=[(ROOT/'c/calypsi/vdi-layout.c',expected_layout())])
    launcher=out/'probe.act'
    launcher.write_text('MODULE MFORMPROBE\nUSE CALYPSICALL\nLONGINT result\n'
        'PROC Main()\n  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'
        %foreign['symbols']['FormProbe'])
    program=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',
        tasks=True,task_capacity=8,foreign_image=foreign,optimize=mode=='opt',console=False)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as bridge:
        machine=verify_machine(bridge,rom,pin)
        runtime,_=execute(bridge,program,timeout=60,frame_limit=600,timer_irq=True)
        require(data(bridge,program['image'],'result',True)==[0,0],'MFORM assertion failed')
        checks=bridge.peek16(foreign['symbols']['FormChecks'])
        require(checks==68,'Incomplete MFORM field/word checks')
        ownership(bridge,program,program['output'])
    record=dict(status='pass',tier='development',qualification=False,mode=mode,
        checks=checks,machine=machine,runtime=runtime,source_sha256=sha256(source))
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('MFORM field/word checks passed:',checks)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    args=parser.parse_args();run(args.output,args.mode)
