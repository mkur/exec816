"""Concurrent port lifetimes on eight admitted native tasks."""
from native_program import ROOT,build,execute,require
from test_cooperative import data
from test_heap_concurrent import ownership


def capacity(bridge,toolchain,output,optimize,bank):
    program=build(toolchain,ROOT/'tests/programs/ports_capacity.act',output,optimize=optimize,
                  tasks=True,task_capacity=8,kernel_bank=bank)
    try:
        runtime,_=execute(bridge,program,timeout=600,frame_limit=24000,timer_irq=True)
    except Exception:
        # Keep only fixture state, never bridge credentials or raw logs.
        import json
        facts={n:data(bridge,program['image'],n) for n in
               ('go','ready','progress','seen','delivered','retained','workers')}
        (output/'failure-state.json').write_text(json.dumps(facts,indent=2)+'\n')
        raise
    facts={n:data(bridge,program['image'],n,True)[0] for n in
           ('checks','delivered','retained','peakTasks','portCount')}
    require(facts==dict(checks=1,delivered=56,retained=7,peakTasks=8,portCount=17),'Capacity facts: '+str(facts))
    require(data(bridge,program['image'],'seen')==[1]*56,'Missing/duplicate reply')
    require(data(bridge,program['image'],'progress')==[2]*7,'Missing retained-message cleanup')
    require(runtime['created']==7 and runtime['native_irq_count']>0 and runtime['vbi_dispatches']>0,'Missing eight-task IRQ/VBI activity')
    ownership(bridge,program)
    return dict(build=program['build'],runtime=runtime,facts=facts,kernel_bank=bank,task_capacity=8,
                barrier='All seven workers allocated ports/messages and remained live before go',
                handoff='Seven heap messages drained and freed only after their allocating tasks exited')


def wait_removal(bridge,toolchain,output,optimize):
    program=build(toolchain,ROOT/'tests/programs/ports_wait_remove.act',output,optimize=optimize,tasks=True)
    runtime,_=execute(bridge,program,timeout=240,frame_limit=12000,timer_irq=True)
    require(data(bridge,program['image'],'checks',True)==[1] and
            data(bridge,program['image'],'resumed')==[0],'Removed WaitPort continuation resumed')
    require(runtime['created']==1,'Missing waiting task')
    ownership(bridge,program)
    return dict(build=program['build'],runtime=runtime,
                quiescence='No producers, queued messages or outstanding requests; manual port reused only after removal')
