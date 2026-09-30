"""Execute private heap mechanics against independent interval traces."""
import json
from pathlib import Path
import struct

from native_program import ROOT,build,compiler,execute,platform_files,require,sha256,verify_machine
from test_banked import PIN,changed_image
from test_cooperative import data
from banked_test_memory import read as far_read
from os_boundary import emulator
from heap_model import trace
from generate_heap import ABI


def inputs():
    return {p:sha256(ROOT/p) for p in ('abi/heap-v1.json','lib/exec/heapcore.act','lib/exec/heap-constants.inc',
        'lib/exec/exec-memory-types.inc','platform/altirraos/hosted.s','tools/native_program.py',
        'tools/generate_heap.py','tools/heap_model.py','tools/test_heap.py','tools/test_heap_core.py','tests/programs/heap_core.act')}


def trace_case(bridge,toolchain,output,optimize):
    operations,snapshots=trace()
    output.mkdir(parents=True,exist_ok=True)
    source=output/'heap_core.act'
    source.write_text((ROOT/'tests/programs/heap_core.act').read_text().replace('CONST COUNT=1',f'CONST COUNT={len(operations)}'))
    program=build(toolchain,source,output,optimize=optimize,banked=True)
    image=program['image']
    # Image-owned banks back the private test pool; payload need not be cleared.
    for address in (0x40000,0x5fff8):
        image['zero_fill'].append(dict(address=address,size=8,writable=True))
    encoded=b''.join(struct.pack('<4BII4x',*op) for op in operations)
    expected=bytearray()
    for result,available,extents in snapshots:
        raw=struct.pack('<III',result,available,len(extents))+b''.join(struct.pack('<II',a,b-a) for a,b in extents)
        require(len(raw)<=128,'Snapshot capacity exceeded')
        expected+=raw+bytes([0xa5])*(128-len(raw))
    for address,payload in [(0x3fff0,bytes([0xa5])*16),(0x60000,bytes([0xa5])*16),
                            (0x70000,encoded),(0x80000,bytes([0xa5])*len(expected))]:
        image['segments'].append(dict(address=address,bytes=list(payload),writable=True,executable=False))
    changed_image(program)
    runtime,_=execute(bridge,program,frame_limit=12000,timeout=240,load_timeout=180)
    require(data(bridge,image,'checks',True)==[1],'Missing completion check')
    require(data(bridge,image,'completed',True)==[len(operations)],'Trace did not finish')
    observed=far_read(bridge,0x80000,len(expected),output)
    for index in range(len(operations)):
        require(observed[index*128:(index+1)*128]==expected[index*128:(index+1)*128],
                f'Pool differs from interval model at operation {index}: {operations[index]}')
    for address in (0x3fff0,0x60000):
        require(far_read(bridge,address,16,output)==bytes([0xa5])*16,'Pool guard changed')
    return dict(build=program['build'],runtime=runtime,operations=operations,operation_count=len(operations),
                snapshots_sha256=__import__('hashlib').sha256(observed).hexdigest(),model='independent free intervals')


FAULTS={
    'outside-head':('pool.mh_First=HEAPCORE.MemChunk POINTER($060000)',0xff60),
    'zero-chunk':('pool.mh_First.mc_Bytes=0',0xff60),
    'cycle':('pool.mh_First.mc_Next=pool.mh_First',0xff60),
    'free-count':('pool.mh_Free=8',0xff60),
    'unaligned-chunk':('pool.mh_First.mc_Bytes=9',0xff60),
    'endpoint':('pool.mh_Upper=LONGCARD($1000008)',0xff60),
    'double-free':('HEAPCORE.Deallocate(@pool,BYTE POINTER($040000),8)',0xff61),
    'outside-free':('HEAPCORE.Deallocate(@pool,BYTE POINTER($03fff8),8)',0xff61),
    'overflow-free':('HEAPCORE.Deallocate(@pool,BYTE POINTER($040000),LONGCARD($ffffffff))',0xff61),
}


def fault_case(bridge,toolchain,output,optimize,variant):
    output.mkdir(parents=True,exist_ok=True)
    source=output/'heap_core.act';text=(ROOT/'tests/programs/heap_core.act').read_text()
    start=text.index('PROC Stamp(')
    mutation,status=FAULTS[variant]
    source.write_text(text[:start]+'PROC Main()\n  Init()\n  '+mutation+'\n  HEAPCORE.Validate(@pool)\n  checks=99\nRETURN\nENDMODULE\n')
    program=build(toolchain,source,output,optimize=optimize,banked=True)
    for address in (0x40000,0x5fff8):
        program['image']['zero_fill'].append(dict(address=address,size=8,writable=True))
    for address in (0x3fff0,0x60000):
        program['image']['segments'].append(dict(address=address,bytes=[0xa5]*16,writable=True,executable=False))
    changed_image(program)
    runtime,_=execute(bridge,program,expected_status=status,frame_limit=1200,timeout=90,load_timeout=180)
    require(data(bridge,program['image'],'checks',True)==[0],'Fault returned to caller')
    for address in (0x3fff0,0x60000):
        require(far_read(bridge,address,16,output)==bytes([0xa5])*16,'Fault changed pool guards')
    expected_header=bytearray(28)
    for offset,value,width in [(14,0x60000 if variant=='outside-head' else 0x40000,3),(17,0x40000,3),
                               (20,0x1000008 if variant=='endpoint' else 0x60000,4),
                               (24,8 if variant=='free-count' else 0x20000,4)]:
        expected_header[offset:offset+width]=value.to_bytes(width,'little')
    require(bytes(data(bridge,program['image'],'pool'))==expected_header,'Fault mutated header')
    expected_chunk=(0x40000 if variant=='cycle' else 0).to_bytes(3,'little')+bytes(1)
    expected_chunk+=(0 if variant=='zero-chunk' else 9 if variant=='unaligned-chunk' else 0x20000).to_bytes(4,'little')
    require(far_read(bridge,0x40000,8,output)==expected_chunk,'Fault mutated free chunk')
    return dict(build=program['build'],runtime=runtime,variant=variant,expected_status=status)


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    report=dict(schema_version=1,status='running',scope='Private MemHeader/MemChunk engine; no system heap',platform=PIN,inputs=inputs(),cases=[])
    cases=[(f'{name}-{mode}',name,mode=='opt') for mode in ('raw','opt') for name in ('trace',*FAULTS)]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown core case')
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config']=verify_machine(bridge,args.rom,PIN)
            for name,variant,optimize in cases:
                print('Running '+name+'...',flush=True)
                result=(trace_case(bridge,toolchain,output/name,optimize) if variant=='trace' else
                        fault_case(bridge,toolchain,output/name,optimize,variant))
                report['cases'].append(dict(name=name,status='pass',**result))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} private heap cases')
