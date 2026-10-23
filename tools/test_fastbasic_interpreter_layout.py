#!/usr/bin/env python3
"""Small emitted raw/optimized public C record and context probe."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership


def run(out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    foreign=emit(out/'c',[ROOT/'tests/programs/fastbasic_interpreter_probe.c'],
        [ROOT/'c/calypsi/image-info.s'],(),optimize,
        roots=['InterpreterProbe','InterpreterChecks','InterpreterSessionBlock'])
    message_base=foreign['symbols']['InterpreterSessionBlock']
    require(message_base%2==0 and (message_base+12)%2==0 and (message_base+32)%2==0,
        'Unaligned emitted session/request messages')
    source=out/'probe.act'
    source.write_text('MODULE INTERPRETERLAYOUT\nUSE CALYPSICALL\nLONGINT result\n'
        'PROC Main()\n  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\nRETURN\nENDMODULE\n'
        %foreign['symbols']['InterpreterProbe'])
    native=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',
        tasks=True,task_capacity=12,foreign_image=foreign,optimize=optimize,
        console=False,stack_checks=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as bridge:
        machine=verify_machine(bridge,rom,pin)
        runtime,_=execute(bridge,native,timeout=120,frame_limit=6000)
        actual=data(bridge,native['image'],'result',True)
        require(actual==[0,0],'C interpreter record probe: '+str(actual))
        ownership(bridge,native,native['output'])
        checks=bridge.peek16(foreign['symbols']['InterpreterChecks'])
    result=dict(status='pass',tier='development',qualification=False,
        optimize=optimize,checks=checks,message_addresses=[message_base+12,message_base+32],machine=machine,runtime=runtime,build=native['build'])
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    args=parser.parse_args()
    print(run(args.output.resolve(),not args.raw)['checks'])
