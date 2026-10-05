#!/usr/bin/env python3
"""PrintFault with real formatting/WriteAll and controlled transport failures."""
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
    (out/'probe.act').write_text(read_source(ROOT/'tests/programs/command_fault_io.act'))
    (out/'doscalls.act').write_text(read_source(ROOT/'tests/programs/command_fault_calls.act'))
    (out/'faultstate.act').write_text('''MODULE FAULTSTATE
PUBLIC BYTE mode
PUBLIC CARD used,writes
PUBLIC LONGINT error
PUBLIC BYTE ARRAY output(384)
ENDMODULE
''')
    (out/'dosclient.act').write_text('''MODULE DOSCLIENT
USE FAULTSTATE AS T
PUBLIC LONGINT FUNC IoErr()
RETURN(T.error)
PUBLIC PROC SetError(LONGINT cause)
  T.error=cause
RETURN
ENDMODULE
''')
    (out/'dosbreak.act').write_text('''MODULE DOSBREAK
USE FAULTSTATE AS T
PUBLIC LONGINT FUNC Pending()
RETURN(LONGINT(T.mode=4))
ENDMODULE
''')
    for module,routine in [('DOSRAW','ValidExtent'),('FSNAMES','Mapped')]:
        (out/(module.lower()+'.act')).write_text(f'''MODULE {module}
PUBLIC BYTE FUNC {routine}(BYTE POINTER buffer LONGINT length)
RETURN(buffer<>NULL AND ADDRESS(buffer)>=ADDRESS($10000) AND length>0)
ENDMODULE
''')
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    (out/'profile.json').write_text(json.dumps(profile))
    p=build(compiler(ROOT/'build/actionc'),out/'probe.act',out,optimize=mode=='opt',
            banked=True,console=False,memory_profile=out/'profile.json')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:
            print('PrintFault check:',data(b,p['image'],'checks',True),flush=True)
            raise
        require(data(b,p['image'],'finished')==[1],'PrintFault checks incomplete')
        checks=data(b,p['image'],'checks',True)[0]
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],
                runtime=runtime,machine=machine,runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();result=run(out,args.case)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PrintFault I/O passed:',args.case,result['checks'],flush=True)
