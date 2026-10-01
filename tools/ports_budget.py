"""Complete bank-zero reservation accounting for port qualification."""
import json
from generate_memory import ROOT,layout
from generate_heap import reserve_metadata
from generate_tasks import validate_memory
from task_capacity import configure


def account(memory):
    validate_memory(memory)
    return dict(memory['bank_zero_budget'])


def current():
    observed={}
    for capacity,key in [(4,'four'),(8,'eight')]:
        memory=layout(upper_table=capacity==8)
        if capacity==8:configure(memory,8)
        reserve_metadata(memory)
        from generate_ports import reserve_metadata as reserve_ports
        reserve_ports(memory);validate_memory(memory)
        observed[key]=account(memory)
    before=json.loads((ROOT/'docs/qualification/memory-exec-api.json').read_text())['bank_zero']['after']
    old,new = before['eight'],observed['eight']
    fixed = lambda b:b['runtime_including_os']-sum(b['public'])-b['idle']
    return dict(before=before,after=observed,fixed_delta=fixed(new)-fixed(old),
                per_public_task_delta=[a-b for a,b in zip(new['public'],old['public'])],idle_delta=new['idle']-old['idle'],
                diagnostic_delta=0,
                accounting='Generated maps; stack guards, full bank-table capacity and VBXE aperture; exact 256-byte direct pages.')



def historical():
    """Frozen geometry for validators of retained qualification records."""
    return json.loads((ROOT/'docs/qualification/memory-exec-api.json').read_text())['bank_zero']['after']
