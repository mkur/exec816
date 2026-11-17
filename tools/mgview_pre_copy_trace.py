"""Passive pre-copy attribution on the frozen MGVIEW executable.

Observe linked routine boundaries only. Arithmetic wrappers belong to the
relocated APP; AES bindings and native routines retain their linked addresses.
"""
from collections import defaultdict

from bitmap_console_performance import native_markers
from c_program import ABI
from console_turn_profile import Timeline,analyze_events
from g4bench_trace import calls
from mgview_end_trace import charged_peers
from mgview_frame_trace import GROUPS as FRAME_GROUPS,partition
from mgview_slider_trace import GROUPS as SLIDER_GROUPS
from native_program import require
from sio_transaction_trace import read_events


APP=('_Mul32','_Div32','_Div16')
SOURCE_CALLS=('wind_update','wind_set','graf_mouse','wind_get','vs_clip',
              '_Mul32','_Div32','rc_intersect')
PREFIXES=('AESLOCAL_','AESLOCKS_','AESWINDOW_','AESWINDOWSTATE_',
          'AESSNAPSHOT_','GEMFRAME_','DESKGEOMETRY_','DESKCACHE_',
          'DESKMENU_','DESKPAINT_','LAYERS_','REGIONS_','CONSOLEBITMAP_')
C_NAMES=('wind_set','wind_get','graf_mouse','ExecAESContext','ExecAESFindView',
         'ExecAESWindowCall','ExecAESWindowGet','ExecAESLocal','_AESLocalCall')
KERNEL=('tasks_find_task','tasks_forbid','tasks_permit')
GROUPS={
    'app_arithmetic':' '.join(APP),
    'binding':'wind_set wind_get graf_mouse ExecAESWindowCall ExecAESWindowGet',
    'context_lookup':'ExecAESContext',
    'window_lookup':'ExecAESFindView AESWINDOWSTATE_HANDLE AESWINDOWSTATE_FINDRECORD',
    'dispatch':'ExecAESLocal _AESLocalCall AESLOCAL_CALL AESLOCAL_POLICY',
    'publication':'AESLOCAL_PUBLISH',
    'exposure':'AESLOCAL_EXPOSURE',
    'update_scope':'AESLOCAL_SCOPE',
    'window_view':'AESWINDOWSTATE_SLIDERS AESWINDOWSTATE_UPDATES',
    'native_frame':'AESFRAME_PAINT',
    'kernel_coordination':' '.join(KERNEL),
}


def definition(program,foreign):
    names=[r['name'].rsplit('_',1)[0][2:] for r in program['image']['routines']
           if r['name'].startswith('M_') and r['name'][2:].startswith(PREFIXES)]
    native=native_markers(program,[(n,n) for n in names])
    entries={v['entry']:n for n,v in native.items()}
    exits={pc for v in native.values() for pc in v['returns']}
    for name in C_NAMES:
        require(name in foreign['symbols'],'Missing pre-copy binding: '+name)
        entries[foreign['symbols'][name]]=name
    for name in KERNEL:
        entries[program['labels'][name]]=name
        exits.add(program['labels'][name+'_end']-1)
    return dict(entries=entries,exits=sorted(exits),pcs=sorted(set(entries)|exits))


def groups(entries):
    kinds={}
    prefixes={'AESLOCKS_':'update_scope','AESWINDOW_':'native_mutation',
        'AESWINDOWSTATE_':'window_view','AESSNAPSHOT_':'input_snapshot',
        'GEMFRAME_':'thumb_geometry','DESKGEOMETRY_':'object_geometry',
        'DESKCACHE_':'cache_metadata','DESKMENU_':'menu_reconcile',
        'DESKPAINT_':'exposure_paint','LAYERS_':'layers','REGIONS_':'regions',
        'CONSOLEBITMAP_':'bitmap_packet'}
    for name in entries.values():
        for prefix,group in prefixes.items():
            if name.startswith(prefix):kinds[name]=group;break
    for group,names in {**SLIDER_GROUPS,**FRAME_GROUPS,**GROUPS}.items():
        for name in names.split():kinds[name]=group
    return kinds


def summarize(rows,timeline,start,end,kinds):
    contained=[dict(r,**timeline.measure(r['start'],r['end'])) for r in rows
               if start<=r['start']<r['end']<=end]
    routines=defaultdict(list)
    for row in contained:routines[row['kind']].append(row)
    return dict(start=start,end=end,measured=timeline.measure(start,end),
        exclusive_cpu_ms=partition(contained,timeline,start,end,kinds),
        routines={name:dict(calls=len(spans),**{key:sum(r[key] for r in spans)
            for key in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')})
            for name,spans in routines.items()},spans=contained)


def stages(rows,timeline,start,end):
    """Disjoint caller intervals, with arithmetic inside the slider explicit."""
    selected=[r for r in rows if start<=r['start']<r['end']<=end]
    slider=[r for r in selected if r['kind']=='window_calc_slider']
    require(len(slider)==1,'Expected one slider helper before the copy')
    helper=slider[0]
    setters=sorted((r for r in selected if r['kind']=='wind_set'),key=lambda r:r['start'])
    require(len(setters)==2 and all(helper['start']<=r['start']<r['end']<=helper['end']
                                  for r in setters),'Expected two slider setters')
    labels=[('before_slider',start,helper['start']),
        ('slider_size_preparation',helper['start'],setters[0]['start']),
        ('WF_VSLSIZE',setters[0]['start'],setters[0]['end']),
        ('slider_position_preparation',setters[0]['end'],setters[1]['start']),
        ('WF_VSLIDE',setters[1]['start'],setters[1]['end']),
        ('slider_return',setters[1]['end'],helper['end']),
        ('after_slider_before_copy',helper['end'],end)]
    result=[dict(kind=name,start=left,end=right,**timeline.measure(left,right))
            for name,left,right in labels]
    for key,value in timeline.measure(start,end).items():
        require(abs(sum(r[key] for r in result)-value)<1e-6,
                'Pre-copy caller stages do not reconcile: '+key)
    return result


def source_calls(events,sites,delta,dp):
    """Match APP call sites across interrupts using the caller's full S/D.

    The observation is before JSL, so the successor has the same S (rather
    than the three-byte difference used for callee-entry observations).
    """
    entries={int(pc)+delta:name.rsplit('/',1)[0] for pc,name in sites.items()
             if name.endswith('/call')}
    active={};rows=[]
    for tick,event in events:
        if int(event[9],16)!=dp:continue
        pc,stack=int(event[4],16),int(event[8],16)
        if (pc,stack) in active:
            rows.append(dict(active.pop((pc,stack)),end=tick))
        if pc in entries:
            key=(pc+4,stack)
            require(key not in active,'Repeated APP call without its successor: '+
                    str((key,active.get(key),entries[pc],tick)))
            active[key]=dict(kind=entries[pc],start=tick)
    return rows,list(active.values())


def analyze(out,definition,audit,loaded_base):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={definition['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,definition['timeline'],include_segments=True)
    dp=audit['samples'][0]['viewer_dp'];timeline=Timeline(profile['segments'],dp)
    roles={dp:'MGVIEW',profile['worker_dp']:'SCRENMGR',
           definition['timeline']['task_dps'][0]:'test controller'}
    delta=loaded_base-(ABI['link_bank']<<16)
    entries={**definition['entries'],**definition['slider']['entries'],
             **definition['pre_copy']['entries'],
             **{int(pc)+delta:name for pc,name in definition['app_entries'].items()}}
    returns=set(definition['returns'])|{pc+delta for pc in definition['app_returns']}
    exits=set(definition['exits'])|set(definition['slider']['exits'])|\
          set(definition['pre_copy']['exits'])|{pc+delta for pc in definition['app_exits']}
    rows,unfinished=calls(events,entries,returns,dp,exits)
    # Observe ordinary returning bindings/arithmetic. Other runtime helpers
    # consume inline operands or their return address; vro_cpyfm crosses the
    # end of the measured interval.
    sites={pc:name for pc,name in definition['sites'].items()
           if name.startswith(('set_shift/','window_calc_slider/'))
           and name.split('/')[1] in SOURCE_CALLS}
    caller_rows,caller_unfinished=source_calls(events,sites,delta,dp)
    kinds=groups(entries);samples=[]
    for sample in audit['samples']:
        shift=next(r for r in sample['spans'] if r['kind']=='set_shift')
        copy=next(r for r in sample['spans'] if r['kind']=='vro_cpyfm')
        start,end=shift['start'],copy['start']
        result=summarize(rows,timeline,start,end,kinds)
        result.update(action=sample['action'],stages=stages(rows,timeline,start,end))
        result['peers']=charged_peers(profile['segments'],start,end,dp,roles)
        require(abs(sum(p['charged_cpu_ms']+p['interrupt_ms'] for p in result['peers'])-
                    result['measured']['off_cpu_ms'])<1e-6,'Pre-copy peer accounting does not reconcile')
        result['caller_calls']=[dict(r,**timeline.measure(r['start'],r['end']))
            for r in caller_rows if start<=r['start']<r['end']<=end]
        result['setters']=[dict(field=r['kind'],**summarize(rows,timeline,r['start'],r['end'],kinds))
                           for r in result['stages'] if r['kind'] in ('WF_VSLSIZE','WF_VSLIDE')]
        samples.append(result)
    require(not any(any(s['start']<=r['start']<s['end'] for s in samples) for r in unfinished),
            'Unfinished measured pre-copy call')
    require(not any(any(s['start']<=r['start']<s['end'] for s in samples)
                    for r in caller_unfinished),'Unfinished measured APP call')
    return dict(samples=samples,unfinished_calls=unfinished,
        scope='Caller stages are disjoint; innermost selected routine partitions Task CPU. Inclusive routine costs overlap. Other Tasks and native interrupts are separate. No guest code or build changes.')
