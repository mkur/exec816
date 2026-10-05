#!/usr/bin/env python3
"""Emitted shell PATH policy with controlled directory and loader failures."""
import argparse
import json
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256
from os_boundary import emulator
from test_cooperative import data

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    for source,target in [('command_path.act','probe.act'),('command_path_dos.act','dos.act'),
                          ('command_path_state.act','pathstate.act')]:
        (out/target).write_text(read_source(ROOT/'tests/programs'/source))
    (out/'process.act').write_text('MODULE PROCESS\nPUBLIC CONST RETURN_OK=0,RETURN_ERROR=10,RETURN_FAIL=20\nENDMODULE\n')
    (out/'programimage.act').write_text('MODULE PROGRAMIMAGE\nPUBLIC TYPE Image=[BYTE unused]\nENDMODULE\n')
    (out/'programfile.act').write_text('''MODULE PROGRAMFILE
USE PATHSTATE AS T
USE PROGRAMIMAGE
USE CSTRING.IMPL AS STR

PUBLIC PROGRAMIMAGE.Image POINTER FUNC Load(BYTE POINTER path)

  T.attempts==+1
  STR.strlcat(T.calls,CSTRING(path),SIZEOF(T.calls))
  STR.strlcat(T.calls,c"\\n",SIZEOF(T.calls))
  IF T.attempts=T.breakAfter THEN
    T.breakFlag=1
  FI

  IF T.attempts=1 AND T.firstError<>0 THEN
    T.error=T.firstError
    RETURN(NULL)
  FI

  IF STR.strcmp(CSTRING(path),T.success)=0 THEN
    T.error=0
    RETURN(PROGRAMIMAGE.Image POINTER($d0000))
  FI

  T.error=T.otherError

RETURN(NULL)

ENDMODULE
''')
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    (out/'profile.json').write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc'),out/'probe.act',out,optimize=mode=='opt',banked=True,
            console=False,memory_profile=out/'profile.json',image_data=[(0x200000,bytes(1152)),(0x210000,bytes(1152))])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:
            print('PATH check:',data(b,p['image'],'checks',True),flush=True)
            raise
        require(data(b,p['image'],'finished')==[1],'PATH checks incomplete')
        checks=data(b,p['image'],'checks',True)[0]
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],
                runtime=runtime,machine=machine,runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();result=run(out,args.case)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PATH policy passed:',args.case,result['checks'],flush=True)
