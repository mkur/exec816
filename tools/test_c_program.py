#!/usr/bin/env python3
"""Development proof of two bank-relocated C images and the native/C bridge."""
import argparse,json
from pathlib import Path
from build_c_program import build as application
from calypsi_build import emit
from native_program import ROOT,build,compiler,require,verify_machine,read_build,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from stack_budget import bank_zero_delta,stack_usage

def run(out,optimize,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        p=read_build(out/'program')
        app=json.loads((out/'app/app.json').read_text())
        require(p['build']['optimize']==optimize,'Wrong reused compiler mode')
        return exercise(out,p,app,optimize)
    app=application(out/'app',[ROOT/'tests/programs/c_program.c'],optimize)
    foreign=emit(out/'provider',[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/c_program.c'],
        [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),optimize,roots=['ExecYield'])
    binding=(ROOT/'lib/dos/cprogrambind.act').read_text().replace('RETURN(ADDRESS(0))',
        'RETURN(ADDRESS($%x))'%foreign['symbols']['ExecYield'],1)
    (out/'cprogrambind.act').write_text(binding)
    payload=(out/'app/program.app').read_bytes()
    include=out/'app.inc'
    include.write_text('CONST WIRE_BYTES='+str(len(payload))+'\nBYTE ARRAY wire=['+' '.join(str(b) for b in payload)+']\n')
    text=(ROOT/'tests/programs/c_program.act').read_text().replace('"app.inc"','"'+str(include)+'"')
    launcher=out/'launcher.act';launcher.write_text(text)
    from generate_memory import PROFILE
    memory=json.loads(PROFILE.read_text());memory['image_data_bytes']=8192
    memory_path=out/'fixture-memory.json';memory_path.write_text(json.dumps(memory,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc'),launcher,out/'program',tasks=True,task_capacity=4,
            foreign_image=foreign,optimize=optimize,memory_profile=memory_path)
    return exercise(out,p,app,optimize)

def exercise(out,p,app,optimize):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    require(sha256(ROOT/'build/shell-paced-bridge/AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned emulator')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        runtime,_=execute(b,p,frame_limit=6000,timeout=180,timer_irq=True)
        require(runtime['native_nmi_count']>0 and runtime['native_irq_count']>0,
                'Missing asynchronous native entries')
        require(data(b,p['image'],'completed',True)==[2],'Missing relocated C entries')
        ownership(b,p,p['output'])
        report=dict(status='pass',tier='development',optimized=optimize,build=p['build'],
            machine=machine,runtime=runtime,stack_usage=stack_usage(b,p['build']['memory']),
            bank_zero_delta=bank_zero_delta(p['build']['memory']),application=app)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),not args.raw,args.from_build)
