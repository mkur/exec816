#!/usr/bin/env python3
"""Emitted production cursor completion against controlled backend outcomes."""
import argparse,json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from stack_budget import stack_usage
from test_screen_copy import function


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'c/calypsi/aes-input.c'
    body=function(source.read_text(),'LONG EXEC_CALL ExecAESMouseApply(')
    extracted=out/'apply.c'
    extracted.write_text('#include "aes-private.h"\n#include "vdi-private.h"\n#include <proto/exec.h>\n#include "gem-drawing.h"\n'+body)
    foreign=emit(out/'c',[ROOT/'c/calypsi/exec.c',extracted,ROOT/'tests/programs/cursor_completion.c'],
        [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],['CompletionWorker'],
        includes=[ROOT/'c/calypsi',ROOT/'ports/gem4xe/adapter'],roots=['CompletionRun'])
    path=out/'launcher.act'
    path.write_text(f'''MODULE CURSORCOMPLETION
USE EXEC
USE HEAPCORE
USE CALYPSICALL
PROC Main()

  IF CALYPSICALL.Invoke(ADDRESS(${foreign['symbols']['CompletionRun']:x}),0)<>0 THEN
    HEAPCORE.Abort($fc90)
  FI

RETURN
ENDMODULE
''')
    p=build(compiler(ROOT/'build/actionc',release=True),path,out/'program',
        tasks=True,optimize=True,foreign_image=foreign)
    report=dict(status='running',tier='development',qualification=False,build=p['build'],pin=PIN,
        production_source_sha256=sha256(source),completion_body_sha256=sha256(extracted),
        scope='Seven C completion cases; only backend borrow is substituted.')
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            report['runtime'],_=execute(b,p,timeout=120,frame_limit=1800)
            for name in ('checks','failures','progress'):
                report[name]=b.eval_expr(f'dw(${foreign["symbols"][name]:x})')
            require(report['failures']==0 and report['checks']>=32,'Cursor completion assertions')
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            ownership(b,p,p['output'])
        report['status']='pass'
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Cursor completion passed:',report['checks'],'checks')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.output.resolve())
