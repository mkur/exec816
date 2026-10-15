#!/usr/bin/env python3
"""Small raw/optimized C/Action UPDATE bridge ABI and preemption probe."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(out, optimize):
    out.mkdir(parents=True, exist_ok=True)
    c = out/'probe.c'
    c.write_text('''#include <exec/types.h>
extern void AESBridgeProbe(void);
UWORD AESBridgeResults[24];
int main(void) { AESBridgeProbe(); return 0; }
''')
    asm = ['''              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern _AESUpdateCall,AESBridgeResults,_Dp,_Vfp
              .section farcode,text
              .public AESBridgeProbe
AESBridgeProbe:
              lda dp:_Dp
              lda dp:_Vfp
''']
    for dp in range(8,16,2): asm += [f'              lda dp:{dp}\n              pha\n']
    for case in range(2):
        offset=case*24
        if case: asm += ['              sep #0x20\n              pha\n              rep #0x20\n']
        for dp in range(8,16,2): asm += [f'              lda ##{0x5a00+dp}\n              sta dp:{dp}\n']
        asm += [f'''              tsc
              sta long:AESBridgeResults+{offset+2}
              tdc
              sta long:AESBridgeResults+{offset+6}
              lda ##0xffc0
              ldx ##0xab12
              jsl _AESUpdateCall
              sta long:AESBridgeResults+{offset}
              php
              tsc
              inc a
              sta long:AESBridgeResults+{offset+4}
              tdc
              sta long:AESBridgeResults+{offset+8}
              sep #0x20
              pla
              sta long:AESBridgeResults+{offset+10}
              phb
              pla
              sta long:AESBridgeResults+{offset+11}
              rep #0x20
''']
        for i,dp in enumerate(range(8,16,2)):
            asm += [f'              lda dp:{dp}\n              sta long:AESBridgeResults+{offset+12+i*2}\n']
        if case: asm += ['              sep #0x20\n              pla\n              rep #0x20\n']
    for dp in reversed(range(8,16,2)): asm += [f'              pla\n              sta dp:{dp}\n']
    asm += ['              rtl\n']
    assembly=out/'probe.s';assembly.write_text(''.join(asm))
    foreign=emit(out/'c',[c,ROOT/'c/calypsi/aes-update.c'],
                 [assembly,ROOT/'c/calypsi/aes-update.s',ROOT/'c/calypsi/image-info.s'],
                 (),optimize,roots=['ExecAESUpdateEntry','AESBridgeResults'])
    sy=foreign['symbols']
    source=out/'probe.act'
    source.write_text('''MODULE AESBRIDGEPROBE
USE EXEC
USE CALYPSICALL
USE HEAPCORE
INCLUDE "%s"
VOLATILE CARD ticks=E816_VBI_COUNT
CARD calls
LONGCARD observed
LONGINT result

CARD FUNC Update(LONGCARD value)

  observed=value
  IF value<>$ab12ffc0 THEN
    HEAPCORE.Abort($fcba)
  FI
  calls==+1
  LET start=ticks
  WHILE ticks-start<2 DO
  OD
  EXEC.Yield()

RETURN($5a39)

PROC Main()

  LET entry=ADDRESS POINTER($%x)
  entry^=ADDRESS(@Update)
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)

RETURN
ENDMODULE
''' % (ROOT/'lib/exec/exec-abi.inc',sy['ExecAESUpdateEntry'],sy['main']))
    program=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',
                  tasks=True,task_capacity=8,optimize=optimize,foreign_image=foreign)
    with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
        machine=verify_machine(bridge,ROM,PIN)
        runtime,_=execute(bridge,program,timeout=120,frame_limit=600)
        ownership(bridge,program,program['output'])
        require(data(bridge,program['image'],'calls',True)==[2],'Both ABI calls required')
        raw=bridge.memdump(sy['AESBridgeResults'],48)
        words=[int.from_bytes(raw[i:i+2],'little') for i in range(0,48,2)]
        for offset in (0,12):
            row=words[offset:offset+12]
            require(row[0]==0x5a39,'Native result lost')
            require(row[1]==row[2] and row[3]==row[4],'Stack or DP changed')
            require(row[5]&0xff30==0,'DBR or native register width changed')
            require(row[6:10]==list(range(0x5a08,0x5a10,2)),'C preserved DP changed')
        require((words[1]^words[13])&1,'Both C stack parities required')
        require(runtime['native_nmi_count']>=4,'Preemption missing')
    (out/'results.json').write_text(json.dumps(dict(status='pass',tier='development',
        optimize=optimize,words=words,runtime=runtime,machine=machine,
        build=program['build']),indent=2)+'\n')
    print('UPDATE bridge passed:', 'opt' if optimize else 'raw',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    for optimize in (False,True):run(args.output.resolve()/('opt' if optimize else 'raw'),optimize)
