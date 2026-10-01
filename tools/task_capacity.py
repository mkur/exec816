"""Checked static native stack/DP pools; boot storage is reused after Adopt."""
from os_boundary import require


def configure(memory, capacity, worker_stack=1024, idle_stack=512):
    require(type(capacity) is int and 2 <= capacity <= 16, 'Task capacity must be 2..16')
    for value in (worker_stack,idle_stack):
        require(type(value) is int and 512 <= value <= 1536 and value % 16 == 0,
                'Stack reservation must be 512..1536 bytes, aligned to 16')
    require(memory['constants']['TABLE'] >= 65536, 'Capacity profile requires an upper bank table')
    regions=memory['regions']
    fixed=[(a,b,name) for name,(a,b) in regions.items()
           if name not in ('table','task0-dp','task1-dp','task0-stack','task1-stack','loader','staging')]
    used=list(fixed)
    pools=[]
    low=regions['state'][1]

    def reserve(start,size,name):
        end=start+size
        require(low <= start < end <= 0x9000 and
                all(end<=a or start>=b for a,b,_ in used), 'Task pool does not fit: '+name)
        used.append((start,end,name))

    def fit(size,alignment,offset,name):
        # Prefer the established pool arena, then use the reclaimed no-DOS
        # space below it, after boot staging. This also leaves room for the
        # eight-slot register probe's temporary $0900-$097f capture extension.
        # Both passes protect the aperture and still-live startup manifest.
        for floor,ceiling in ((0x2000,0x9000),(max(low,regions['staging'][1]),0x2000)):
            first=((floor+offset+alignment-1)//alignment)*alignment
            for address in range(first,ceiling,alignment):
                start=address-offset
                if start+size<=ceiling and all(start+size<=a or start>=b for a,b,_ in used):
                    reserve(start,size,name)
                    return address
        raise ValueError('No bank-zero space for '+name)

    # Root and the first worker retain adapter probe identities; every other
    # range is packed into checked runtime holes, including retired INITAD RAM.
    for i in range(capacity+1):
        size=1536 if i==0 else idle_stack if i==capacity else worker_stack
        pool=dict(stack_bytes=size,dp_reserved_bytes=512,interrupt_reserve=256)
        if i<2:
            pool.update(dp=(0x2200,0x2400)[i],stack_base=(0x4200,0x5200)[i])
            reserve(pool['dp']-16,512,f'dp{i}')
            reserve(pool['stack_base']-16,size+32,f'stack{i}')
        pools.append(pool)
    for i,pool in enumerate(pools[2:],2):
        # Aligned D requires padding. Reserve the complete 512-byte stride,
        # including both guards and unused space, instead of hiding its cost.
        pool['dp']=fit(512,256,16,f'dp{i}')
    for i,pool in enumerate(pools[2:],2):
        pool['stack_base']=fit(pool['stack_bytes']+32,16,16,f'stack{i}')
    for i in (0,1):
        p=pools[i]
        regions[f'task{i}-dp']=[p['dp']-16,p['dp']-16+p['dp_reserved_bytes']]
        regions[f'task{i}-stack']=[p['stack_base']-16,p['stack_base']+p['stack_bytes']+16]
    for r in memory['profile']['regions']:
        if r['name'] in regions:
            a,b=regions[r['name']];r.update(address=a,size=b-a)
    memory['task_pools']=pools
    memory['task_capacity']=capacity
    memory['reclaimed_after_adopt']=['loader','staging']
    memory['runtime_reservations']=[dict(name=n,address=a,size=b-a) for a,b,n in sorted(used) if n != 'manifest']
    fixed_bytes=sum(b-a for a,b,n in fixed if not n.startswith('os-') and n != 'manifest')
    public=[p['dp_reserved_bytes']+p['stack_bytes']+32 for p in pools[:-1]]
    idle=pools[-1]['dp_reserved_bytes']+pools[-1]['stack_bytes']+32
    loading=fixed_bytes+regions['manifest'][1]-regions['manifest'][0]+sum(public[:2])+sum(regions[n][1]-regions[n][0] for n in ('loader','staging'))
    os_bytes=sum(b-a for name,(a,b) in regions.items() if name.startswith('os-'))
    memory['bank_zero_budget']=dict(fixed_runtime=fixed_bytes,public=public,idle=idle,
        runtime_excluding_os=fixed_bytes+sum(public)+idle,loading_excluding_os=loading,
        runtime_including_os=fixed_bytes+sum(public)+idle+os_bytes,loading_including_os=loading+os_bytes)
    return pools
