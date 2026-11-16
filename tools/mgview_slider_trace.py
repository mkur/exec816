"""Passive caller-side slider costs on the existing MGVIEW/Counter fixture."""
from collections import Counter, defaultdict

from bitmap_console_performance import native_markers
from console_turn_profile import Timeline, analyze_events
from g4bench_trace import calls
from sio_transaction_trace import read_events


GROUPS = {
    'scope': 'AESLOCKS_CALL',
    'mutation': 'AESWINDOW_FRAME',
    'thumb_geometry': 'AESWINDOWSTATE_GEOMETRY DESKGEOMETRY_SLIDER DESKGEOMETRY_HSLIDER',
    'window_view': 'AESWINDOWSTATE_PUBLISH AESWINDOWSTATE_SYNC',
    'damage': 'LAYERS_INVALIDATE LAYERS_REPAIRED',
    'publication': 'AESLOCAL_PUBLISH',
    'input_snapshot': 'AESSNAPSHOT_PUBLISH',
    'native_frame': 'AESFRAME_PAINT',
    'renderer': 'ExecAESFrameApply DesktopFrameBorrow GemDrawingFrameBorrow',
    'fills': 'GemWidgetFill',
    'gadgets': 'GemFrameGadget',
    'submission': 'VbxeOwnerSubmit',
    'fence': 'VbxeOwnerFence',
    'display_access': 'DisplayEnter DisplayLeave',
}


def definition(program, foreign):
    names={name for group in GROUPS.values() for name in group.split()}
    native=native_markers(program,[(n,n) for n in names if n.isupper()])
    entries={value['entry']:name for name,value in native.items()}
    entries.update({foreign['symbols'][n]:n for n in names if n in foreign['symbols']})
    exits=sorted({pc for value in native.values() for pc in value['returns']})
    return dict(entries=entries,exits=exits,pcs=sorted(set(entries)|set(exits)))


def analyze(out, definition, audit):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={definition['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,definition['timeline'],include_segments=True)
    selected=definition['slider']
    dp=audit['samples'][0]['viewer_dp']
    timeline=Timeline(profile['segments'],dp)
    spans,unfinished=calls(events,selected['entries'],set(definition['returns']),dp,
        set(definition['exits'])|set(selected['exits']))
    kinds={name:group for group,names in GROUPS.items() for name in names.split()}
    samples=[]
    for sample in audit['samples']:
        window=next(s for s in sample['spans'] if s['kind']=='window_calc_slider')
        start,end=window['start'],window['end']
        rows=[dict(s,**timeline.measure(s['start'],s['end'])) for s in spans
              if start<=s['start']<s['end']<=end]
        edges=defaultdict(list);edges[start];edges[end]
        for index,row in enumerate(rows):
            edges[row['start']].append((index,True))
            edges[row['end']].append((index,False))
        active=set();previous=start;exclusive=Counter()
        for tick,changes in sorted(edges.items()):
            inner=max(active,key=lambda i:rows[i]['start']) if active else None
            group=kinds[rows[inner]['kind']] if inner is not None else 'caller_other'
            exclusive[group]+=timeline.measure(previous,tick)['charged_cpu_ms']
            for index,entering in changes:
                if entering:active.add(index)
                else:active.remove(index)
            previous=tick
        measured=timeline.measure(start,end)
        if abs(sum(exclusive.values())-measured['charged_cpu_ms'])>=1e-6:
            raise RuntimeError('Slider phase accounting does not reconcile')
        routines={}
        for row in rows:
            total=routines.setdefault(row['kind'],dict(calls=0,elapsed_ms=0,charged_cpu_ms=0))
            total['calls']+=1
            for key in ('elapsed_ms','charged_cpu_ms'):total[key]+=row[key]
        samples.append(dict(action=sample['action'],measured=measured,
            exclusive_cpu_ms=dict(exclusive),routines=routines,spans=rows))
    return dict(samples=samples,unfinished_calls=unfinished,
        scope='Innermost selected routine owns each CPU interval; inclusive routine totals must not be added. Other Tasks and native interrupts are separate.')
