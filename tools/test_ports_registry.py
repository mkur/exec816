"""Registry order, borrowed names, retained pointers and resolved prefix maps."""
from native_program import ROOT,build,execute,require
from test_cooperative import data
from banked_test_memory import read as far_read,write as far_write
from test_heap_concurrent import ownership


def registry(bridge,toolchain,output,optimize,bank=1,capacity=4):
    output.mkdir(parents=True,exist_ok=True)
    ports=[0x8fffd,0x8f001,0x9f001,0x9f041,0x9f081,0x9f0c1,0x9f101,0x9f141]
    priorities=[0,127,-128,-1,127,1,0,-128]
    long_names=(bank,capacity) in ((1,8),(3,4))
    last=b'x'*255+b'end' if long_names else b'gamma'
    names=[b'',b'alpha',b'alphabet',b'beta',b'alpha',b'ALPHA',None,last]
    queries=[b'',b'alpha',b'ALPHA',b'Alpha',b'alp',b'alphabet',b'beta',last,b'missing']
    if long_names:queries.append(b'x'*255+b'enD')
    query_addresses=[0xa0000+(i<<9) for i in range(len(queries))]
    name_addresses=[0xa9000+(i<<9) for i in range(8)]
    name_addresses[3]=0xcfffe
    if long_names:name_addresses[7]=0xbff80
    regions=[]
    for i,(p,pri,name) in enumerate(zip(ports,priorities,names)):
        record=bytearray([0xa5]*27)
        record[7]=pri&255;record[8:11]=(name_addresses[i] if name is not None else 0).to_bytes(3,'little')
        record[11]=2;record[12]=255;record[13:16]=b'\xff'*3
        regions.append((p-1,b'\xa5'+bytes(record)+b'\xa5'))
        if name is not None:regions.append((name_addresses[i],name+b'\0'))
    regions.extend((a,q+b'\0') for a,q in zip(query_addresses,queries))
    (output/'registry-data.inc').write_text('ADDRESS ARRAY addresses=['+' '.join(f'${a:x}' for a in ports)+']\n'+
        'ADDRESS ARRAY queries=['+' '.join(f'${a:x}' for a in query_addresses)+']\n')
    source=output/'ports_registry.act'
    fixture='ports_registry_long.act' if long_names else 'ports_registry.act'
    source.write_text((ROOT/'tests/programs'/fixture).read_text())
    program=build(toolchain,source,output,optimize=optimize,tasks=True,kernel_bank=bank,task_capacity=capacity,image_data=regions)
    memory=program['build']['memory'];storage=memory['ports_storage'];base=storage['BASE']
    require(storage==dict(BASE=(bank<<16)+(0x240 if capacity==8 else 0x200),BYTES=16,ACTIVE_BYTES=11),'Unexpected registry prefix')
    require(memory['profile']['code_origin']==base+16,'Code origin does not exclude registry')
    # Placement validation excludes reserved prefix bytes from every image span.
    for s in program['image']['segments']:
        require(s['address']+len(s['bytes'])<=base or s['address']>=base+16,'Image overlaps registry')
    expected_order=sorted(range(8),key=lambda i:-priorities[i])
    expected_found=[0 if q not in names else ports[next(i for i in expected_order if names[i]==q)] for q in queries]
    boots=[]
    for launch in range(2):
        runtime,_=execute(bridge,program,before_run=lambda b:far_write(b,base,b'\xa5'*16,output),timeout=240,frame_limit=12000,timer_irq=True)
        require(data(bridge,program['image'],'checks',True)==[1],'Registry fixture incomplete')
        observed={}
        for key,expected in [('found',expected_found),('order',[ports[i] for i in expected_order]),('after',[ports[4],ports[4],ports[1]])]:
            raw=bytes(data(bridge,program['image'],key));values=[int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]
            require(values==expected,f'Registry {key}: {values}');observed[key]=values
        empty=(base+3).to_bytes(3,'little')+bytes(3)+base.to_bytes(3,'little')+bytes(2)
        require(far_read(bridge,base,16,output)==empty+b'\xa5'*5,'Registry init/drain/padding failed')
        for p in ports:
            require(far_read(bridge,p-1,1,output)==b'\xa5' and far_read(bridge,p+27,1,output)==b'\xa5','Port guard changed')
        ownership(bridge,program)
        boots.append(dict(runtime=runtime,observed=observed))
    return dict(build=program['build'],boots=boots,kernel_bank=bank,task_capacity=capacity,registry_storage=storage,
                priorities=priorities,names=[n.decode() if n is not None else None for n in names],
                restarts=1,initial_registry='Poisoned before each launch; reset without walking old links')


def peer(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/ports_registry_peer.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=360,frame_limit=12000,timer_irq=True)
    require(data(bridge,program['image'],'checks',True)==[1],'Named rendezvous incomplete')
    counters={name:data(bridge,program['image'],name,True)[0] for name in ('misses','received')}
    require(counters['received']==8 and counters['misses']>=7,'Missing removal/discovery interleavings')
    require(runtime['created']==1 and runtime['native_irq_count']>0 and runtime['vbi_dispatches']>0,'Missing peer/IRQ/VBI activity')
    ownership(bridge,program)
    return dict(build=program['build'],runtime=runtime,counters=counters)
