#!/usr/bin/env python3
"""Execute current message/port qualification slices on the pinned platform."""
from library_paths import module_args, read_source
import argparse
import json
from pathlib import Path
import re

from native_program import ROOT,build,command,compiler,execute,platform_files,require,sha256,verify_machine
from os_boundary import emulator
from test_banked import PIN,changed_image
from test_cooperative import data
from banked_test_memory import read as far_read
from generate_ports import ABI,check_routine,generate


def imports(toolchain,output):
    from generate_tasks import policy_modules,generate_kernel
    from generate_memory import layout,generate as memory_generate
    from generate_heap import reserve_metadata,registration_include,install_policy
    memory=layout();reserve_metadata(memory)
    from generate_ports import reserve_metadata as reserve_ports
    reserve_ports(memory)
    memory_generate(output,memory);registration_include(output,memory);install_policy(output)
    (output/'execmemory.act').write_text(read_source(ROOT/'lib/exec/execmemory.act'))
    generate_kernel(output,memory=memory);directory=policy_modules(output,memory=memory)
    interfaces=json.loads(command([toolchain['binary'],'--module-path',directory,'--module-path',output,
        *module_args(),'--emit-interfaces',ROOT/'tests/programs/ports_imports.act']))
    chosen={i['name'].split('.')[1]:i for i in interfaces if i['name'].startswith('EXEC.')}
    require(set(chosen)==set(ABI['imports']),'Missing port declarations')
    for name,interface in chosen.items():check_routine(interface,name)
    return chosen


def abi_case(bridge,toolchain,output,optimize):
    generate(output);generate(output,True)
    for source in ('tests/programs/ports_abi.act','lib/exec/exec-task-types.inc'):
        (output/Path(source).name).write_text((ROOT/source).read_text())
    program=build(toolchain,output/'ports_abi.act',output,optimize=optimize,banked=True)
    ranges=[(0x4fff0,64),(0x6fff0,48)]
    for a,n in ranges:program['image']['segments'].append(dict(address=a,bytes=[0xa5]*n,writable=True,executable=False))
    changed_image(program)
    for name in ABI['imports']:
        routine=next(r for r in program['image']['routines'] if re.fullmatch('M_PORTABI_'+name.upper()+'_[0-9A-F]+',r['name']))
        check_routine(routine,name)
    runtime,_=execute(bridge,program,timeout=120,frame_limit=2400)
    def longs(name):
        b=bytes(data(bridge,program['image'],name))
        return [int.from_bytes(b[i:i+4],'little') for i in range(0,len(b),4)]
    facts=longs('facts');seen=longs('seen')
    require(facts==[27,16,11,12,13,16,11,14,0xab1234,0xfeffff,0x71234,0xffffff,0x4fff3,65535,0x80000000],f'Port layouts/results: {facts}')
    require(seen==[0x11234,0x71234,0x11234,0xfeffff,0xabffff,0x71234,0x11234,0x71234,0x5ffff],f'Port arguments: {seen}')
    expected={a+i:0xa5 for a,n in ranges for i in range(n)}
    for a,value,n in [(0x4fff9,4,1),(0x4fffe,0,1),(0x4ffff,31,1),(0x50000,0xab1234,3),
                      (0x50003,0xcd1234,3),(0x6fffa,7,1),(0x6ffff,0x4fff3,3),(0x70002,65535,2)]:
        expected.update((a+i,b) for i,b in enumerate(value.to_bytes(n,'little')))
    for a,n in ranges:require(far_read(bridge,a,n,output)==bytes(expected[a+i] for i in range(n)),'Port field/guard mismatch')
    require(data(bridge,program['image'],'writeStatus',True)==[1],'OS console call failed')
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(bridge.memdump(c['TABLE'],len(seed))==seed,'ABI probe altered bank ownership')
    return dict(build=program['build'],runtime=runtime,facts=facts,seen=seen)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'build/ports-tests')
    parser.add_argument('--suite',choices=('abi','queues','queue-faults','queue-races','queue-context','queue-crossing','queue-handoff','wait','wait-gap','wait-faults','wait-masked','wait-publication','lifetime','example','delete-faults','lifetime-masked','registry','registry-races','registry-peer','capacity','wait-removal'),default='abi')
    parser.add_argument('--case',action='append')
    parser.add_argument('--profile',choices=('1x','8x'),default='1x',help='Pinned functional profile; 8x also exercises the serial timing CPU profile')
    args=parser.parse_args()
    args.pin=json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text()) if args.profile=='8x' else PIN
    if args.suite!='abi':
        from test_ports_services import run
        return run(args)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[('abi-raw',False),('abi-opt',True)]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown port case')
    inputs=('abi/ports.json','lib/exec/exec-port-types.inc','lib/exec/port-call-types.inc','tools/generate_ports.py',
            'tools/generate_tasks.py','tools/test_ports.py','tests/programs/ports_abi.act','tests/programs/ports_imports.act')
    report=dict(schema_version=1,status='running',scope='Port native ABI only; no public services bound',platform=args.pin,
                inputs={p:sha256(ROOT/p) for p in inputs},interfaces=imports(toolchain,output),cases=[])
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=args.pin) as bridge:
            report['machine']=verify_machine(bridge,args.rom,args.pin)
            for name,optimize in cases:
                print('Running '+name+'...',flush=True)
                report['cases'].append(dict(name=name,status='pass',**abi_case(bridge,toolchain,output/name,optimize)))
        report['status']='pass'
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} port cases',flush=True)


if __name__=='__main__':main()
