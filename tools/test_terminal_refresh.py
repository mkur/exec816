#!/usr/bin/env python3
"""Emitted Terminal refresh/retry state decisions with controlled endpoints and real Exec resources/signals."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from calypsi_build import emit
from os_boundary import emulator
from test_mouse_observe import BRIDGE,ROM,PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from terminal_model import LAYOUT


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    # Only controller lookup/enqueue are controlled. Ports, replies, heap and
    # signals remain the production bindings; the full GEM case covers RPC.
    bindings=out/'exec.c';text=(ROOT/'c/calypsi/exec.c').read_text()
    import re
    for name in ('FindPort','PutMsg'):
        text=re.sub(r'(?m)^[^\n]*EXEC_CALL '+name+r'\([\s\S]+?^}\n','',text,flags=re.M)
    bindings.write_text(text)
    sources=[ROOT/'tests/programs/gem_terminal_refresh.c',ROOT/'examples/gem-terminal/platform.c',bindings]
    roots=['TerminalRefreshServe','TerminalRefreshProbe','TerminalRefreshChecks',
        'TerminalQueries','TerminalDirectories','TerminalCopies','TerminalAdmissions']
    foreign=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),mode=='opt',
        roots=roots,includes=[ROOT/'c/calypsi'],probes=[(ROOT/'tests/programs/gem_terminal_layout.c',LAYOUT)])
    sy=foreign['symbols'];source=out/'probe.act'
    source.write_text('''MODULE TERMINALREFRESH
USE CALYPSICALL
LONGINT result

PROC Main()

  result=CALYPSICALL.Invoke(ADDRESS($%x),0)

RETURN
ENDMODULE
''' % sy['TerminalRefreshProbe'])
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,
        optimize=mode=='opt',foreign_image=foreign)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN)
        try:runtime,_=execute(b,p,timeout=120,frame_limit=1200)
        except Exception:
            print('Refresh checks before fault',int.from_bytes(b.memdump(sy['TerminalRefreshChecks'],2),'little'),flush=True)
            raise
        ownership(b,p,p['output'])
        result=int.from_bytes(bytes(data(b,p['image'],'result')),'little')
        counts={name:int.from_bytes(b.memdump(sy[name],2),'little') for name in roots[2:]}
        require(result==0,'Refresh check failed: '+str(result)+' '+str(counts))
        require(counts['TerminalRefreshChecks']>=40,'Incomplete refresh decisions')
    record=dict(status='pass',tier='development',qualification=False,mode=mode,counts=counts,
        runtime=runtime,machine=machine,build=p['build'],checked_layout=foreign['provenance']['checked_layout'],
        inputs={str(f.relative_to(ROOT)):sha256(f) for f in [*sources,ROOT/'examples/gem-terminal/terminal.h',Path(__file__)]})
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Terminal refresh checks passed:',mode,counts,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');args=a.parse_args();run(args.output.resolve(),args.mode)
