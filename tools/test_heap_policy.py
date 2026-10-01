"""Compare serialized system heap policy with an independent region model."""
import adapter_state as adapter
import hashlib
import json
import struct
from pathlib import Path
from native_program import ROOT,build,compiler,execute,platform_files,require,sha256,verify_machine
from test_banked import PIN,changed_image
from test_cooperative import data
from banked_test_memory import read as far_read
from os_boundary import emulator
from heap_model import system_trace

FAULTS={
    'null-free':('HEAPPOLICY.Free(BYTE POINTER(0),1)',0xff61),
    'unaligned-free':('p=HEAPPOLICY.Reserve(24,0)\n  HEAPPOLICY.Free(BYTE POINTER(ADDRESS(p)+SIZE(1)),8)',0xff61),
    'overflow-free':('p=HEAPPOLICY.Reserve(24,0)\n  HEAPPOLICY.Free(p,LONGCARD($ffffffff))',0xff61),
    'region-cycle':('state=HEAPPOLICY.GetState()\n  state.regions.lh_Head.ln_Succ=state.regions.lh_Head\n  ignored=HEAPPOLICY.Avail(0)',0xff60),
}


def fault_case(bridge,toolchain,output,optimize,variant):
    output.mkdir(parents=True,exist_ok=True)
    source=output/'heap_policy.act';text=(ROOT/'tests/programs/heap_policy.act').read_text()
    mutation,status=FAULTS[variant]
    source.write_text(text[:text.index('PROC Main()')]+'''PROC Main()
  BYTE POINTER p
  HEAPPOLICY.HeapState POINTER state
  LONGCARD ignored
  switching=1
  '''+mutation+'\n  checks=99\nRETURN\nENDMODULE\n')
    program=build(toolchain,source,output,optimize=optimize,tasks=True)
    result,_=execute(bridge,program,expected_status=status,frame_limit=1200,timeout=90)
    require(data(bridge,program['image'],'checks',True)==[0],'Invalid operation returned')
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(bridge.memdump(c['TABLE'],c['TABLE_BYTES'])==seed,'Fault shutdown leaked heap ownership')
    return dict(build=program['build'],runtime=result,variant=variant,expected_status=status)


def case(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/heap_policy.act',output,optimize=optimize,tasks=True,
        image_data=[(0x70000,b'HOLE'),(0xd0000,bytes(16)),(0xdfff0,bytes([0xa5])*16),(0xefff0,bytes([0xa5])*16)])
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    regions=[]
    for bank in range(c['MAX_BANKS']):
        if seed[bank*4]!=1:continue
        if regions and regions[-1][1]==bank<<16:regions[-1][1]=(bank+1)<<16
        else:regions.append([bank<<16,(bank+1)<<16,0,17])
    require(len(regions)>1,'Policy probe needs separated regions')
    regions[1][2]=10
    operations,snapshots=system_trace(regions)
    for segment in program['image']['segments']:
        if segment['address']==0xd0000:segment['bytes'][:2]=list(struct.pack('<H',len(operations)))
    encoded=b''.join(struct.pack('<4BIII',*op) for op in operations)
    program['image']['segments'].append(dict(address=0xd0010,bytes=list(encoded),writable=True,executable=False))
    changed_image(program)
    try:
        result,_=execute(bridge,program,timer_irq=True,frame_limit=12000,timeout=1200)
    except Exception:
        # Safe parsed state only; bridge transport logs contain credentials.
        diagnostic=dict(regs=bridge.regs(),state=list(bridge.memdump(adapter.STATE,64)),
                        completed=data(bridge,program['image'],'completed',True),
                        checks=data(bridge,program['image'],'checks',True))
        (output/'diagnostic.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
        raise
    require(data(bridge,program['image'],'checks',True)==[1],'Policy did not complete')
    require(data(bridge,program['image'],'completed',True)==[len(operations)],'Policy trace incomplete')
    active=bytearray(seed)
    for bank in range(c['MAX_BANKS']):
        if seed[bank*4]==1:active[bank*4:bank*4+4]=bytes([3,0,5,0])
    require(bytes(data(bridge,program['image'],'bankSnapshots'))==bytes(active)*2,'Allocation or query changed bank ownership')
    require(result['native_irq_count']>0 and result['native_nmi_count']>0,'Missing asynchronous entry coverage')
    raw=far_read(bridge,0xe0000,len(operations)*256,output)
    verified=bytearray()
    for index,(answer,available,largest,linear,total,extents) in enumerate(snapshots):
        expected=struct.pack('<6I',answer,available,largest,linear,total,6+len(extents)*3)
        expected+=b''.join(struct.pack('<III',*extent) for extent in extents)
        observed=raw[index*256:index*256+len(expected)]
        require(observed==expected,f'System policy differs at operation {index}: {operations[index]}; observed {observed[:24].hex()}, expected {expected[:24].hex()}')
        verified+=observed
    for address in (0xdfff0,0xefff0):require(far_read(bridge,address,16,output)==bytes([0xa5])*16,'Policy guard changed')
    require(bridge.memdump(c['TABLE'],c['TABLE_BYTES'])==seed,'Policy cleanup changed ownership')
    return dict(build=program['build'],runtime=result,regions=regions,operations=operations,
                operation_count=len(operations),snapshots_sha256=hashlib.sha256(verified).hexdigest(),
                model='Independent region priorities and free intervals',guard='Task-context qualification harness; E816_SWITCHING=1; IRQs remain enabled')


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[(variant+'-'+mode,mode=='opt',variant) for mode in ('raw','opt') for variant in ('policy',*FAULTS)]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown policy case')
    report=dict(schema_version=1,status='running',platform=PIN,cases=[],inputs={p:sha256(ROOT/p) for p in
        ('lib/exec/heappolicy.act','lib/exec/heap-system.inc','lib/exec/heapcore.act','tools/native_program.py',
         'tools/heap_model.py','tests/programs/heap_policy.act','tools/test_heap_policy.py')})
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config']=verify_machine(bridge,args.rom,PIN)
            for name,optimize,variant in cases:
                print('Running '+name+'...',flush=True)
                observed=case(bridge,toolchain,output/name,optimize) if variant=='policy' else fault_case(bridge,toolchain,output/name,optimize,variant)
                report['cases'].append(dict(name=name,status='pass',**observed))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} system policy cases',flush=True)
