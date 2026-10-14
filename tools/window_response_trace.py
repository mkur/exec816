"""Passive boundaries shared by the existing window/menu observers."""
import json
from pathlib import Path
import adapter_state as adapter
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from dos_concurrent_trace import call_marker
from g4bench_trace import listing_returns, calls
from native_program import read_build, require
from sio_transaction_trace import BASE_HZ

NATIVE = ('DESKINPUT_SERVICE DESKMENU_ADVANCE DESKMENUCACHE_PUMP '
          'LAYERS_FINISHSAVE DESKPAINT_PUMP CONSOLEBITMAP_COPYSTART '
          'CONSOLEBITMAP_POLL CONSOLEBITMAP_FRAME DESKAPPMENU_PAINT').split()
DRAWING = ('GemDrawingFrameBatch GemDrawingWidgetBatch GemDrawingBatch '
           'GemDrawingCopyStart GemDrawingPoll GemFrameGadget GemWidgetFill '
           'blit_mask solid_record VbxeOwnerSubmit VbxeOwnerFence '
           'VbxeOwnerWrite pointer_erase').split()


def setup(out):
    program = read_build(out)
    foreign = json.loads((out/'bitmap-console/c-image.json').read_text())
    spans = native_markers(program, [(n, n) for n in NATIVE])
    points = {}
    for name, span in spans.items():
        points[span['entry']] = name
        for pc in span['returns']: points[pc] = name+'_return'
    entries = {foreign['symbols'][n]:n for n in DRAWING if n in foreign['symbols']}
    points.update(entries)
    returns = listing_returns(foreign, out/'bitmap-console/drawing')
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
    return dict(points=points, entries=entries, returns=returns,
                timeline=dict(points=clock,spans=spans,
                    task_dps=[p['dp'] for p in program['build']['memory']['task_pools']]))


def pcs(d):
    return sorted(set(d['points']) | set(d['returns']))


def report(out, events, d, samples, name):
    profile = analyze_events(events,d['timeline'],include_segments=True)
    workers={int(e[9],16) for _,e in events if int(e[4],16)==d['timeline']['points']['turn']}
    worker=workers.pop();timeline=Timeline(profile['segments'],worker)
    cspans,unfinished=calls(events,d['entries'],set(d['returns']),worker)
    rows=[]
    for sample in samples:
        start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        end=start+(sample['end']-sample['start'])%(1<<32)
        spans=[s for s in profile['routine_spans']+cspans if start<=s['start']<s['end']<=end]
        for s in spans:s.update(timeline.measure(s['start'],s['end']))
        boundaries=[dict(ms=(tick-start)/BASE_HZ*1000,name=d['points'][int(e[4],16)])
                    for tick,e in events if start<=tick<end and int(e[4],16) in d['points']
                    and d['points'][int(e[4],16)] not in
                    ('turn','selected','native_irq','native_nmi','interrupt_schedule')]
        frames=[]
        for frame in (s for s in spans if s['kind']=='CONSOLEBITMAP_FRAME'):
            nested=[s for s in spans if frame['start']<=s['start']<s['end']<=frame['end']]
            counts={kind:sum(s['kind']==kind for s in nested) for kind in DRAWING}
            frames.append(dict(frame,counts=counts))
        rows.append(dict(action=sample['action'],start=start,end=end,frames=frames,
                         spans=spans,boundaries=boundaries))
    result=dict(tier='development',qualification=False,
        completion='IRQ completion observation, not an independently sampled BUSY falling edge',
        cpu='Conservative Task CPU charge, excluding peer Tasks and native interrupts',samples=rows)
    (out/(name+'-trace.json')).write_text(json.dumps(result,indent=2)+'\n')
