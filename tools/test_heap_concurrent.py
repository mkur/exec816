"""Functional lifetime and deliberately stalled IRQ/NMI heap race probes.

These are separate from passive serial timing; race copies deliberately stop
inside partial metadata mutations until both real hardware entries execute.
"""
import adapter_state as adapter
from library_paths import read_source
import json
from native_program import ROOT,build,command,compiler,execute,platform_files,require,sha256,verify_machine
from os_boundary import emulator
from test_banked import PIN,changed_image
from test_cooperative import data
from banked_test_memory import read as far_read


def ownership(bridge,program):
    c=program['build']['memory']['constants']
    observed=(far_read(bridge,c['TABLE'],c['TABLE_BYTES'],program['output']) if c['TABLE']>=65536
              else bridge.memdump(c['TABLE'],c['TABLE_BYTES']))
    seed=(program['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(observed==seed,'Heap lifetime leaked bank ownership')


def race_program(toolchain,output,optimize,ports=False,registry=False):
    output.mkdir(parents=True,exist_ok=True)
    source=read_source(ROOT/'lib/exec/heapcore.act').replace('USE EXECLISTS','USE EXECLISTS\nUSE HEAPAPIPROBE')
    points={
        '  pool.mh_Free==-bytes':'  HEAPAPIPROBE.Fill(BYTE POINTER(0),1,0)\n  pool.mh_Free==-bytes',
        '  pool.mh_Free==+high-low':'  HEAPAPIPROBE.Fill(BYTE POINTER(0),2,0)\n  pool.mh_Free==+high-low',
        '  chunk=pool.mh_First\n  best=0\n  total=0':'  chunk=pool.mh_First\n  best=0\n  total=0\n  HEAPAPIPROBE.Fill(BYTE POINTER(0),4,0)',
    }
    for old,new in points.items():
        require(source.count(old)==1,'Ambiguous heap checkpoint')
        source=source.replace(old,new)
    (output/'heapcore.act').write_text(source)
    if ports and registry:
        lists=read_source(ROOT/'lib/exec/execlists.act').replace('MODULE EXECLISTS','MODULE EXECLISTS\nUSE HEAPAPIPROBE')
        points={
            '  item.ln_Pred=last':'  item.ln_Pred=last\n  HEAPAPIPROBE.Fill(BYTE POINTER(chain),1,0)',
            '  previous.ln_Succ=following':'  previous.ln_Succ=following\n  HEAPAPIPROBE.Fill(BYTE POINTER(item),2,0)',
        }
        for old,new in points.items():
            require(lists.count(old)==1,'Ambiguous port link checkpoint')
            lists=lists.replace(old,new)
        (output/'execlists.act').write_text(lists)
    fixture=ROOT/('tests/programs/ports_races.act' if ports else 'tests/programs/heap_races.act')
    if registry:
        require(ports,'Registry races use the port path')
        text=fixture.read_text()
        first=text.index('PROC RaceOperations()');last=text.index('PROC Main()',first)
        text=text[:first]+'''PROC RaceOperations()
  port.mp_Flags=EXEC.PA_IGNORE
  active=1
  EXEC.AddPort(@port)
  AwaitWake(1)
  EXEC.RemPort(@port)
  AwaitWake(2)
  EXEC.AddPort(@port)
  AwaitWake(3)
  active=0
  EXEC.RemPort(@port)
RETURN

'''+text[last:]
        fixture=output/'ports_registry_races.act';fixture.write_text(text)
        (output/'heapapiprobe.act').write_text((ROOT/'tests/programs/heapapiprobe.act').read_text())
    program=build(toolchain,fixture,output,optimize=optimize,tasks=True,heap_probe=True)
    image=program['image'];base=0xe0000
    # Claim the probe bank before deriving the first allocatable byte.
    image['segments'].append(dict(address=base,bytes=[0]*1024,writable=False,executable=True))
    changed_image(program)
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    labels={name:next(d['address'] for d in image['data'] if '_'+name+'_' in d['name'])
            for name in ('ACTIVE','WAKES','IRQREADS','CHECKPOINTS')}
    fault_offset=program['labels']['heap_fault']-program['build']['memory']['regions']['resident'][0]
    resident=(output/'hosted.bin').read_bytes()
    require(resident[fault_offset+2]==0x4c,'Fault thunk changed')
    finish=int.from_bytes(resident[fault_offset+3:fault_offset+5],'little')
    labels.update(BUFFER=next(b for b in range(c['MAX_BANKS']) if seed[b*4]==1)<<16,
                  FINISH=finish,POST_CONTINUE=program['labels']['signal_post']+7)
    if ports:
        labels.update(PORT_RACE=1,**{name:next(d['address'] for d in image['data'] if '_'+name+'_' in d['name']) for name in ('PORT','ITEM')})
        if not registry:labels['ATOMIC_PORTS']=1
    if registry:labels.update(REGISTRY_RACE=1,REGISTRY=program['build']['memory']['ports_storage']['BASE'])
    (output/'races.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',output,'-I',ROOT/'platform/altirraos',*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],
             '-o',output/'races.o',ROOT/'tests/programs/heap_races.s'])
    command(['ld65','-C',output/'races.cfg','-o',output/'races.bin','-Ln',output/'races.lbl',output/'races.o'])
    native_labels={line.split()[2].lstrip('.'):int(line.split()[1],16) for line in (output/'races.lbl').read_text().splitlines()}
    payload=(output/'races.bin').read_bytes();require(len(payload)<=1024,'Race code exceeds reserved image extent')
    image['segments'][-1]['bytes'][:len(payload)]=list(payload)
    for name,target in [('heap_probe_fill','checkpoint'),('signal_post','consumer')]:
        address=program['labels'][name]
        segment=next(s for s in image['segments'] if s['address']<=address<s['address']+len(s['bytes']))
        offset=address-segment['address']
        if name=='signal_post':
            binding=program['build']['task_storage']['SERIAL_BINDING']-program['build']['task_storage']['BASE']
            require(segment['bytes'][offset:offset+7]==[0xa2,*binding.to_bytes(2,'little'),0xc2,0x20,0x0b,0x3b],'IRQ prologue changed')
            segment['bytes'][offset:offset+7]=[0x5c,*native_labels[target].to_bytes(3,'little'),0xea,0xea,0xea]
        else:segment['bytes'][offset:offset+4]=[0x5c,*native_labels[target].to_bytes(3,'little')]
    if ports and not registry:
        points=sorted(name for name in program['labels'] if name.startswith('port_link_probe_'))
        require(len(points)==46,'Missing shared queue link access checkpoints')
        for name in points:
            address=program['labels'][name]
            segment=next(s for s in image['segments'] if s['address']<=address<s['address']+len(s['bytes']))
            offset=address-segment['address']
            require(segment['bytes'][offset:offset+4]==[0xea]*4,'Native link checkpoint changed')
            segment['bytes'][offset:offset+4]=[0x22,*native_labels['native_dequeue'].to_bytes(3,'little')]
    changed_image(program)
    program['build']['heap_race_probe']=dict(generated_core_sha256=sha256(output/'heapcore.act'),
        native_probe_sha256=sha256(output/'races.bin'),buffer=labels['BUFFER'],points=list(points),
        native_stack_peak=20 if ports and not registry else 2,serialized_wait='Wait for one actual POKEY IRQ and VBI while checking the worker cannot run')
    if ports:
        program['build']['port_race_probe']=dict(queue_source_sha256=sha256(output/'execlists.act' if registry else ROOT/'platform/altirraos/ports-atomic.s'),
            native_probe_sha256=sha256(output/'races.bin'),points=list(points),native_dequeue=not registry,irq_rejected_service='PutMsg',registry=registry)
    (output/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program


def case(bridge,toolchain,output,optimize,variant,bank=1):
    if variant=='races':program=race_program(toolchain,output,optimize)
    else:
        source='heap_lifetime.act' if variant=='lifetime' else 'heap_capacity.act'
        program=build(toolchain,ROOT/'tests/programs'/source,output,optimize=optimize,tasks=True,
                      heap_probe=variant=='lifetime',task_capacity=8 if variant=='capacity' else 4,kernel_bank=bank)
    try:result,_=execute(bridge,program,timeout=1200,frame_limit=24000)
    except Exception:
        observed={n:data(bridge,program['image'],n) for n in
                  (('phase','badIndex','created','consumed','sharedBlock','clearBlock','stage','before','after') if variant=='lifetime' else ('checks',))}
        (output/'diagnostic.json').write_text(json.dumps(dict(regs=bridge.regs(),state=list(bridge.memdump(adapter.STATE,64)),observed=observed),indent=2)+'\n')
        raise
    require(data(bridge,program['image'],'checks',True)==[1],'Concurrent heap fixture incomplete')
    if variant=='lifetime':
        counters={n:data(bridge,program['image'],n,True)[0] for n in ('created','consumed','removedDuringClear')}
        require(all(v==1 for v in counters.values()) and result['created']==4,'Missing handoff/reuse/removal')
        require(int.from_bytes(bytes(data(bridge,program['image'],'reserved')),'little')==0x40008,'Removed clear was reclaimed')
    elif variant=='races':
        counters={n:data(bridge,program['image'],n,True)[0] for n in ('wakes','irqReads','checkpoints')}
        require(counters==dict(wakes=3,irqReads=3,checkpoints=7),'Race posts or quiescence incomplete')
        require(result['native_irq_count']>=3 and result['native_nmi_count']>=3,'Missing real asynchronous entries')
    else:
        counters=dict(progress=data(bridge,program['image'],'progress'))
        require(counters['progress']==[1]*8 and result['created']==7,'Missing eight simultaneous heap callers')
    ownership(bridge,program)
    return dict(build=program['build'],runtime=result,counters=counters)


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[(f'{v}-{m}',m=='opt',v,1) for m in ('raw','opt') for v in ('lifetime','races')]
    cases += [(f'capacity-bank{b}-{m}',m=='opt','capacity',b) for b in (1,3) for m in ('raw','opt')]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown concurrent heap case')
    paths=('lib/exec/heapcore.act','lib/exec/heap-system.inc','lib/exec/task-memory.inc','platform/altirraos/heap.s',
           'tests/programs/heap_lifetime.act','tests/programs/heap_capacity.act','tests/programs/heap_races.act',
           'tests/programs/heap_races.s','tools/test_heap_concurrent.py')
    report=dict(schema_version=1,status='running',platform=PIN,cases=[],inputs={p:sha256(ROOT/p) for p in paths},
                scope='Functional lifetime, forced serialized IRQ/NMI races, and eight-task allocation; no timing claims')
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,args.rom,PIN)
            for name,optimize,variant,bank in cases:
                print('Running '+name+'...',flush=True)
                report['cases'].append(dict(name=name,status='pass',**case(bridge,toolchain,output/name,optimize,variant,bank)))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} concurrent heap cases',flush=True)
