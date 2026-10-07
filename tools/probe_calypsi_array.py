#!/usr/bin/env python3
"""Record a small external compiler defect in raw/optimized emitted code."""
import argparse,json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,sha256
from os_boundary import emulator
from test_dos_stack import execute
from test_mouse_observe import BRIDGE,ROM,PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    driver=out/'driver.c'
    driver.write_text('''short ArrayResult[4];
extern void ArrayExample(short,short);
void ArrayFill(short *p) { short i; for(i=0;i<4;++i) p[i]=100+i; }
void ArrayConsume(const short *p) { short i; for(i=0;i<4;++i) ArrayResult[i]=p[i]; }
unsigned short main(void) { ArrayExample(10,20); return 0; }
''')
    rows=[]
    for mode in ('raw','opt'):
        folder=out/mode;folder.mkdir(exist_ok=True)
        image=emit(folder,[ROOT/'tests/programs/calypsi_array_copy.c',driver],
                   [ROOT/'c/calypsi/image-info.s'],[],optimize=mode=='opt',roots=['main','ArrayResult'])
        source=folder/'probe.act';source.write_text(f'''MODULE ARRAYPROBE
CARD FUNC POINTER entry()
CARD result
PROC Main()

  LET target=ADDRESS POINTER(@entry)
  target^=${image['symbols']['main']:x}
  result=entry()

RETURN
ENDMODULE
''')
        p=build(compiler(ROOT/'build/actionc'),source,folder/'program',optimize=mode=='opt',
                tasks=True,task_capacity=8,foreign_image=image,stack_checks=True)
        with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
            runtime,_=execute(b,p,timeout=60,frame_limit=3000)
            raw=b.memdump(image['symbols']['ArrayResult'],8)
            actual=[int.from_bytes(raw[i:i+2],'little') for i in range(0,8,2)]
        rows.append(dict(mode=mode,expected=[18,68,145,91],actual=actual,correct=actual==[18,68,145,91],
                         runtime=runtime,tools=image['provenance']['tools'],xex_sha256=sha256(p['xex'])))
    record=dict(tier='development',scope='External Calypsi diagnostic, not an Exec qualification gate',
                source_sha256=sha256(ROOT/'tests/programs/calypsi_array_copy.c'),cases=rows)
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print([(row['mode'],row['actual']) for row in rows],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
