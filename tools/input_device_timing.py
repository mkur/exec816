"""Passive native input Task accounting; no guest instructions are inserted."""
import os
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, flat_markers
from latency_statistics import distribution
from native_program import require
from sio_transaction_trace import BASE_HZ, read_events


def setup(program):
    spans=native_markers(program,[('INPUTDRIVER_DRAIN','drain'),
        ('INPUTDRIVER_CONTROL','control'),('INPUTDRIVER_DISPATCH','dispatch'),
        ('CONSOLEINPUT_DELIVER','key'),('DESKINPUT_CAPTUREPOINTER','pointer'),
        ('AESINBOX_PUBLISHENDPOINT','inbox')])
    labels=program['labels']
    address=labels['context_restore']
    import adapter_state as adapter
    hosted=(program['output']/'hosted.bin').read_bytes()
    require(hosted[address-adapter.RESIDENT_BASE:address-adapter.RESIDENT_BASE+8]
        ==bytes.fromhex('c230ab2b7afa6840'),'Unrecognized context restore sequence')
    definition=dict(spans=spans,points=dict(turn=spans['drain']['entry'],selected=address+4,
        **{k:labels[k] for k in ('native_irq','native_nmi','interrupt_schedule')}),
        task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])
    points=flat_markers(definition)
    for name in ('input_notify','pointer_notify'):points[name]=labels[name]
    saved={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1',
        EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in set(points.values())))
    return definition,saved


def restore(config):
    for key,value in config[1].items():
        if value is None:os.environ.pop(key,None)
        else:os.environ[key]=value


def result(out,program,config,idle):
    definition=config[0];events=read_events(out/'emulator.log')
    profile=analyze_events(events,definition,include_segments=True)
    spans=profile['routine_spans']
    costs={kind:{metric:distribution([s[metric] for s in spans if s['kind']==kind])
        for metric in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')}
        for kind in ('control','key','pointer')}
    notifications={kind:[t for t,e in events if e[0]=='cpu'
        and int(e[4],16)==program['labels'][label]]
        for kind,label in (('key','input_notify'),('pointer','pointer_notify'))}
    delays=[]
    for span in spans:
        kind=span['kind']
        if kind not in notifications:continue
        pending=[t for t in notifications[kind] if t<=span['start']]
        if not pending:continue
        notified=pending[-1]
        published=[s for s in spans if s['kind']=='inbox'
            and span['start']<=s['start']<s['end']<=span['end']]
        delays.append(dict(kind=kind,notification_to_handler_ms=(span['start']-notified)/BASE_HZ*1000,
            notification_to_inbox_ms=(published[0]['end']-notified)/BASE_HZ*1000 if published else None))
    idle_start=idle[0]+round((events[0][0]-idle[0])/(1<<32))*(1<<32)
    idle_end=idle_start+((idle[1]-idle[0])%(1<<32))
    require(events[0][0]<=idle_start<idle_end<=events[-1][0],
        'Idle interval is outside the native trace')
    idle_drains=sum(e[0]=='cpu' and int(e[4],16)==definition['points']['turn']
        and idle_start<=t<=idle_end for t,e in events)
    require(idle_drains==0,'Input Task woke without source/control work during idle')
    return dict(callbacks_and_control=costs,delivery=delays,
        idle=dict(start=idle_start,end=idle_end,duration_ms=(idle_end-idle_start)/BASE_HZ*1000,device_drain_turns=idle_drains),
        scope='Native publication/notification to copied-handler/inbox return in the controlled Counter case. Pointer samples can coalesce: their delay starts at the latest preceding notification, not the oldest physical movement. Charged CPU, interrupts and off-Task time are separate; nested spans must not be added. This does not measure key-to-paint latency or establish a scroll improvement.')
