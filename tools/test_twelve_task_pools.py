#!/usr/bin/env python3
"""Three managed large stacks, twelve live Tasks, high-stack ROM entry and NMI."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_large_stacks import observe
from stack_budget import stack_usage


def bounds_check(program,out,pin):
    out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for phase in ('loader','native-entry'):
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out/phase,pin) as b:
            b.boot(str(program['xex']))
            if phase=='native-entry':
                run_to(b,program['labels']['loader_start'],1800,180)
                b.bp_clear_all()
            entry=program['labels']['loader_init' if phase=='loader' else 'start']
            b.bp_set(entry)
            run_to(b,entry,1800,90)
            memlo=b.peek16(0x2e7)
            vectors=b.memdump(0x256,9)
            b.memload(0xa00,bytes([0xa6])*256)
            b.memload(0x9000,bytes([0x69])*11264)
            b.poke16(0x2e5,0xbbff)
            b.bp_clear_all()
            stop=program['labels']['loader_return' if phase=='loader' else 'state_rejected']
            b.bp_set(stop)
            run_to(b,stop,60,5)
            if phase=='loader':
                require(b.peek(program['labels']['loader_error'])==b'\x01','Missing loader MEMTOP rejection')
            require(b.peek16(0x2e7)==memlo,'Rejected entry changed MEMLO')
            require(b.memdump(0xa00,256)==bytes([0xa6])*256,'Rejected entry claimed adapter state')
            require(b.memdump(0x9000,11264)==bytes([0x69])*11264,'Rejected entry initialized high pools')
            require(b.memdump(0x256,9)==vectors,'Rejected entry installed vectors')
            cases.append(dict(phase=phase,memlo=memlo,state_intact=True,high_ram_intact=True,vectors_intact=True))
    report=dict(status='pass',tier='development',injected_memtop=0xbbff,required_memtop=0xbc00,cases=cases)
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    program=build(compiler(ROOT/'build/actionc',release=True),
                  ROOT/'tests/programs/twelve_task_pools.act',out,
                  optimize=True,tasks=True,task_capacity=12)
    report=dict(status='running',tier='development',pin=pin,build=program['build'],
                runner_sha256=sha256(Path(__file__)))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin) as bridge:
            report['machine']=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',pin)
            at=lambda name:next(d['address'] for d in program['image']['data']
                                if '_'+name.upper()+'_' in d['name'])

            def before(b):
                report['preemption']=observe(b,program,[at('progress')+2*i for i in range(3)],
                                             slots=(6,7,11))
                b.poke(at('release'),1)

            report['runtime'],_=execute(bridge,program,before_run=before,
                                         frame_limit=6000,timeout=180)
            ownership(bridge,program,out)
            require(data(bridge,program['image'],'finished')==[11],'Missing managed Task retirement')
            require(data(bridge,program['image'],'outputStatus',True)==[1,1,1],'ROM write failed')
            report.update(status='pass',checks=data(bridge,program['image'],'checks',True),
                          stack_usage=stack_usage(bridge,program['build']['memory']))
        report['bounds']=bounds_check(program,out/'bounds',pin)
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bounds-from',type=Path,help='Only test admission with an existing native fixture')
    args=parser.parse_args()
    if args.bounds_from:
        pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        bounds_check(read_build(args.bounds_from),args.output.resolve(),pin)
    else:
        run(args.output.resolve())
    print('Twelve-pool probe passed')
