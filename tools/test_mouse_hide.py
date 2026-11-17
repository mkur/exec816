#!/usr/bin/env python3
"""Small optimized emitted draw_Mouse hide, form-apply and late-target cases."""
import argparse,json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from test_screen_copy import function


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'ports/gem4xe/adapter/gem-vbxe.c'
    body=out/'mouse-hide-body.inc'
    body.write_text(function(source.read_text(),'static UWORD draw_Mouse('))
    foreign=emit(out/'c',[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/mouse_hide.c'],
        [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],[],
        includes=[out,ROOT/'c/calypsi',ROOT/'ports/gem4xe/adapter'],
        roots=['HideRun','checks','failures','firstFailure'])
    launcher=out/'mouse-hide.act'
    launcher.write_text(f'''MODULE MOUSEHIDETEST
USE HEAPCORE
USE CALYPSICALL
PROC Main()

  IF CALYPSICALL.Invoke(ADDRESS(${foreign['symbols']['HideRun']:x}),0)<>0 THEN
    HEAPCORE.Abort($fc91)
  FI

RETURN
ENDMODULE
''')
    p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',
        tasks=True,optimize=True,foreign_image=foreign)
    with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        number=lambda name:bridge.eval_expr(f'dw(${foreign["symbols"][name]:x})')
        try:
            runtime,_=execute(bridge,p,timeout=90,frame_limit=900)
        except Exception:
            print('Mouse hide checks/failures/first:',number('checks'),number('failures'),
                  number('firstFailure'),flush=True)
            raise
        checks,failures=number('checks'),number('failures')
        require(checks==25 and failures==0,'Mouse hide assertions: '+str((checks,failures)))
        ownership(bridge,p,p['output'])
    report=dict(status='pass',tier='development',qualification=False,checks=checks,
        failures=failures,machine=machine,runtime=runtime,build=p['build'],
        production_source_sha256=sha256(source),extracted_body_sha256=sha256(body),
        scope='Production draw_Mouse with only flush/cursor hardware substituted; actual Exec guards. Direct hide, form installation while already hidden, subsequent show, late revision, busy and fault cases. MGVIEW supplies real hardware/pixels.')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Mouse hide checks passed:',checks,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
