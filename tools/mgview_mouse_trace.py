"""Passive M_OFF/M_ON policy, device and completion costs on frozen MGVIEW."""
from bitmap_console_performance import native_markers
from console_turn_profile import Timeline,analyze_events
from g4bench_trace import calls
from mgview_pre_copy_trace import summarize
from native_program import require
from sio_transaction_trace import read_events


PREFIXES=('AESLOCAL_','AESCURSOR_','AESMOUSE_','AESSNAPSHOT_','AESSTATE_',
          'AESWAIT_','CALYPSICALL_')
GROUPS={
    'binding':'graf_mouse ExecAESMouseForm ExecAESMouseControl ExecAESEnter',
    'context_lookup':'ExecAESContext',
    'dispatch':'ExecAESLocal _AESLocalCall AESLOCAL_CALL',
    'cursor_policy':'AESCURSOR_CALL AESCURSOR_SETDEPTH AESCURSOR_INSTALL AESCURSOR_TRANSITION',
    'recipient_selection':'AESCURSOR_SELECT AESMOUSE_CURSORRECIPIENT AESSNAPSHOT_SELECT AESSNAPSHOT_DROP',
    'completion_and_wake':'AESCURSOR_WAKE AESCURSOR_PENDING AESWAIT_SIGNAL',
    'device_apply':'ExecAESMouseApply',
    'display_admission':'GemDrawingMouseBorrow DisplayEnter DisplayLeave',
    'device_target':'draw_Mouse',
    'target_copy':'memcpy memcmp',
    'cursor_render':'cursor_render cursor_hide cursor_record',
    'queue':'flush drain fence_owner',
    'submission':'VbxeOwnerSubmit submit',
    'upload':'_VbxeUpload',
    'fence':'VbxeOwnerFence',
    'coordination':'Forbid Permit Signal Wait tasks_forbid tasks_permit tasks_signal tasks_wait',
}


def definition(program,foreign):
    names=[r['name'].rsplit('_',1)[0][2:] for r in program['image']['routines']
           if r['name'].startswith('M_') and r['name'][2:].startswith(PREFIXES)]
    native=native_markers(program,[(n,n) for n in names])
    entries={v['entry']:n for n,v in native.items()}
    exits={pc for v in native.values() for pc in v['returns']}
    for name in {n for names in GROUPS.values() for n in names.split()}:
        if name in foreign['symbols']:entries[foreign['symbols'][name]]=name
        elif name.startswith('tasks_'):
            entries[program['labels'][name]]=name
            exits.add(program['labels'][name+'_end']-1)
        else:require(name in entries.values(),'Missing mouse observation: '+name)
    return dict(entries=entries,exits=sorted(exits),pcs=sorted(set(entries)|exits))


def stages(rows,timeline,start,end):
    def one(name):
        selected=[r for r in rows if r['kind']==name and start<=r['start']<r['end']<=end]
        require(len(selected)==1,'Expected one mouse stage: '+name)
        return selected[0]
    policy=one('AESCURSOR_CALL');apply=one('ExecAESMouseApply')
    require(start<=policy['start']<policy['end']<=apply['start']<apply['end']<=end,
            'Mouse stages overlap')
    bounds=(('binding_and_dispatch',start,policy['start']),
        ('cursor_policy',policy['start'],policy['end']),
        ('policy_to_device',policy['end'],apply['start']),
        ('device_apply',apply['start'],apply['end']),
        ('completion_and_return',apply['end'],end))
    result=[dict(kind=name,start=left,end=right,**timeline.measure(left,right))
            for name,left,right in bounds]
    for key,value in timeline.measure(start,end).items():
        require(abs(sum(r[key] for r in result)-value)<1e-6,'Mouse stages do not reconcile: '+key)
    return result


def analyze(out,definition,audit):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={definition['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,definition['timeline'],include_segments=True)
    dp=audit['samples'][0]['viewer_dp'];timeline=Timeline(profile['segments'],dp)
    selected=definition['mouse']
    entries={**definition['entries'],**selected['entries']}
    exits=set(definition['exits'])|set(selected['exits'])
    rows,unfinished=calls(events,entries,set(definition['returns']),dp,exits)
    kinds={n:group for group,names in GROUPS.items() for n in names.split()}
    for name in entries.values():
        if name.startswith('AESSTATE_'):kinds[name]='registration_lookup'
    samples=[]
    for sample in audit['samples']:
        shift=next(r for r in sample['spans'] if r['kind']=='set_shift')
        copy=next(r for r in sample['spans'] if r['kind']=='vro_cpyfm')
        mouse=sorted((r for r in rows if r['kind']=='graf_mouse' and
                      shift['start']<=r['start']<r['end']<=shift['end']),key=lambda r:r['start'])
        require(len(mouse)==2 and mouse[0]['end']<=copy['start']<copy['end']<=mouse[1]['start'],
                'Expected mouse hide before copy and show after painting')
        for mode,call in zip(('M_OFF','M_ON'),mouse):
            start,end=call['start'],call['end']
            report=summarize(rows,timeline,start,end,kinds)
            require(not any(start<=r['start']<end for r in unfinished),'Unfinished measured mouse call')
            report.update(action=sample['action'],mode=mode,return_a=call['return_a'],
                stages=stages(rows,timeline,start,end),
                submission_records=[r['argument'] for r in report['spans'] if r['kind']=='VbxeOwnerSubmit'])
            samples.append(report)
    return dict(samples=samples,scope='Mouse caller stages are disjoint. Innermost selected routines partition Task CPU; inclusive costs overlap. Native interrupts and other Tasks are separate. No guest instrumentation or rebuild.')
