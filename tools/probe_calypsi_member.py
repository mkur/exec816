#!/usr/bin/env python3
"""Record member-address conversion and execute the typed-pointer form."""
import argparse,json,subprocess
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,sha256,require
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from test_cooperative import data

def run(out):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/calypsi_member_address.c'
    driver=out/'driver.c'
    driver.write_text('''#include <stddef.h>
'''+source.read_text().split('void MemberAddress(')[0]+'''
void MemberAddress(struct Fields *);
static struct Fields fields;
UWORD main(void)
{
    fields.object.x=123;fields.ted.text=0xabcdef01UL;fields.ted.colour=456;
    MemberAddress(&fields);
    return !(fields.object.spec==(ULONG)&fields+offsetof(struct Fields,ted) &&
             fields.object.x==123 && fields.ted.text==0xabcdef01UL && fields.ted.colour==456);
}
''')
    rows=[]
    for mode in ('raw','opt'):
        folder=out/mode;folder.mkdir(exist_ok=True)
        image=emit(folder,[source,driver],[ROOT/'c/calypsi/image-info.s'],[],
                   optimize=mode=='opt',roots=['main','MemberAddress'])
        target=folder/'probe.act';target.write_text(f'''MODULE MEMBERPROBE
CARD FUNC POINTER entry()
CARD result
PROC Main()

  LET call=ADDRESS POINTER(@entry)
  call^=${image['symbols']['main']:x}
  result=entry()

RETURN
ENDMODULE
''')
        p=build(compiler(ROOT/'build/actionc',release=True),target,folder/'program',
                optimize=mode=='opt',tasks=True,task_capacity=8,foreign_image=image)
        with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
            runtime,_=execute(b,p,frame_limit=1200)
            require(data(b,p['image'],'result',True)==[0],'Member conversion corrupted its address or neighbors')
            ownership(b,p,p['output'])
        cc=image['provenance']['tools']['cc65816']['path']
        direct=subprocess.run([cc,'--code-model=large','--data-model=huge',
            '-O2' if mode=='opt' else '-O0','-I',str(ROOT/'c/include'),
            '-DDIRECT_MEMBER_CAST=1','-c','-o',str(folder/'direct.o'),str(source)],
            capture_output=True,text=True)
        rows.append(dict(mode=mode,normalized='pass',direct_exit=direct.returncode,
            direct_diagnostic=direct.stderr.strip(),tools=image['provenance']['tools'],
            runtime=runtime,xex_sha256=sha256(p['xex'])))
    result=dict(status='pass',tier='development',qualification=False,
        scope='External Calypsi diagnostic; emitted typed-pointer conversion and unchanged neighbors',
        source_sha256=sha256(source),cases=rows)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Typed member address conversion passed raw/opt; direct form recorded',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
