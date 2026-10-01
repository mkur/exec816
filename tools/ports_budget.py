"""Complete bank-zero reservation accounting for port qualification."""
import json
from generate_memory import ROOT,layout
from generate_heap import reserve_metadata
from generate_tasks import validate_memory
from task_capacity import configure


def account(memory):
    os_bytes=sum(b-a for name,(a,b) in memory['regions'].items() if name.startswith('os-'))
    if 'bank_zero_budget' in memory:
        return dict(memory['bank_zero_budget'])
    excluded={'task0-dp','task1-dp','task0-stack','task1-stack','loader','staging','manifest'}
    regions=memory['regions']
    # The full table arena and retained legacy context arena are reserved even
    # when their active fields are smaller. See the current capacity contract.
    slack=1024-memory['constants']['TABLE_BYTES'];extra=slack+240
    fixed=sum(b-a for name,(a,b) in regions.items() if not name.startswith('os-') and name not in excluded)+extra
    pools=[p.get('dp_reserved_bytes',288)+p.get('stack_bytes',1536)+32 for p in memory['task_pools']]
    loading=sum(b-a for name,(a,b) in regions.items() if not name.startswith('os-'))+extra
    runtime=fixed+sum(pools)
    return dict(fixed_runtime=fixed,public=pools[:-1],idle=pools[-1],runtime_excluding_os=runtime,
                runtime_including_os=runtime+os_bytes,loading_excluding_os=loading,loading_including_os=loading+os_bytes)


def current():
    observed={}
    for capacity,key in [(4,'four'),(8,'eight')]:
        memory=layout(upper_table=capacity==8)
        if capacity==8:configure(memory,8,1024,512)
        reserve_metadata(memory)
        from generate_ports import reserve_metadata as reserve_ports
        reserve_ports(memory);validate_memory(memory)
        observed[key]=account(memory)
    before=json.loads((ROOT/'docs/qualification/memory-exec-api.json').read_text())['bank_zero']['after']
    return dict(before=before,after=observed,fixed_delta=observed['eight']['runtime_including_os']-before['eight']['runtime_including_os'],per_task_delta=0,diagnostic_delta=0,
                accounting='Generated maps; full guards, table slack, retained legacy contexts and VBXE aperture; unchanged pool sizes.')


def historical():
    """Frozen geometry for validators of retained qualification records."""
    return json.loads((ROOT/'docs/qualification/memory-exec-api.json').read_text())['bank_zero']['after']
