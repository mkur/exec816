#!/usr/bin/env python3
"""Qualify the classic Task layout/call shapes without enabling its gateway."""
from library_paths import module_args
import argparse
import json
from pathlib import Path
import re

from native_program import ROOT, build, command, compiler, execute, platform_files, require, sha256, verify_machine
from generate_tasks import ABI, SIGNALS, check_routine, declarations, generate, public_api
from os_boundary import emulator
from test_banked import PIN, changed_image
from test_cooperative import data
from banked_test_memory import read as far_read


CORE_CALLS = ('AddTask', 'RemTask', 'FindTask', 'SetTaskPri', 'Forbid', 'Permit', 'CreateTask')


def imports(toolchain, output):
    source = output/'imports.act'
    source.write_text('MODULE TASKIMPORTS\nUSE EXECLISTS\n'+public_api()+'''
Task prepared
Task POINTER result
BYTE old
PROC POINTER missing()
'''+declarations()+'''
PROC Entry()
RETURN
PROC Main()
  Forbid()
  result=CreateTask(c"abi",-128,@Entry,1536)
  result=AddTask(@prepared,@Entry,missing)
  result=FindTask(BYTE POINTER(0))
  old=SetTaskPri(result,$80)
  RemTask(result)
  Permit()
RETURN
ENDMODULE
''')
    interfaces = json.loads(command([toolchain['binary'], *module_args(),
                                    '--emit-interfaces', source]))
    require({i['name'].split('.')[1] for i in interfaces} == set(CORE_CALLS), 'Missing task imports')
    for interface in interfaces:
        check_routine(interface, interface['name'].split('.')[1])
    return interfaces


def case(bridge, toolchain, output, optimize):
    generate(output)
    source = output/'tasks_abi.act'
    source.write_text((ROOT/'tests/programs/tasks_abi.act').read_text())
    program = build(toolchain, source, output, optimize=optimize, banked=True)
    base, size = 0x04ffe0, 96
    program['image']['segments'].append({'address':base, 'bytes':[0xa5]*size,
                                         'writable':True, 'executable':False})
    changed_image(program)
    routines = {}
    for name in (*CORE_CALLS, 'Entry', 'Finalizer'):
        matches = [r for r in program['image']['routines']
                   if re.fullmatch('M_TASKABI_'+name.upper()+'_[0-9A-F]+', r['name'])]
        require(len(matches) == 1, 'Missing emitted Task routine '+name)
        routines[name] = matches[0]
        if name in ABI['imports']:
            check_routine(matches[0], name)
    result, _ = execute(bridge, program, frame_limit=1200, timeout=60)
    raw = bytes(data(bridge, program['image'], 'facts'))
    facts = [int.from_bytes(raw[i:i+3], 'little') for i in range(0,len(raw),3)]
    expected = [62,0,11,12,13,14,32,36,40,43,54,routines['Entry']['address'],
                routines['Finalizer']['address'],0x04ffef,0x05ffff,6,0,0]
    require(facts == expected, f'Task ABI facts: {facts}; expected {expected}')
    require(data(bridge,program['image'],'creation',True) == [0xff80,0xffff,0x5678,0x1234], 'CreateTask wide packet changed')
    require(data(bridge,program['image'],'created') == [1], 'CreateTask call/result changed')
    require(data(bridge,program['image'],'previous') == [255]+list(range(255)), 'Priority BYTE result changed')
    require(data(bridge,program['image'],'nesting') == [0], 'Void calls changed')
    observed = far_read(bridge,base,size,output)
    want = bytearray([0xa5]*size)
    start = 0x04ffef-base
    def put(offset, value, width=3):
        want[start+offset:start+offset+width] = value.to_bytes(width,'little')
    for offset,value in [(6,1),(7,255),(11,0),(12,6),(13,255),(14,255),(52,0),(53,0)]:
        put(offset,value,1)
    for offset,value in [(8,0x05ffff),(32,0x57fe),(36,0x5200),(40,0x5800),
                         (43,0x04ffef+46),(46,0),(49,0x04ffef+43),(54,0xbc4567)]:
        put(offset,value)
    require(observed == want, 'Task fields/guards changed: '+observed.hex())
    return {'build':program['build'], 'runtime':result, 'facts':facts, 'routines':routines,
            'guarded_task_bytes':observed.hex()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, required=True)
    parser.add_argument('--bridge-dir', type=Path, required=True)
    parser.add_argument('--rom', type=Path, default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output', type=Path, default=ROOT/'build/tasks-abi-tests')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir,args.rom)
    report = {'schema_version':1, 'status':'running', 'scope':'Task core layout and native call shapes only; no task gateway',
              'platform':PIN, 'interfaces':imports(toolchain,output), 'cases':[],
              'inputs':{name:sha256(ROOT/name) for name in ('abi/tasks.json','lib/exec/exec-task-types.inc',
                  'tools/generate_tasks.py','tools/test_tasks_abi.py','tests/programs/tasks_abi.act')}}
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config'] = verify_machine(bridge,args.rom,PIN)
            for optimize in (False,True):
                name = 'abi-opt' if optimize else 'abi-raw'
                print('Running '+name+'...',flush=True)
                report['cases'].append({'name':name,'status':'pass',**case(bridge,toolchain,output/name,optimize)})
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed raw and optimized Task ABI probes')


if __name__ == '__main__':
    main()
