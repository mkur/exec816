#!/usr/bin/env python3
"""Qualify native I/O layouts and call shapes; reject any unfinished imports."""
from library_paths import module_args, read_source
import argparse
import json
from pathlib import Path
import re

from native_program import ROOT, build, command, compiler, execute, platform_files, require, sha256, verify_machine
from os_boundary import emulator
from test_banked import PIN, changed_image
from test_cooperative import data
from banked_test_memory import read as far_read
from generate_io import ABI, SIO, check_routine, generate, IMPLEMENTED
from ports_budget import current as production_budget


def interfaces(toolchain, output):
    from generate_tasks import policy_modules, generate_kernel
    from generate_memory import layout, generate as memory_generate
    from generate_heap import reserve_metadata, registration_include, install_policy
    from generate_ports import reserve_metadata as reserve_ports
    memory=layout();reserve_metadata(memory);reserve_ports(memory)
    memory_generate(output,memory);registration_include(output,memory);install_policy(output)
    (output/'execmemory.act').write_text(read_source(ROOT/'lib/exec/execmemory.act'))
    generate_kernel(output,memory=memory);directory=policy_modules(output,memory=memory)
    result=json.loads(command([toolchain['binary'],'--module-path',directory,'--module-path',output,
        *module_args(),'--emit-interfaces',ROOT/'tests/programs/io_imports.act']))
    chosen={i['name'].split('.')[1]:i for i in result if i['name'].startswith('EXEC.')}
    require(set(chosen)==set(ABI['imports']),'Missing I/O declarations in generated EXEC')
    for name,interface in chosen.items():check_routine(interface,name)
    return chosen


# Independent expected bytes, including all inherited Message/Node fields.
# Unmentioned bytes (record padding and adjacent guards) must remain $A5.
REQUEST=[(0,0x011234,3),(3,0x071234,3),(6,9,1),(7,255,1),(8,0xfeffff,3),
         (11,0xab1234,3),(14,65535,2),(16,0xcd1234,3),(19,0xef1234,3),
         (22,65535,2),(24,0xa5,1),(25,0xfe,1)]
STANDARD=[(0,0x071234,3),(3,0x011234,3),(6,5,1),(7,128,1),(8,0xabffff,3),
          (11,0xab0000,3),(14,42,2),(16,0x011234,3),(19,0x071234,3),
          (22,2,2),(24,1,1),(25,9,1),(26,0xffffffff,4),(30,0x80000000,4),
          (34,0xfeffff,3),(38,0xfedcba98,4)]
SERIAL=[(0,0x090000,3),(3,0x080000,3),(6,6,1),(7,127,1),(8,0xcdffff,3),
        (11,0xef0000,3),(14,52,2),(16,0xab1234,3),(19,0xcd1234,3),
        (22,9,2),(24,254,1),(25,255,1),(26,0x87654321,4),(30,0xffffffff,4),
        (34,0x080000,3),(38,0x80000000,4),(42,255,1),(43,129,1),(44,254,1),
        (45,2,1),(46,65535,2),(48,0xffffffff,4)]
FIXTURES=[(0x4fff3,26,REQUEST),(0x6ffe4,42,STANDARD),(0x8ffce,52,SERIAL)]
LAYOUTS=[26,0,16,19,22,24,25,42,0,16,19,22,24,25,26,30,34,38,
         52,0,16,19,22,24,25,26,30,34,38,42,43,44,45,46,48]
SEEN=[0x011234,0xffffffff,0x071234,0xfeffff,0x89abcdef,0x011234,0xffffffff,
      0x071234,0x011234,0x071234,0x4fff3,0,0x6ffe4,0xffffff,0xffffffff,0x80000000]


def abi_case(bridge,toolchain,output,optimize,public_interfaces):
    from generate_ports import generate as ports_generate
    generate(output);generate(output,True);ports_generate(output)
    for source in ('tests/programs/io_abi.act','lib/exec/exec-task-types.inc'):
        (output/Path(source).name).write_text((ROOT/source).read_text())
    program=build(toolchain,output/'io_abi.act',output,optimize=optimize,banked=True)
    for address,size,_ in FIXTURES:
        program['image']['segments'].append(dict(address=address-16,bytes=[0xa5]*(size+32),writable=True,executable=False))
    changed_image(program)
    routines={}
    for name in ABI['imports']:
        routine=next(r for r in program['image']['routines'] if re.fullmatch('M_IOABI_'+name.upper()+'_[0-9A-F]+',r['name']))
        check_routine(routine,name)
        routines[name]={k:routine[k] for k in ('name','address','size','arguments','outgoing_bytes',
                       'result_bytes','fixed_frame','local_stack_peak','calls')}
    public_symbols={i['symbol'] for i in public_interfaces.values()}
    require(not public_symbols.intersection(i['symbol'] for i in program['image']['imports']),
            'Test-only I/O callees were bound as production imports')
    runtime,_=execute(bridge,program,timeout=120,frame_limit=2400)
    def values(name,width=4,signed=False):
        raw=bytes(data(bridge,program['image'],name))
        return [int.from_bytes(raw[i:i+width],'little',signed=signed) for i in range(0,len(raw),width)]
    facts=values('facts');seen=values('seen');readback=values('readback')
    errors=values('errors',2,True);returns=values('returns')
    require(facts==LAYOUTS,f'I/O field offsets/strides: {facts}')
    require(seen==SEEN,f'I/O argument values: {seen}')
    require(readback==[value for _,_,fields in FIXTURES for _,value,_ in fields],f'I/O field readback: {readback}')
    require(errors==[-1,-2,9],f'I/O errors were not sign extended: {errors}')
    require(returns==[0xab1234,0x070000,0],f'I/O pointer result narrowed: {returns}')
    buffers={}
    for address,size,fields in FIXTURES:
        expected=bytearray([0xa5]*(size+32))
        for offset,value,width in fields:expected[16+offset:16+offset+width]=value.to_bytes(width,'little')
        actual=far_read(bridge,address-16,len(expected),output)
        require(actual==expected,f'I/O field/guard bytes differ at {address:x}')
        buffers[f'{address:06x}']=actual.hex()
    require(data(bridge,program['image'],'writeStatus',True)==[1],'OS console call failed')
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(bridge.memdump(c['TABLE'],len(seed))==seed,'ABI probe altered bank ownership')
    return dict(build=program['build'],runtime=runtime,routines=routines,facts=facts,seen=seen,
                readback=readback,errors=errors,returns=returns,guarded_buffers=buffers,
                generated={name:sha256(output/name) for name in ('io.inc','io-action.inc','ports-action.inc')})


def rejection_case(toolchain,output,name):
    output.mkdir(parents=True,exist_ok=True)
    calls={
        'CreateIORequest':'request=EXEC.CreateIORequest(EXEC.MsgPort POINTER($011234),LONGCARD($ffffffff))',
        'OpenDevice':'error=EXEC.OpenDevice(BYTE POINTER($011234),LONGCARD($ffffffff),request,LONGCARD($ffffffff))',
        'CheckIO':'request=EXEC.CheckIO(request)',
        'DoIO':'error=EXEC.DoIO(request)', 'WaitIO':'error=EXEC.WaitIO(request)'}
    call=calls.get(name,f'EXEC.{name}(request)')
    source=output/'unimplemented.act'
    source.write_text('MODULE UNIMPLEMENTED\nUSE EXEC\nEXEC.IORequest POINTER request\nINT error\nPROC Main()\n  '+call+'\nRETURN\n\nENDMODULE\n')
    try:build(toolchain,source,output,tasks=True)
    except ValueError as error:
        require(str(error)=='Unimplemented device I/O import: EXEC.'+name,f'Wrong rejection: {error}')
        require(not (output/'program.xex').exists(),'Unimplemented I/O published an executable')
        return dict(name=name,status='rejected',reason=str(error))
    raise RuntimeError('Production accepted an unimplemented I/O binding: '+name)


def validate_record(report):
    require(report['status']=='pass','Failed or incomplete I/O qualification')
    require(len(report['cases'])==2 and {c['name'] for c in report['cases']}=={'abi-raw','abi-opt'},
            'I/O ABI requires raw and optimized execution')
    for case in report['cases']:
        require(case['status']=='pass' and case['runtime']['guards']=='intact','I/O execution failed')
        require(case['errors']==[-1,-2,9] and case['returns']==[0xab1234,0x70000,0],
                'Incorrect signed or far-pointer result')
    rejected=report['production_rejections']
    expected=set(report.get('unimplemented',ABI['imports']))
    require(len(rejected)==len(expected) and {r['name'] for r in rejected}==expected
            and all(r['status']=='rejected' for r in rejected),'Production test-stub binding or missing rejection')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/io-abi')
    p.add_argument('--case',action='append',choices=('abi-raw','abi-opt'))
    a=p.parse_args();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    t=compiler(a.compiler_dir);platform_files(a.bridge_dir,a.rom)
    cases=[('abi-raw',False),('abi-opt',True)]
    if a.case:cases=[c for c in cases if c[0] in a.case]
    inputs=('abi/io.json','abi/sio.json','lib/exec/exec-io-types.inc','tools/generate_io.py',
            'tools/generate_tasks.py','tools/native_program.py','tools/test_io.py',
            'tests/programs/io_abi.act','tests/programs/io_imports.act')
    report=dict(schema_version=1,status='running',scope='Native I/O ABI; remaining unimplemented imports rejected',unimplemented=sorted(set(ABI['imports'])-set(IMPLEMENTED)),
                platform=PIN,inputs={name:sha256(ROOT/name) for name in inputs},
                interfaces=interfaces(t,output),cases=[],production_rejections=[],
                bank_zero=production_budget(),reservation_delta=dict(fixed_bank_zero=0,per_task_bank_zero=0),
                diagnostic_upper_bytes=sum(size+32 for _,size,_ in FIXTURES),abi_qualified=False)
    try:
        with emulator(a.bridge_dir.resolve(),a.rom.resolve(),output,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,a.rom,PIN)
            for name,optimize in cases:
                print('Running '+name+'...',flush=True)
                report['cases'].append(dict(name=name,status='pass',**abi_case(bridge,t,output/name,optimize,report['interfaces'])))
        for name in report['unimplemented']:
            print('Checking unimplemented '+name+'...',flush=True)
            report['production_rejections'].append(rejection_case(t,output/'reject'/name,name))
        report['status']='pass'
        if len(cases)==2:
            validate_record(report)
            report['abi_qualified']=True
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed native I/O ABI and remaining production rejection cases',flush=True)


if __name__=='__main__':main()
