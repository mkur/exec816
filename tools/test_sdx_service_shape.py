#!/usr/bin/env python3
"""Small raw/optimized P4 record-layout and suspended-frame ABI check."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:
        program=build(compiler(ROOT/'build/actionc',release=True),
            ROOT/'tests/programs/sdx_service_shape.act',out,optimize=args.case=='opt',
            tasks=True,task_capacity=8,console=False,console_test=True,sdx=True)
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:
                runtime,_=execute(b,program,timeout=180,frame_limit=9000)
            except Exception:
                print('Checks:',data(b,program['image'],'checks'),flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
            size=int.from_bytes(bytes(data(b,program['image'],'sessionBytes')),'little')
        result=dict(status='pass',tier='development',mode=args.case,checks=checks,
                    session_bytes=size,runtime=runtime,machine=machine,build=program['build'])
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDX service shape:',checks,'checks passed',args.case,flush=True)


if __name__=='__main__':
    main()
