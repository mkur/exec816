#!/usr/bin/env python3
"""Small emitted raw/optimized access probe for native desktop records."""
import argparse,json
from pathlib import Path
from generate_desktop import ABI,layout
from native_program import ROOT,build,compiler,execute,require,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_signals_irq import PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    checks=[]
    for name,fields in ABI['records'].items():
        checks += [f'  LET r{name}=DESKTYPES.{name} POINTER(memory)',
                   f'  Require(SIZEOF(DESKTYPES.{name})={layout()[name]["size"]})']
        for field,kind,*counts in fields:
            access=field+'(0)' if counts else field
            checks += [f'  Require(ADDRESS(@r{name}.{access})-ADDRESS(memory)={layout()[name]["fields"][field]})']
    source=out/'layout.act'
    source.write_text('''MODULE DESKTOPLAYOUT
USE EXEC
USE HEAPCORE
USE DESKTYPES
CARD checks
PROC Require(BYTE okay)
  IF okay=0 THEN
    HEAPCORE.Abort($f900+checks)
  FI
  checks==+1
RETURN
PROC Main()
  LET memory=EXEC.AllocMem(LONGCARD(DESKTYPES.SERVICE_SIZE),EXEC.MEMF_CLEAR)
  Require(memory<>NULL)
'''+ '\n'.join(checks)+'''
  rService.windows(0).normalBounds.left=104
  rService.windows(0).iconified=1
  rService.windows(1).normalBounds.left=192
  rService.windows(1).iconified=0
  Require(rService.windows(0).normalBounds.left=104)
  Require(rService.windows(0).iconified=1)
  Require(rService.windows(1).normalBounds.left=192)
  Require(rService.windows(1).iconified=0)
  EXEC.FreeMem(memory,LONGCARD(DESKTYPES.SERVICE_SIZE))
RETURN
ENDMODULE
''')
    result=dict(tier='development',qualification=False,cases=[])
    for mode in ('raw','opt'):
        p=build(compiler(ROOT/'build/actionc',release=True),source,out/mode,tasks=True,optimize=mode=='opt')
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out/(mode+'-run'),pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            runtime,_=execute(b,p,timeout=120,frame_limit=3000)
            count=data(b,p['image'],'checks',True)[0]
            require(count==len(checks)-len(ABI['records'])+5,'Missing layout/access checks')
            result['cases'].append(dict(mode=mode,checks=count,build=p['build'],runtime=runtime,machine=machine))
    result['status']='pass'
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Native desktop layout/access passed raw and optimized',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
