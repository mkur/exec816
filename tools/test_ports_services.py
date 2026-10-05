"""Public port services, executed through emitted raw and optimized code."""
import adapter_state as adapter
import json
from native_program import ROOT,build,command,compiler,execute,platform_files,require,sha256,verify_machine
from test_banked import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
from os_boundary import emulator
from ports_model import exchange_trace

QUEUE_FAULTS={
    'softint':'port.mp_Flags=EXEC.PA_SOFTINT',
    'action3':'port.mp_Flags=3',
    'high-flags':'port.mp_Flags=$80',
    'null-port':'destination=EXEC.MsgPort POINTER(0)',
    'null-message':'msg=EXEC.Message POINTER(0)',
    'dead-owner':'port.mp_SigTask=@dead',
    'bad-bit':'port.mp_SigBit=32',
}
WAIT_FAULTS={'wrong-owner':'port.mp_SigTask=@dead','ignore':'port.mp_Flags=EXEC.PA_IGNORE',
             'null-wait':'destination=EXEC.MsgPort POINTER(0)'}


def queue_fault(bridge,toolchain,output,optimize,variant,waiting=False):
    output.mkdir(parents=True,exist_ok=True)
    source=output/'ports_fault.act'
    source.write_text('''MODULE PORTFAULT
USE EXEC
USE EXECLISTS
EXEC.MsgPort port
EXEC.Message item
EXEC.Task dead
BYTE reached
PROC Main()
  EXEC.MsgPort POINTER destination
  EXEC.Message POINTER msg
  port.mp_Node.ln_Type=EXEC.NT_MSGPORT
  port.mp_SigTask=EXEC.FindTask(BYTE POINTER(0)) port.mp_SigBit=31
  EXECLISTS.NewList(@port.mp_MsgList)
  destination=@port msg=@item
  '''+(WAIT_FAULTS if waiting else QUEUE_FAULTS)[variant]+'''
  '''+('msg=EXEC.WaitPort(destination)' if waiting else 'EXEC.PutMsg(destination,msg)')+'\n  reached=1\n\nRETURN\n\nENDMODULE\n')
    program=build(toolchain,source,output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,expected_status=4,timeout=180,frame_limit=2400)
    require(data(bridge,program['image'],'reached')==[0],'Invalid send returned')
    require(data(bridge,program['image'],'item')==[0]*16,'Invalid send changed message')
    raw=bytes(data(bridge,program['image'],'port'))
    address=next(d['address'] for d in program['image']['data'] if '_PORT_' in d['name'])
    require(raw[16:25]==(address+19).to_bytes(3,'little')+bytes(3)+(address+16).to_bytes(3,'little'),
            'Invalid send changed queue')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,variant=variant,unmodified_queue=True,unmodified_message=True)


def queues(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/ports_queues.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000,timer_irq=True)
    checks=data(bridge,program['image'],'checks',True)
    trace=data(bridge,program['image'],'trace',True)
    require(checks==[1]*12+[0]*4,'Queue checks: '+str(checks))
    require(trace==exchange_trace()+[0]*3,'FIFO/protocol trace: '+str(trace))
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,trace=trace)


def queue_races(bridge,toolchain,output,optimize,registry=False):
    from test_heap_concurrent import race_program
    program=race_program(toolchain,output,optimize,ports=True,registry=registry)
    runtime,_=execute(bridge,program,timeout=360,frame_limit=12000)
    require(data(bridge,program['image'],'checks',True)==[1],'Port race fixture incomplete')
    counters={n:data(bridge,program['image'],n,True)[0] for n in ('wakes','irqReads','checkpoints')}
    require(counters==dict(wakes=3,irqReads=3,checkpoints=3),'Port race counts: '+str(counters))
    require(runtime['native_irq_count']>=3 and runtime['native_nmi_count']>=3,'Missing IRQ/NMI link-write entries')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,counters=counters,
                scope=('Real IRQ/NMI inside partial registry writes' if registry else
                    'NMI before/after shared link accesses; requested IRQ deferred until unmasking')+
                    '; IRQ port COP rejects; worker resumes after guard release')


def queue_context(bridge,toolchain,output,optimize,variant,waiting=False,nonempty=False):
    from test_banked import changed_image
    from generate_tasks import ABI as TASK_ABI
    program=build(toolchain,ROOT/'tests/programs/ports_context.act',output,optimize=optimize,tasks=True)
    image=program['image'];base=0xe0000
    labels={name:next(d['address'] for d in image['data'] if '_'+name+'_' in d['name']) for name in ('PORT','CHECKS')}
    labels.update(GETMSG=program['labels']['ports_wait_port' if waiting else 'ports_get_msg'],VARIANT=variant)
    source=ROOT/'tests/programs/ports_context.s'
    if waiting:
        text=source.read_text().replace('lda #P_PA_IGNORE','lda #P_PA_SIGNAL')
        setup='''    lda #^T_ROOT
    sta f:PORT+P_MSGPORT_MP_SIGTASK+2
    rep #$20
    lda #.loword(T_ROOT)
    sta f:PORT+P_MSGPORT_MP_SIGTASK
'''
        if nonempty:
            labels['ITEM']=next(d['address'] for d in image['data'] if '_ITEM_' in d['name'])
            setup+='''    lda #.loword(ITEM)
    sta f:PORT+P_MSGPORT_MP_MSGLIST
    sep #$20
    lda #^ITEM
    sta f:PORT+P_MSGPORT_MP_MSGLIST+2
'''
        setup+='    sep #$20\n'
        text=text.replace('    lda #$12\n',setup+'    lda #$12\n')
        source=output/'masked-wait.s';source.write_text(text)
    (output/'context.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',output,*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],'-o',output/'context.o',source])
    command(['ld65','-C',output/'context.cfg','-o',output/'context.bin',output/'context.o'])
    image['segments'].append(dict(address=base,bytes=list((output/'context.bin').read_bytes()),writable=False,executable=True))
    segment=next(s for s in image['segments'] if s['address']==image['entry'])
    segment['bytes'][:4]=[0x5c,*base.to_bytes(3,'little')];changed_image(program)
    fault=waiting or variant==2
    runtime,_=execute(bridge,program,expected_status=4 if fault else 0,timeout=180,frame_limit=2400)
    words=data(bridge,image,'checks',True)
    if fault:require(words[7]==0,'Invalid context returned')
    else:
        require(words[:4]==[0,0,TASK_ABI['constants']['PROFILE_TAG'],adapter.TASK0_DP] and words[4]==words[6] and
                words[5]&255==0x12 and (words[5]>>8)&0x3c==(4 if variant else 0) and words[7]==1,
                'Port native context: '+str(words))
    clean_ownership(bridge,program,output)
    if waiting:
        port=bytes(data(bridge,image,'port'))
        expected=labels['ITEM'] if nonempty else labels['PORT']+19
        require(int.from_bytes(port[16:19],'little')==expected,'Masked WaitPort changed queue')
        require(runtime['root_task'][20:28]==[0]*8,'Masked WaitPort changed signals')
    return dict(build=program['build'],runtime=runtime,checks=words,variant=variant,waiting=waiting,nonempty=nonempty,native_probe_sha256=sha256(output/'context.bin'))


def queue_crossing(bridge,toolchain,output,optimize):
    from banked_test_memory import read as far_read
    regions=[(0x4fff0,bytes([0xa5])*64),(0x6fff0,bytes([0xa5])*32)]
    program=build(toolchain,ROOT/'tests/programs/ports_crossing.act',output,optimize=optimize,tasks=True,image_data=regions)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    checks=data(bridge,program['image'],'checks',True)
    require(checks==[1]*8,'Far queues/forwarding/reuse: '+str(checks))
    for base,blob in regions:
        observed=far_read(bridge,base,len(blob),output)
        low,size=(3,27) if base==0x4fff0 else (4,16)
        require(observed[:low]==blob[:low] and observed[low+size:]==blob[low+size:],'Crossing port/message guard changed')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,port=0x4fff3,message=0x6fff4,reuses=8)


def queue_handoff(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/ports_handoff.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    checks=data(bridge,program['image'],'checks',True)
    require(checks==[1]*6,'Reply/reuse before PutMsg return: '+str(checks))
    # The production send wrapper has no post-publication dereference.
    code=(output/'hosted.bin.signals').read_bytes()
    end=program['labels']['ports_put_msg_end']-program['build']['task_storage']['BASE']-0x1000
    require(code[end-3:end]==bytes([2,0x50,0x6b]),'PutMsg does work after COP return')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,reply_and_reuse_before_put_return=True)


def wait_port(bridge,toolchain,output,optimize,probe=0):
    program=build(toolchain,ROOT/'tests/programs/ports_wait.act',output,optimize=optimize,tasks=True,policy_probe=probe)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    checks=data(bridge,program['image'],'checks',True)
    require(checks==[1]*14,'WaitPort ownership/queue/signal/Forbid: '+str(checks))
    if probe:require(runtime['signal_nmi_checkpoints']>0,'Missing wait-publication NMI')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,wrapper_stack_peak=11,publication_probe=probe)


def wait_gap(bridge,toolchain,output,optimize):
    from test_banked import changed_image
    program=build(toolchain,ROOT/'tests/programs/ports_wait_gap.act',output,optimize=optimize,tasks=True)
    image=program['image'];base=0xe0000;entry=program['labels']['ports_wait_empty']
    labels={name:next(d['address'] for d in image['data'] if '_'+name+'_' in d['name']) for name in ('GO','CHECKPOINTS')}
    labels.update(YIELD=program['labels']['exec_yield'],CONTINUE=entry+4)
    (output/'gap.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65',*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],'-o',output/'gap.o',ROOT/'tests/programs/ports_wait_gap.s'])
    command(['ld65','-C',output/'gap.cfg','-o',output/'gap.bin',output/'gap.o'])
    segment=next(s for s in image['segments'] if s['address']<=entry<s['address']+len(s['bytes']))
    offset=entry-segment['address']
    require(segment['bytes'][offset:offset+4]==[0xa3,12,0x85,0],'WaitPort empty continuation changed')
    segment['bytes'][offset:offset+4]=[0x5c,*base.to_bytes(3,'little')]
    image['segments'].append(dict(address=base,bytes=list((output/'gap.bin').read_bytes()),writable=False,executable=True))
    changed_image(program)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    checks=data(bridge,image,'checks',True)
    require(checks==[1]*4,'Arrival between peek and Wait: '+str(checks))
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,
                forced_interleaving='Producer enqueues after the empty peek and before Wait; no IRQ calls a port API')


def run(args):
    pin=getattr(args,'pin',PIN)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    variants=list(QUEUE_FAULTS) if args.suite=='queue-faults' else list(WAIT_FAULTS) if args.suite=='wait-faults' else [f'context-{i}' for i in range(3)] if args.suite=='queue-context' else [f'masked-{i}' for i in range(2)] if args.suite=='wait-masked' else [args.suite]
    if args.suite=='wait-publication':variants=['publication-2','publication-3']
    if args.suite=='delete-faults':variants=['delete-0','delete-1','delete-2']
    if args.suite=='capacity':variants=['capacity-1','capacity-3']
    if args.suite=='registry':variants=[f'registry-{bank}-{capacity}' for bank in (1,3) for capacity in (4,8)]
    cases=[(variant+'-'+mode,mode=='opt',variant) for mode in ('raw','opt') for variant in variants]
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown port case')
    paths=('abi/tasks.json','abi/ports.json','lib/exec/taskpolicy.act','lib/exec/task-ports.inc',
           'lib/exec/task-signals.inc','platform/altirraos/ports.s','platform/altirraos/tasks.s',
           'tools/native_program.py','tools/generate_tasks.py','tools/generate_ports.py',
           'tools/test_ports_services.py','tools/ports_model.py','tests/programs/ports_queues.act',
           'tools/test_heap_concurrent.py','tests/programs/heap_races.s','tests/programs/ports_races.act',
           'tests/programs/ports_context.act','tests/programs/ports_context.s',
           'tests/programs/ports_crossing.act','tests/programs/ports_handoff.act',
           'lib/exec/portcore.act','tools/test_ports_lifetime.py','tests/programs/ports_lifetime.act',
           'tests/programs/ports_delete_fault.act','tests/programs/ports_lifetime_masked.act',
           'tests/programs/ports_lifetime_masked.s','examples/messages.act',
           'tools/test_ports_concurrent.py','tests/programs/ports_capacity.act',
           'tests/programs/ports_wait_remove.act','tools/test_ports_registry.py',
           'tests/programs/ports_registry.act','tests/programs/ports_registry_long.act',
           'tests/programs/ports_registry_peer.act')
    report=dict(schema_version=1,status='running',suite=args.suite,platform=pin,
                inputs={p:sha256(ROOT/p) for p in paths},cases=[])
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=pin) as bridge:
            report['machine']=verify_machine(bridge,args.rom,pin)
            for name,optimize,variant in cases:
                print('Running '+name+'...',flush=True)
                if args.suite=='queue-faults':observed=queue_fault(bridge,toolchain,output/name,optimize,variant)
                elif args.suite=='wait-faults':observed=queue_fault(bridge,toolchain,output/name,optimize,variant,waiting=True)
                elif args.suite=='queue-races':observed=queue_races(bridge,toolchain,output/name,optimize)
                elif args.suite=='registry-races':observed=queue_races(bridge,toolchain,output/name,optimize,registry=True)
                elif args.suite=='queue-context':observed=queue_context(bridge,toolchain,output/name,optimize,int(variant.split('-')[1]))
                elif args.suite=='queue-crossing':observed=queue_crossing(bridge,toolchain,output/name,optimize)
                elif args.suite=='queue-handoff':observed=queue_handoff(bridge,toolchain,output/name,optimize)
                elif args.suite=='wait':observed=wait_port(bridge,toolchain,output/name,optimize)
                elif args.suite=='wait-publication':observed=wait_port(bridge,toolchain,output/name,optimize,int(variant.split('-')[1]))
                elif args.suite=='wait-gap':observed=wait_gap(bridge,toolchain,output/name,optimize)
                elif args.suite=='wait-masked':observed=queue_context(bridge,toolchain,output/name,optimize,1,waiting=True,nonempty=variant.endswith('1'))
                elif args.suite in ('lifetime','example'):
                    from test_ports_lifetime import lifetime,example
                    observed=(lifetime if args.suite=='lifetime' else example)(bridge,toolchain,output/name,optimize)
                elif args.suite=='delete-faults':
                    from test_ports_lifetime import fault
                    observed=fault(bridge,toolchain,output/name,optimize,int(variant.split('-')[1]))
                elif args.suite=='lifetime-masked':
                    from test_ports_lifetime import masked
                    observed=masked(bridge,toolchain,output/name,optimize)
                elif args.suite=='wait-removal':
                    from test_ports_concurrent import wait_removal
                    observed=wait_removal(bridge,toolchain,output/name,optimize)
                elif args.suite=='capacity':
                    from test_ports_concurrent import capacity
                    observed=capacity(bridge,toolchain,output/name,optimize,int(variant.split('-')[1]))
                elif args.suite=='registry':
                    from test_ports_registry import registry
                    _,bank,capacity=variant.split('-')
                    observed=registry(bridge,toolchain,output/name,optimize,int(bank),int(capacity))
                elif args.suite=='registry-peer':
                    from test_ports_registry import peer
                    observed=peer(bridge,toolchain,output/name,optimize)
                else:observed=queues(bridge,toolchain,output/name,optimize)
                report['cases'].append(dict(name=name,status='pass',**observed))
        report['status']='pass'
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} port service cases',flush=True)
