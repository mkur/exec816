"""Passive boundaries shared by the existing window/menu observers."""
import json
from pathlib import Path
import adapter_state as adapter
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from dos_concurrent_trace import call_marker
from g4bench_trace import listing_returns, calls, native_calls, update_summary
from native_program import read_build, require
from sio_transaction_trace import BASE_HZ

NATIVE = ('DESKINPUT_SERVICE DESKMENU_ADVANCE DESKMENUCACHE_PUMP '
          'LAYERS_FINISHSAVE DESKPAINT_PUMP CONSOLEBITMAP_COPYSTART '
          'CONSOLEBITMAP_POLL CONSOLEBITMAP_FRAME DESKAPPMENU_PAINT').split()
DRAWING = ('GemDrawingFrameBatch GemDrawingWidgetBatch GemDrawingBatch '
           'GemDrawingCopyStart GemDrawingPoll GemFrameGadget GemWidgetFill '
           'blit_mask solid_record VbxeOwnerSubmit VbxeOwnerFence '
           'VbxeOwnerWrite pointer_erase wind_update ExecAESBeginUpdate ExecAESUpdate '
           'ExecAESSubmit _AESUpdateCall').split()


def setup(out, bookkeeping=False):
    program = read_build(out)
    foreign = json.loads((out/'bitmap-console/c-image.json').read_text())
    spans = native_markers(program, [(n, n) for n in NATIVE])
    optional = ('AESLOCAL_UPDATE AESGATE_CLAIM AESGATE_RELEASE AESGATE_OWNERENTER '
                'AESGATE_OFFER AESLOCKS_NATIVEREADY AESLOCKS_ATTEMPT AESLOCKS_ELIGIBLE').split()
    present = [n for n in optional if any(r['name'].startswith('M_'+n+'_')
               for r in program['image']['routines'])]
    spans.update(native_markers(program, [(n,n) for n in present]))
    quiet_pc = None
    if bookkeeping:
        from presenter_control_trace import bookkeeping_markers
        extra, quiet_pc = bookkeeping_markers(program)
        spans.update(extra)
    points = {}
    for name, span in spans.items():
        points[span['entry']] = name
        for pc in span['returns']: points[pc] = name+'_return'
    entries = {foreign['symbols'][n]:n for n in DRAWING if n in foreign['symbols']}
    points.update(entries)
    returns = listing_returns(foreign, out/'bitmap-console/drawing')
    exits = listing_returns(foreign, out/'bitmap-console/drawing', exits=True)
    collect = next(r['address'] for r in program['image']['routines']
                   if r['name'].startswith('M_CONSOLEDRIVER_COLLECT_'))
    mapped = {**program, 'labels': {**program['labels'], 'collect':collect}}
    clock = {'turn':call_marker(mapped,'M_CONSOLEDRIVER_WORKER_','collect')}
    address = program['labels']['context_restore']
    hosted = (out/'hosted.bin').read_bytes()
    require(hosted[address-adapter.RESIDENT_BASE:address-adapter.RESIDENT_BASE+8] ==
            bytes.fromhex('c230ab2b7afa6840'), 'Unrecognized context restore')
    clock['selected'] = address+4
    for n in ('native_irq','native_nmi','interrupt_schedule',
              'blitter_irq_complete','blitter_irq_posted','blitter_expired'):
        if n in program['labels']: clock[n] = program['labels'][n]
    points.update({pc:n for n,pc in clock.items()})
    if quiet_pc is not None: points[quiet_pc]='quiet_cache'
    return dict(points=points, entries=entries, returns=returns, exits=exits,
                quiet_pc=quiet_pc,
                timeline=dict(points=clock,spans=spans,
                    task_dps=[p['dp'] for p in program['build']['memory']['task_pools']]))


def pcs(d):
    return sorted(set(d['points']) | set(d['returns']) | set(d.get('exits',())))


def report(out, events, d, samples, name):
    profile = analyze_events(events,{**d['timeline'],'spans':{}},include_segments=True)
    workers={int(e[9],16) for _,e in events if int(e[4],16)==d['timeline']['points']['turn']}
    worker=workers.pop();timeline=Timeline(profile['segments'],worker)
    cspans,unfinished=calls(events,d['entries'],set(d['returns']),worker,set(d.get('exits',())))
    all_native=native_calls(events,d['timeline']['spans'])
    caller_dps={int(e[9],16) for _,e in events if d['entries'].get(int(e[4],16))
                in ('wind_update','ExecAESBeginUpdate')}
    caller_spans={dp:calls(events,d['entries'],set(d['returns']),dp,set(d.get('exits',())))[0] for dp in caller_dps}
    rows=[]
    for sample in samples:
        start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        end=start+(sample['end']-sample['start'])%(1<<32)
        spans=[s for s in all_native+cspans if s.get('dp',worker)==worker
               and start<=s['start']<s['end']<=end]
        for s in spans:s.update(timeline.measure(s['start'],s['end']))
        boundaries=[dict(ms=(tick-start)/BASE_HZ*1000,name=d['points'][int(e[4],16)])
                    for tick,e in events if start<=tick<end and int(e[4],16) in d['points']
                    and d['points'][int(e[4],16)] not in
                    ('turn','selected','native_irq','native_nmi','interrupt_schedule')]
        frames=[]
        for frame in (s for s in spans if s['kind']=='CONSOLEBITMAP_FRAME'):
            nested=[s for s in spans if frame['start']<=s['start']<s['end']<=frame['end']]
            counts={kind:sum(s['kind']==kind for s in nested) for kind in DRAWING}
            frames.append(dict(frame,counts=counts,
                blitter_records=sum(s['argument'] for s in nested if s['kind']=='VbxeOwnerSubmit')))
        require(boundaries,'No response trace events for '+sample['action'])
        updates=[]
        for dp,cs in caller_spans.items():
            local_timeline=Timeline(profile['segments'],dp)
            u=update_summary(cs,all_native,local_timeline,dp,start,end)
            if u['calls']:
                first,last=u['calls'][0]['start'],u['calls'][-1]['end']
                u.update(task_dp=dp,completion=local_timeline.measure(first,last),
                         presenter_cpu_ms=timeline.measure(first,last)['charged_cpu_ms'])
                updates.append(u)
        rows.append(dict(action=sample['action'],start=start,end=end,frames=frames,
                         spans=spans,boundaries=boundaries,updates=updates))
    result=dict(tier='development',qualification=False,
        completion='IRQ completion observation, not an independently sampled BUSY falling edge',
        cpu='Conservative Task CPU charge, excluding peer Tasks and native interrupts',samples=rows)
    (out/(name+'-trace.json')).write_text(json.dumps(result,indent=2)+'\n')
    if d.get('quiet_pc') is not None:
        from presenter_control_trace import bookkeeping_report
        costs=bookkeeping_report(events,all_native,cspans,timeline,worker,samples,rows,
                                 d['quiet_pc'],d['timeline']['points']['turn'])
        costs.update(tier='development',qualification=False)
        (out/(name+'-bookkeeping.json')).write_text(json.dumps(costs,indent=2)+'\n')
