"""Execute the public memory API through current Task-native bindings."""
import json
from pathlib import Path
from native_program import ROOT,build,command,compiler,execute,platform_files,require,sha256,verify_machine
from test_banked import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from os_boundary import emulator
from generate_tasks import ABI as TASK_ABI


def context(bridge,toolchain,output,optimize,variant):
    program=build(toolchain,ROOT/'tests/programs/heap_context.act',output,optimize=optimize,tasks=True)
    image=program['image'];base=0xe0000
    checks=next(d['address'] for d in image['data'] if '_CHECKS_' in d['name'])
    (output/'context.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',output,'-D',f'VARIANT={variant}','-D',f'CHECKS={checks}',
             '-D',f'AVAIL={program["labels"]["heap_avail_mem"]}',
             '-o',output/'context.o',ROOT/'tests/programs/heap_context.s'])
    command(['ld65','-C',output/'context.cfg','-o',output/'context.bin',output/'context.o'])
    image['segments'].append(dict(address=base,bytes=list((output/'context.bin').read_bytes()),writable=False,executable=True))
    segment=next(s for s in image['segments'] if s['address']==image['entry'])
    segment['bytes'][:4]=[0x5c,*base.to_bytes(3,'little')]
    from test_banked import changed_image
    changed_image(program)
    result,_=execute(bridge,program,expected_status=4 if variant else 0,timeout=180,frame_limit=2400)
    words=data(bridge,image,'checks',True)
    if variant:require(words[7]==0,'Invalid context returned')
    else:
        c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
        total=sum(seed[b*4]==1 for b in range(c['MAX_BANKS']))*65536
        require(words[0]+(words[1]<<16)==total,'32-bit COP result mismatch')
        require(words[2]==TASK_ABI['version'] and words[3]==0x2200 and words[4]==words[6] and
                words[5]&255==0x12 and (words[5]>>8)&0x3c==0 and words[7]==1,
                f'Memory COP context mismatch: {words}')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=result,checks=words,variant=variant)

FAULTS={
    'null-free':('EXEC.FreeMem(BYTE POINTER(0),1)',0xff61),
    'unaligned-free':('p=EXEC.AllocMem(24,0)\n  EXEC.FreeMem(BYTE POINTER(ADDRESS(p)+SIZE(1)),8)',0xff61),
    'double-free':('p=EXEC.AllocMem(24,0)\n  EXEC.FreeMem(p,24)\n  EXEC.FreeMem(p,24)',0xff61),
    'overflow-free':('p=EXEC.AllocMem(24,0)\n  EXEC.FreeMem(p,LONGCARD($ffffffff))',0xff61),
    'vector-unaligned':('EXEC.FreeVec(BYTE POINTER($ffffff))',0xff61),
    'vector-outside':('EXEC.FreeVec(BYTE POINTER($fffff8))',0xff61),
    'vector-prefix':('p=EXEC.AllocVec(9,0)\n  sizeWord=LONGCARD POINTER(ADDRESS(p)-SIZE(8))\n  sizeWord^=16\n  EXEC.FreeVec(p)',0xff61),
    'vector-request':('p=EXEC.AllocVec(9,0)\n  sizeWord=LONGCARD POINTER(ADDRESS(p)-SIZE(4))\n  sizeWord^=0\n  EXEC.FreeVec(p)',0xff61),
}


def clean_ownership(bridge,program,output):
    c=program['build']['memory']['constants']
    seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(bridge.memdump(c['TABLE'],c['TABLE_BYTES'])==seed,'API shutdown ownership mismatch')


def example(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'examples/memory.act',output,optimize=optimize,tasks=True)
    result,_=execute(bridge,program,timeout=240,frame_limit=12000)
    require(data(bridge,program['image'],'completed')==[1],'Public example did not complete')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=result)


def fault(bridge,toolchain,output,optimize,variant):
    output.mkdir(parents=True,exist_ok=True)
    mutation,status=FAULTS[variant]
    source=output/'heap_fault.act'
    source.write_text('MODULE HEAPFAULT\nUSE EXEC\nCARD checks\nPROC Main()\n  BYTE POINTER p\n  LONGCARD POINTER sizeWord\n  '+mutation+'\n  checks=99\nRETURN\nENDMODULE\n')
    program=build(toolchain,source,output,optimize=optimize,tasks=True)
    result,_=execute(bridge,program,expected_status=status,timeout=180,frame_limit=2400)
    require(data(bridge,program['image'],'checks',True)==[0],'Invalid operation returned')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=result,expected_status=status)


def clearing(bridge,toolchain,output,optimize,variant):
    source=ROOT/'tests/programs/heap_clear.act'
    if variant=='clear-vector':
        output.mkdir(parents=True,exist_ok=True)
        (output/'heapapiprobe.act').write_text((ROOT/'tests/programs/heapapiprobe.act').read_text())
        text=source.read_text().replace('CONST ROUNDED=$40008','CONST ROUNDED=$40008\nCONST BACKING=$40010')
        text=text.replace('AllocMem(LONGCARD(ROUNDED)','AllocMem(LONGCARD(BACKING)')
        text=text.replace('Fill(p,LONGCARD(ROUNDED)','Fill(p,LONGCARD(BACKING)')
        text=text.replace('testBlock=ADDRESS(p)','testBlock=ADDRESS(p)+SIZE(8)')
        text=text.replace('FreeMem(p,LONGCARD(ROUNDED))','FreeMem(p,LONGCARD(BACKING))')
        text=text.replace('AllocMem(LONGCARD(REQUEST)','AllocVec(LONGCARD(REQUEST)')
        text=text.replace('FreeMem(p,LONGCARD(REQUEST))','FreeVec(p)')
        source=output/'heap_clear.act';source.write_text(text)
    program=build(toolchain,source,output,optimize=optimize,tasks=True,heap_probe=True)
    result,_=execute(bridge,program,timer_irq=True,timeout=1200,frame_limit=24000)
    counters={n:data(bridge,program['image'],n,True)[0] for n in ('checks','overlap','allocations')}
    require(all(v==1 for v in counters.values()),f'Clear concurrency counters: {counters}')
    require(result['vbi_dispatches']>0 and result['native_irq_count']>0,'Missing preemption/IRQ coverage')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=result,counters=counters,requested_bytes=0x40001,
                verified_payload='Independent byte-wise verification of entire payload; seven padding bytes and both neighbours retain poison',
                concurrency='Worker observed partial clear, allocated/freed disjoint memory before clear returned',
                masked_caller='Public AllocMem(CLEAR) and FreeMem preserve I=1')


def basic(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/heap_api.act',output,optimize=optimize,tasks=True)
    result,_=execute(bridge,program,timeout=240,frame_limit=12000)
    raw=bytes(data(bridge,program['image'],'facts'))
    facts=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    free=[b for b in range(c['MAX_BANKS']) if seed[b*4]==1]
    total=len(free)*65536;first=free[0]<<16
    expected=[total,total,65536,0,0,0,first,17,total,0,24,9,first+8,0,first,total,
              first,65536,131080,1,0,total,TASK_ABI['version'],0,total,65536,0,0]
    require(facts==expected,f'Public API facts: {facts}; expected {expected}')
    require(data(bridge,program['image'],'checks',True)==[1],'Public API did not complete')
    require(bridge.memdump(c['TABLE'],c['TABLE_BYTES'])==seed,'Public API shutdown ownership mismatch')
    labels=program['labels'];image=program['image']
    native=next(s for s in image['segments'] if s['address']==program['build']['task_storage']['BASE']+0x1000)
    require(bytes(native['bytes'])==(output/'hosted.bin.signals').read_bytes(),'Packaged native code differs from final bindings')
    targets={}
    for operation in ('Allocate','Deallocate'):
        routine=next(r for r in image['routines'] if r['name'].startswith('M_HEAPCORE_'+operation.upper()+'_'))
        offset=labels['heap_'+operation.lower()+'_end']-4-native['address']
        require(bytes(native['bytes'][offset:offset+4])==b'\x5c'+routine['address'].to_bytes(3,'little'),'Private call thunk has stale address')
        targets[operation]=routine['address']
    return dict(build=program['build'],runtime=result,facts=facts,private_targets=targets,
                upper_native_bytes=len(native['bytes']),bank_zero_reservation_delta=dict(fixed=0,per_task=0))


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[(variant+'-'+mode,mode=='opt',variant) for mode in ('raw','opt')
           for variant in ('basic','example','clear','clear-vector',*FAULTS,*(f'context-{i}' for i in range(7)))]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown API case')
    paths=('abi/tasks.json','abi/heap-v1.json','lib/exec/taskpolicy.act','lib/exec/task-memory.inc',
           'lib/exec/heap-system.inc','lib/exec/heap-call-types.inc','platform/altirraos/heap.s',
           'platform/altirraos/tasks.s','tools/native_program.py','tools/generate_tasks.py',
           'tools/generate_heap.py','tests/programs/heap_api.act','tools/test_heap_api.py',
           'tests/programs/heap_clear.act','tests/programs/heapapiprobe.act','platform/altirraos/heap-probe.s',
           'tests/programs/heap_context.act','tests/programs/heap_context.s','examples/memory.act')
    report=dict(schema_version=1,status='running',platform=PIN,cases=[],inputs={p:sha256(ROOT/p) for p in paths})
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config']=verify_machine(bridge,args.rom,PIN)
            for name,optimize,variant in cases:
                print('Running '+name+'...',flush=True)
                if variant=='basic':observed=basic(bridge,toolchain,output/name,optimize)
                elif variant=='example':observed=example(bridge,toolchain,output/name,optimize)
                elif variant.startswith('clear'):observed=clearing(bridge,toolchain,output/name,optimize,variant)
                elif variant.startswith('context-'):observed=context(bridge,toolchain,output/name,optimize,int(variant.split('-')[1]))
                else:observed=fault(bridge,toolchain,output/name,optimize,variant)
                report['cases'].append(dict(name=name,status='pass',**observed))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} public memory API cases',flush=True)
