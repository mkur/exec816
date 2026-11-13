#!/usr/bin/env python3
"""Small emitted Terminal signal ownership/rollback probe; console/AES are stubs."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from terminal_model import LAYOUT


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/gem_terminal_wake.c',ROOT/'examples/gem-terminal/platform.c',ROOT/'c/calypsi/exec.c']
    foreign=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),mode=='opt',
        roots=['TerminalWakeProbe','TerminalWakeChecks'],probes=[(ROOT/'tests/programs/gem_terminal_layout.c',LAYOUT)])
    source=out/'probe.act'
    source.write_text('''MODULE TERMINALWAKE
USE CALYPSICALL
LONGINT result

PROC Main()

  result=CALYPSICALL.Invoke(ADDRESS($%x),0)

RETURN
ENDMODULE
''' % foreign['symbols']['TerminalWakeProbe'])
    program=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',
        tasks=True,task_capacity=8,optimize=mode=='opt',foreign_image=foreign)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN)
        try:runtime,_=execute(b,program,frame_limit=600,timeout=120)
        except Exception:
            print('Terminal checks before fault:',int.from_bytes(b.memdump(
                foreign['symbols']['TerminalWakeChecks'],2),'little'),flush=True)
            raise
        ownership(b,program,program['output'])
        result=int.from_bytes(bytes(data(b,program['image'],'result',False)),'little')
        checks=int.from_bytes(b.memdump(foreign['symbols']['TerminalWakeChecks'],2),'little')
        require(result==0,'Terminal signal check failed: '+str(result))
        require(checks>=30,'Incomplete Terminal signal cases')
    record=dict(status='pass',tier='development',qualification=False,mode=mode,checks=checks,
        scope=__doc__,runtime=runtime,machine=machine,build=program['build'],
        inputs={str(p.relative_to(ROOT)):sha256(p) for p in [*sources,ROOT/'examples/gem-terminal/terminal.h',
            ROOT/'tests/programs/gem_terminal_layout.c',ROOT/'tools/terminal_model.py',Path(__file__)]},
        checked_layout=foreign['provenance']['checked_layout'])
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Terminal signal probe passed:',mode,checks,'checks',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    args=parser.parse_args();run(args.output.resolve(),args.mode)
