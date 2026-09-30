#!/usr/bin/env python3
"""Qualify heap slices with emitted native code on the pinned hosted platform."""
from library_paths import module_args, read_source
import argparse
import json
from pathlib import Path
import re

from native_program import (ROOT, build, command, compiler, execute, platform_files,
                            require, sha256, verify_machine)
from os_boundary import emulator
from test_banked import PIN, changed_image
from test_cooperative import data
from banked_test_memory import read as far_read
from generate_heap import ABI, check_compiler, check_routine, generate, public_api


def import_shapes(toolchain, output):
    output=output.resolve()
    from generate_tasks import policy_modules, generate_kernel
    from generate_memory import layout,generate as generate_memory
    from generate_heap import reserve_metadata,registration_include,install_policy
    memory=layout();reserve_metadata(memory)
    from generate_ports import reserve_metadata as reserve_ports
    reserve_ports(memory)
    generate_memory(output,memory);registration_include(output,memory)
    install_policy(output)
    (output/'execmemory.act').write_text(read_source(ROOT/'lib/exec/execmemory.act'))
    generate_kernel(output,memory=memory)
    directory = policy_modules(output,memory=memory)
    interfaces = json.loads(command([toolchain['binary'], '--module-path', directory,
                                    '--module-path', output,
                                    *module_args(), '--emit-interfaces', ROOT/'tests/programs/heap_imports.act']))
    selected = {i['name'].split('.')[1]:i for i in interfaces if i['name'].startswith('EXEC.')}
    require(set(selected) == set(ABI['imports']), 'Missing heap declarations')
    for name,interface in selected.items(): check_routine(interface,name)
    return selected


def abi_case(bridge, toolchain, output, optimize, count):
    generate(output,count);generate(output,count,check=True)
    (output/'heap_abi.act').write_text((ROOT/'tests/programs/heap_abi.act').read_text())
    program=build(toolchain,output/'heap_abi.act',output,optimize=optimize,banked=True)
    ranges=[(0x04ffd0,80),(0x060000,64)]
    for address,size in ranges:
        program['image']['segments'].append(dict(address=address,bytes=[0xa5]*size,writable=True,executable=False))
    changed_image(program)
    routines=[]
    for name in ABI['imports']:
        matches=[r for r in program['image']['routines'] if re.fullmatch('M_HEAPABI_'+name.upper()+'_[0-9A-F]+',r['name'])]
        require(len(matches)==1,'Missing emitted ABI routine '+name)
        check_routine(matches[0],name);routines+=matches
    result,screen=execute(bridge,program,frame_limit=1200,timeout=60)
    def longs(name):
        raw=bytes(data(bridge,program['image'],name))
        return [int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
    facts=longs('facts');seen=longs('seen')
    expected=[28,8,8,0,12,14,17,20,24,0,3,4,0xab1234,0xfefff8,0x80010001,0x80000011,
              0x6fff8,0x1000000,0x43210000,0x100000,0x10008,count]
    require(facts==expected,f'Heap ABI facts: {facts}, expected {expected}')
    require(seen==[0xfe123456,0x80010001,0xab1234,0xfe123456,0xffffffff,0x80100001,
                   0xcdffff,0x80120001,0xffffff,0x04ffeb,0x80010001,0x04ffeb,0xabffff,
                   0x80010001,0x87654321],f'Heap argument values: {seen}')
    require(data(bridge,program['image'],'writeStatus',True)==[1],'Heap probe console failed')
    expected_bytes={a+i:0xa5 for a,n in ranges for i in range(n)}
    def put(address,value,width): expected_bytes.update((address+i,b) for i,b in enumerate(value.to_bytes(width,'little')))
    for offset,value,width in [(6,10,1),(12,17,2),(14,0x60010,3),(17,0xff0000,3),(20,0x1000000,4),(24,0x43210000,4)]:
        put(0x04ffeb+offset,value,width)
    for address,value,width in [(0x60010,0xabfff8,3),(0x60013,0,1),(0x60014,0x100000,4),
                                (0x60020,0x12345678,4),(0x60024,0x87654321,4)]: put(address,value,width)
    for address,size in ranges:
        observed=far_read(bridge,address,size,output)
        require(observed==bytes(expected_bytes[address+i] for i in range(size)),f'Heap ABI fields/guards changed at {address:06x}')
    memory=program['build']['memory']['constants']
    seed=(output/'manifest.bin').read_bytes()[32:32+memory['TABLE_BYTES']]
    require(bridge.memdump(memory['TABLE'],len(seed))==seed,'ABI probe altered ownership')
    return dict(build=program['build'],runtime=result,facts=facts,seen=seen,routines=routines,
                heap_max_banks=count,limit_is_layout_only=True,bank255_arithmetic_only=True,
                heap_generated={p:sha256(output/p) for p in ('heap.inc','heap-action.inc','heap.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, required=True)
    parser.add_argument('--bridge-dir', type=Path, required=True)
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/heap-tests')
    parser.add_argument('--case', action='append')
    parser.add_argument('--suite', choices=('abi','core','registration','policy','api','concurrent'), default='abi')
    args = parser.parse_args()
    if args.suite == 'concurrent':
        from test_heap_concurrent import run
        return run(args)
    if args.suite == 'api':
        from test_heap_api import run
        return run(args)
    if args.suite == 'policy':
        from test_heap_policy import run
        return run(args)
    if args.suite == 'registration':
        from test_heap_registration import run
        return run(args)
    if args.suite == 'core':
        from test_heap_core import run
        return run(args)
    toolchain = compiler(args.compiler_dir)
    check_compiler(json.loads((toolchain['directory']/'docs/abi/action65816-native-v2.json').read_text()))
    require((ROOT/'lib/exec/exec-memory-types.inc').read_text().replace('\r\n','\n') == public_api(),
            'Stale public heap constants')
    platform_files(args.bridge_dir, args.rom)
    cases = [(f'abi-{count}-{mode}', count, mode == 'opt') for count in (1,16,256) for mode in ('raw','opt')]
    if args.case:
        cases = [case for case in cases if case[0] in args.case]
        require({case[0] for case in cases} == set(args.case), 'Unknown heap case')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    interfaces = import_shapes(toolchain,output)
    report = {'schema_version':1, 'status':'running', 'scope':'Classic Exec memory ABI: layouts and full-width native calls; no allocator service',
              'platform':PIN, 'interfaces':interfaces, 'cases':[],
              'inputs':{p:sha256(ROOT/p) for p in ('abi/heap-v1.json','lib/exec/exec-memory-types.inc','tools/generate_tasks.py',
                        'tools/generate_heap.py','tools/test_heap.py','tests/programs/heap_abi.act',
                        'tests/programs/heap_imports.act')}}
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config'] = verify_machine(bridge,args.rom,PIN)
            for name,count,optimize in cases:
                print('Running '+name+'...',flush=True)
                observed = abi_case(bridge,toolchain,output/name,optimize,count)
                report['cases'].append({'name':name,'status':'pass',**observed})
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} heap cases; report: {output}/results.json')


if __name__ == '__main__':
    main()
