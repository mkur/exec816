"""Focused existing-kernel checks after adding DOS task lifecycle hooks."""
from native_program import ROOT,build,execute,require
from test_cooperative import data

def run(b,t,out,optimize,name):
    if name=='heap':
        from test_heap_api import basic
        return basic(b,t,out,optimize)
    if name=='ports':
        from test_ports_lifetime import lifetime
        return lifetime(b,t,out,optimize)
    if name=='io':
        from test_io_services import run_case
        return run_case(b,t,out,optimize,'queues')
    if name=='signals':
        from test_signals import check_masks
        p=build(t,ROOT/'tests/programs/signals_masks.act',out,tasks=True,optimize=optimize)
        runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        return dict(build=p['build'],runtime=runtime,observed=check_masks(b,p,runtime))
    if name=='tasks':
        from test_tasks_exec import check
        p=build(t,ROOT/'tests/programs/tasks_exec_reuse.act',out,tasks=True,optimize=optimize)
        runtime,_=execute(b,p,timeout=600,frame_limit=30000)
        return dict(build=p['build'],runtime=runtime,observed=check(b,p,'reuse',runtime))
    raise ValueError(name)
