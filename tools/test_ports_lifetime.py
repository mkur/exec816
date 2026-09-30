"""Creation/deletion resource transactions and the public request/reply example."""
from native_program import ROOT,build,command,execute,require,sha256
from test_cooperative import data
from test_heap_api import clean_ownership


def lifetime(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/ports_lifetime.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=480,frame_limit=24000)
    require(data(bridge,program['image'],'checks',True)==[15],'Port resource transactions incomplete')
    raw=bytes(data(bridge,program['image'],'facts'))
    facts=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
    c=program['build']['memory']['constants'];seed=(output/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    total=sum(seed[b*4]==1 for b in range(c['MAX_BANKS']))*65536
    require(facts==[total,total-128,total,0,0,total,0xffff,0xffffffff,0,total],'Resource accounting: '+str(facts))
    require(runtime['created']==0,'Ports allocated Task contexts')
    code=(output/'hosted.bin.signals').read_bytes();base=program['build']['task_storage']['BASE']+0x1000
    helpers={}
    for operation,label in [('CreateMsgPort','create_msg_port'),('DeleteMsgPort','delete_msg_port')]:
        routine=next(r for r in program['image']['routines'] if r['name'].startswith('M_PORTCORE_'+operation.upper()+'_'))
        end=program['labels']['ports_'+label+'_end']-base
        require(code[end-4:end]==b'\x5c'+routine['address'].to_bytes(3,'little'),'Port thunk target not finalized')
        helpers[operation]=dict(address=routine['address'],local_stack_peak=routine['local_stack_peak'],native_thunk_stack_peak=0)
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,facts=facts,helpers=helpers,heap_bytes_per_port=32)


def example(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'examples/messages.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    require(data(bridge,program['image'],'completed')==[1] and data(bridge,program['image'],'failureCode')==[0],'Public request/reply example failed')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,completed=1,error=0)


def fault(bridge,toolchain,output,optimize,variant):
    from banked_test_memory import read as far_read
    program=build(toolchain,ROOT/'tests/programs/ports_delete_fault.act',output,optimize=optimize,tasks=True)
    image=program['image'];address=next(d['address'] for d in image['data'] if '_VARIANT_' in d['name'])
    runtime,_=execute(bridge,program,expected_status=4,before_run=lambda b:b.poke(address,variant),timeout=240,frame_limit=12000)
    require(data(bridge,image,'reached')==[0],'Invalid deletion returned')
    allocated=int.from_bytes(bytes(data(bridge,image,'allocated')),'little')
    require(allocated!=0,'Creation failed before deletion misuse')
    snapshot=bytes(data(bridge,image,'snapshot'))
    require(far_read(bridge,allocated,27,output)==snapshot,'Rejected deletion changed/freed port storage')
    before=int.from_bytes(bytes(data(bridge,image,'beforeMask')),'little')
    require(int.from_bytes(bytes(runtime['root_task'][16:20]),'little')==before,'Rejected deletion released owner signal')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,variant=variant,unchanged_port=True,unchanged_owner_mask=before)


def masked(bridge,toolchain,output,optimize):
    from test_banked import changed_image
    program=build(toolchain,ROOT/'tests/programs/ports_lifetime_masked.act',output,optimize=optimize,tasks=True,heap_probe=True)
    image=program['image'];base=0xe0000
    labels=dict(CREATE=program['labels']['ports_create_msg_port'],DELETE=program['labels']['ports_delete_msg_port'],
                CHECKS=next(d['address'] for d in image['data'] if '_CHECKS_' in d['name']))
    (output/'masked.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65',*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],'-o',output/'masked.o',ROOT/'tests/programs/ports_lifetime_masked.s'])
    command(['ld65','-C',output/'masked.cfg','-o',output/'masked.bin',output/'masked.o'])
    address=program['labels']['heap_probe_masked']
    segment=next(s for s in image['segments'] if s['address']<=address<s['address']+len(s['bytes']))
    offset=address-segment['address'];segment['bytes'][offset:offset+4]=[0x5c,*base.to_bytes(3,'little')]
    image['segments'].append(dict(address=base,bytes=list((output/'masked.bin').read_bytes()),writable=False,executable=True))
    changed_image(program)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
    checks=data(bridge,image,'checks',True)
    require(checks[2]==1 and all(v&4 for v in checks[:2]),'Create/Delete lost caller I: '+str(checks))
    require(data(bridge,image,'before')==data(bridge,image,'after'),'Masked lifetime leaked memory')
    require(runtime['root_task'][16:20]==[255,255,0,0],'Masked lifetime leaked signal')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,native_probe_sha256=sha256(output/'masked.bin'))
