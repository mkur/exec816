"""Resolve compact DP ownership and fixed guarded stacks from the platform map."""
from os_boundary import require
from adapter_state import direct_pages
from generate_memory import reservation_maps


def configure(memory, capacity, worker_stack=None, idle_stack=None):
    require(type(capacity) is int and 2 <= capacity <= 16, 'Task capacity must be 2..16')
    profile = memory['profile']
    require(str(capacity) in profile['task_stacks'], 'No supported stack map for Task capacity')
    spec = profile['task_stacks'][str(capacity)]
    require(len(spec['bases']) == len(spec['sizes']) == capacity+1, 'Invalid stack map')
    for value in (worker_stack, idle_stack):
        require(value is None or type(value) is int and 512 <= value <= 1536 and value % 16 == 0,
                'Stack reservation must be 512..1536 bytes, aligned to 16')
    require(capacity == 4 or memory['constants']['TABLE'] >= 65536,
            'Capacity profile requires an upper bank table')
    dp = direct_pages(profile)
    regions = memory['regions']
    require(regions['kernel-dp'] == [dp['KERNEL_DP'],dp['KERNEL_DP']+256],
            'Kernel direct page differs from its reservation')
    excluded = {'table','task0-dp','task1-dp','task0-stack','task1-stack','loader','staging'}
    fixed = [(a,b,name) for name,(a,b) in regions.items() if name not in excluded]
    if memory['constants']['TABLE'] < 65536:
        table = next(r for r in profile['regions'] if r['name'] == 'table')
        fixed.append((table['address'],table['address']+table['size'],'table'))
    fixed.sort()
    require(all(a[1] <= b[0] for a,b in zip(fixed,fixed[1:])), 'Fixed reservation overlaps')
    used = list(fixed)

    def reserve(start, size, name):
        end = start+size
        require(regions['state'][1] <= start < end <= 0x9000 and
                all(end <= a or start >= b for a,b,_ in used),
                'Task pool overlaps reserved memory: '+name)
        used.append((start,end,name))

    pools = []
    for i,(base,size) in enumerate(zip(spec['bases'],spec['sizes'])):
        if i == capacity and idle_stack is not None:
            size = idle_stack
        elif 0 < i < capacity and worker_stack is not None:
            size = worker_stack
        require(type(base) is int and base % 16 == 0 and type(size) is int and
                512 <= size <= 1536 and size % 16 == 0, 'Invalid stack map entry')
        if i < 2:
            require(base == regions[f'task{i}-stack'][0]+16,
                    'Bootstrap stack differs from its reservation')
        page = dp['TASK0_DP']+i*profile['direct_pages']['task_stride']
        reserve(page,256,f'dp{i}')
        reserve(base-16,size+32,f'stack{i}')
        pools.append(dict(dp=page,dp_reserved_bytes=256,stack_base=base,
                          stack_bytes=size,interrupt_reserve=256))
    for i in (0,1):
        p = pools[i]
        regions[f'task{i}-dp'] = [p['dp'],p['dp']+256]
        regions[f'task{i}-stack'] = [p['stack_base']-16,p['stack_base']+p['stack_bytes']+16]
    # The profile retains full table capacity; regions describes active fields.
    for r in profile['regions']:
        if r['name'].startswith(('task0-','task1-')):
            a,b = regions[r['name']]
            r.update(address=a,size=b-a)
    memory['task_pools'] = pools
    memory['task_capacity'] = capacity
    memory['reclaimed_after_adopt'] = ['loader','staging']
    encode = lambda spans:[dict(name=n,address=a,size=b-a) for a,b,n in spans]
    bootstrap = fixed+[(p['dp'],p['dp']+256,f'dp{i}') for i,p in enumerate(pools[:2])]
    bootstrap += [(p['stack_base']-16,p['stack_base']+p['stack_bytes']+16,f'stack{i}')
                  for i,p in enumerate(pools[:2])]
    bootstrap += [(*regions[n],n) for n in ('loader','staging')]
    reservation_maps(memory,encode(bootstrap),encode(used),
                     encode([(a,b,n) for a,b,n in used if n != 'manifest']))
    fixed_bytes = sum(b-a for a,b,n in fixed if not n.startswith('os-') and n != 'manifest')
    public = [p['dp_reserved_bytes']+p['stack_bytes']+32 for p in pools[:-1]]
    idle = pools[-1]['dp_reserved_bytes']+pools[-1]['stack_bytes']+32
    loading = fixed_bytes+sum(public[:2])+sum(regions[n][1]-regions[n][0]
                                              for n in ('manifest','loader','staging'))
    os_bytes = sum(b-a for name,(a,b) in regions.items() if name.startswith('os-'))
    memory['bank_zero_budget'] = dict(fixed_runtime=fixed_bytes,public=public,idle=idle,
        runtime_excluding_os=fixed_bytes+sum(public)+idle,loading_excluding_os=loading,
        runtime_including_os=fixed_bytes+sum(public)+idle+os_bytes,loading_including_os=loading+os_bytes)
    require(sum(r['size'] for r in memory['phase_reservations']['loading']) == loading+os_bytes,
            'Loading ownership differs from budget')
    return pools
