"""Passive native admissions, including the opcode loads already in the guest."""
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict

from aes_latency_trace import routine
from generate_desktop import ABI, layout
from native_program import require


def markers(program):
    points = {}
    offset = layout()['Request']['fields']['operation']
    # SEP #$20; LDY #operation; LDA [pointer],Y. Observe A8 after the read,
    # including the busy-scene checks which can defer without calling Dispatch.
    needle = b'\xe2\x20\xa0'+offset.to_bytes(2, 'little')+b'\xb7\x80'
    for name in ('PUMP', 'DISPATCH'):
        base, raw = routine(program, 'DESKCORE_'+name)
        loads = [m.end() for m in re.finditer(re.escape(needle), raw)]
        require(loads, 'Missing native operation loads in '+name)
        for index, end in enumerate(loads):
            points[f'native_operation_{name.lower()}_{index}'] = base+end
    target = next(r['address'] for r in program['image']['routines']
                  if r['name'].startswith('M_EXECLISTS_ADDTAIL_'))
    base, raw = routine(program, 'DESKCORE_PUMP')
    call = b'\x22'+target.to_bytes(3, 'little')
    require(raw.count(call) == 1, 'Ambiguous native deferral call')
    points['native_deferred'] = base+raw.index(call)
    return points


def admissions(events, definition, spans, worker):
    """Charge each Pump(1), excluding the subsequent input boundary."""
    points = definition['points']
    operations = {pc for name, pc in points.items()
                  if name.startswith('native_operation_')}
    if not operations:
        return []
    interesting = operations | {points['native_deferred']}
    observations = [(t, int(e[4], 16), int(e[5], 16) & 255)
                    for t, e in events if e[0] == 'cpu'
                    and int(e[9], 16) == worker and int(e[4], 16) in interesting]
    ticks = [row[0] for row in observations]
    names = 'REGISTER OPEN SHOW HIDE MOVE RAISE FOCUS REPLACE NEXT_EVENT CANCEL_EVENT CLOSE UNREGISTER SET_TREE UPDATE_WIDGETS READ_WIDGET_STATE'.split()
    names = {ABI['constants'][name]: name for name in names}
    result = []
    for span in spans:
        if span['kind'] != 'deskcore_pump' or not span['return_a'] & 255:
            continue
        require(span['return_a'] & 255 == 1, 'Expected single native admission')
        selected = observations[bisect_left(ticks, span['start']):
                                bisect_left(ticks, span['end'])]
        codes = {a for _, pc, a in selected if pc in operations}
        require(len(codes) <= 1, 'Opcode changed inside native admission')
        code = next(iter(codes), None)
        result.append(dict(span, operation=code,
            operation_name=names.get(code, 'unobserved' if code is None else 'unknown'),
            deferred=any(pc == points['native_deferred'] for _, pc, _ in selected)))
    return result


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['operation_name']].append(row)
    return {name: dict(calls=len(values), deferred=sum(r['deferred'] for r in values),
                      total_cpu_ms=sum(r['charged_cpu_ms'] for r in values),
                      slowest=max(values, key=lambda r: r['charged_cpu_ms']))
            for name, values in sorted(groups.items())}


# Selected bookkeeping boundaries, rather than every native routine. These
# observations add no target counters, calls, reservations or timing hooks.
BOOKKEEPING = '''CONSOLEDRIVER_COLLECT CONSOLEDRIVER_RUNNABLE
DESKHOST_RUNNABLE DESKHOST_CACHE DESKINPUT_RUNNABLE DESKINPUT_BOUNDARY
DESKINPUT_SERVICE DESKINPUT_PRESENT DESKINPUT_ADVANCE DESKMENU_RUNNABLE
DESKWIDGETINPUT_RUNNABLE DESKDRAG_RUNNABLE DESKPAINT_READY DESKPAINT_RUNNABLE
DESKPAINT_PAINTPENDING DESKPAINT_DAMAGEPENDING AESLOCKS_NATIVEREADY
AESGATE_OWNERENTER AESGATE_OFFER AESHOST_SETTLED INPUT_TAKE
DESKCACHE_PATCH DESKCACHE_CAPTURE DESKMENUCACHE_CAPTUREPOPUP
LAYERS_REBUILD LAYERS_SHOW LAYERS_ORDER LAYERS_ORDERBELOW
AESWINDOW_REQUEST CONSOLEBITMAP_RUN'''.split()
BOOKKEEPING_GROUPS = dict(
    readiness_checks=set('''DESKHOST_RUNNABLE CONSOLEDRIVER_RUNNABLE
        DESKPAINT_READY DESKPAINT_RUNNABLE DESKPAINT_PAINTPENDING
        DESKPAINT_DAMAGEPENDING DESKINPUT_RUNNABLE DESKMENU_RUNNABLE
        DESKWIDGETINPUT_RUNNABLE DESKDRAG_RUNNABLE AESLOCKS_NATIVEREADY'''.split()),
    input_boundaries={'DESKINPUT_SERVICE','DESKINPUT_PRESENT','DESKINPUT_ADVANCE'},
    cache_maintenance={'DESKHOST_CACHE'},
    pixel_dispatch={'CONSOLEBITMAP_RUN','GemDrawingWidgetBatch'},
    visibility_rebuild={'LAYERS_REBUILD'},
    find_task={'tasks_find_task'})


def bookkeeping_markers(program):
    from bitmap_console_performance import native_markers
    names = [n for n in BOOKKEEPING if any(r['name'].startswith('M_'+n+'_')
             for r in program['image']['routines'])]
    spans = native_markers(program, [(n,n) for n in names])
    for n in ('tasks_find_task','ports_reply_msg'):
        spans[n] = dict(entry=program['labels'][n],
                        returns=[program['labels'][n+'_end']-1])
    # The first Cache call is the quiet notification branch; the other is the
    # normal turn tail. Pin the actual emitted call sites, not source offsets.
    base, raw = routine(program, 'CONSOLEDRIVER_WORKER')
    call = b'\x22'+spans['DESKHOST_CACHE']['entry'].to_bytes(3,'little')
    sites = [base+m.start() for m in re.finditer(re.escape(call),raw)]
    require(len(sites)==2, 'Presenter cache branches changed')
    return spans, sites[0]


def bookkeeping_costs(events, spans, timeline, start, end):
    """Inclusive routine costs; group costs are interval unions, not sums."""
    from collections import Counter
    rows = [s for s in spans if start<s['end'] and s['start']<end]
    routines = {}
    def measure(a,b):
        return timeline.measure(max(a,timeline.ticks[0]),min(b,timeline.ticks[-1]))
    for s in rows:
        r = routines.setdefault(s['kind'],dict(calls=0,cpu_ms=0,returns=Counter()))
        r['calls'] += 1
        r['cpu_ms'] += measure(max(start,s['start']),min(end,s['end']))['charged_cpu_ms']
        if 'return_a' in s: r['returns'][str(s['return_a'])] += 1
    groups = {}
    for name, kinds in BOOKKEEPING_GROUPS.items():
        ranges = sorted((max(start,s['start']),min(end,s['end']))
                        for s in rows if s['kind'] in kinds)
        merged = []
        for a,b in ranges:
            if merged and a<=merged[-1][1]: merged[-1][1]=max(b,merged[-1][1])
            else: merged.append([a,b])
        groups[name]=sum(measure(a,b)['charged_cpu_ms'] for a,b in merged)
    return dict(measured=measure(start,end),routines=routines,group_cpu_ms=groups)


def bookkeeping_report(events, native, cspans, timeline, worker_dp, samples, traces, quiet_pc, turn_pc):
    from sio_transaction_trace import BASE_HZ
    worker = [s for s in native if s['dp']==worker_dp]
    spans = worker+cspans
    actions=[]
    for sample,trace in zip(samples,traces):
        start=trace['start'];end=start+round(sample.get('window_ms',
            (trace['end']-start)*1000/BASE_HZ)*BASE_HZ/1000)
        row=dict(action=sample['action'],visible=bookkeeping_costs(events,spans,timeline,start,end))
        requests=[s for s in worker if s['kind']=='AESWINDOW_REQUEST'
                  and start<=s['start']<s['end']<=end]
        prepared=[s for s in worker if s['kind']=='LAYERS_ORDERBELOW']
        rebuilds=[s for s in worker if s['kind']=='LAYERS_REBUILD']
        row['prepared_open_rebuilds']=[
            sum(r['start']<=s['start']<s['end']<=r['end'] for s in rebuilds)
            for r in requests
            if any(r['start']<=s['start']<s['end']<=r['end'] for s in prepared)]
        if trace['updates']:
            first=min(u['calls'][0]['start'] for u in trace['updates'])
            row['before_application_BEGIN']=bookkeeping_costs(events,spans,timeline,start,first)
        a=min(end+round(.6*BASE_HZ),trace['end']);b=trace['end']
        row['settled_idle_turns']=sum(a<=t<b and int(e[4],16)==turn_pc for t,e in events)
        actions.append(row)
    offers=sorted((s for s in worker if s['kind']=='AESGATE_OFFER'),key=lambda s:s['start'])
    offer_ticks=[s['start'] for s in offers]
    quiet_ticks=[t for t,e in events if int(e[4],16)==quiet_pc]
    quiet=[];active=[]
    for s in worker:
        if s['kind']!='AESGATE_OWNERENTER':continue
        if not any(t['start']<=s['start']<t['end'] for t in traces):continue
        index=bisect_right(offer_ticks,s['start'])
        if index==len(offers):continue
        offer=offers[index]
        q=bisect_left(quiet_ticks,s['start'])
        if q<len(quiet_ticks) and quiet_ticks[q]<offer['end']:
            quiet.append(bookkeeping_costs(events,spans,timeline,s['start'],offer['end']))
        else:
            active.append(timeline.measure(s['start'],offer['end']))
    return dict(actions=actions,quiet_turns=quiet,active_turns=active)
