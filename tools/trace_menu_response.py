#!/usr/bin/env python3
"""Passive per-action dropdown costs on an unchanged packaged desktop."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import zipfile

from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from g4bench_trace import calls, native_calls
from measure_menu_feedback import Feedback
from native_program import read_build, require, sha256
from presenter_control_trace import bookkeeping_costs
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run
import window_response_trace as response

NATIVE = '''DESKMENU_MOUSE DESKMENU_KEY DESKMENU_HEADING DESKMENU_OPEN
DESKMENU_POPUP DESKMENU_CANCEL DESKMENU_DAMAGETITLE
DESKAPPMENU_REFRESH DESKAPPMENU_SNAPSHOT DESKAPPMENU_FINISH
DESKAPPMENU_DAMAGEOBJECT DESKAPPMENU_INVERTSELECTION DESKAPPMENU_PLAINROW
DESKAPPMENU_POPUPBOUNDS DESKAPPMENU_BACKGROUNDBOUNDS DESKSTATE_TOPCHROME
DESKMENUCACHE_RESTORE DESKMENUCACHE_CAPTURE DESKMENUCACHE_REUSABLE
DESKMENUCACHE_TRANSFER DESKMENUCACHE_POPUPTRANSFER DESKMENUCACHE_RESTOREPOPUP
DESKMENUCACHE_POPUPRESTORED DESKMENUCACHE_END DESKMENUCACHE_EXPOSED
DESKMENUCACHE_NOTIFY DESKMENUCACHE_SELECTPOPUP
DESKHOST_CONTROLS DESKHOST_MENUCONTINUATION DESKHOST_INPUTBOUNDARY
DESKHOST_EVENTS DESKHOST_AFTERPAINT DESKPAINT_PAINTSTRIP DESKPAINT_SELECTSTRIP
DESKPAINT_SYNC CONSOLEINPUT_SERVICE CONSOLEWINDOWS_TAKE
AESHOST_PUMP AESHOST_SETTLE AESMOUSE_REFRESH AESINBOX_SNAPSHOT
AESWINDOWSTATE_SYNC AESWINDOWSTATE_PUBLISH AESWINDOWSTATE_HANDOFF
LAYERS_ADMIT LAYERS_FINISH LAYERS_BEGIN LAYERS_BEGINREAD LAYERS_BEGINSAVE
LAYERS_BEGINRESTORE LAYERS_BOUNDS LAYERS_INVALIDATE LAYERS_REORDER
LAYERS_MARKRESTORED LAYERS_DAMAGEALL LAYERS_ADDDAMAGE
REGIONS_SUBTRACT REGIONS_INTERSECT REGIONS_INTERSECTLIST REGIONS_COPY
'''.split()
C = '''GemDrawingMenuRow GemDrawingInvertRect GemDrawingText
VbxeOwnerCopyStart VbxeOwnerPoll VbxeOwnerWait VbxeOwnerCopy
draw_CopyStart draw_Poll blit_chain VbxeValidateCopy idle start drain fence_owner
GemWidgetText GemFramePattern'''.split()


def setup(out):
    p=read_build(out);d=response.setup(out,bookkeeping=True)
    present=[n for n in NATIVE if any(r['name'].startswith('M_'+n+'_') for r in p['image']['routines'])]
    extra=native_markers(p,[(n,n) for n in present])
    d['timeline']['spans'].update(extra)
    for n,s in extra.items():
        d['points'][s['entry']]=n
        d['points'].update({pc:n+'_return' for pc in s['returns']})
    foreign=json.loads((out/'bitmap-console/c-image.json').read_text())
    d['entries'].update({foreign['symbols'][n]:n for n in C if n in foreign['symbols']})
    d['points'].update(d['entries'])
    return d


def analyze(out):
    d=json.loads((out/'menu-definition.json').read_text())
    d['points']={int(pc):name for pc,name in d['points'].items()}
    d['entries']={int(pc):name for pc,name in d['entries'].items()}
    events=read_events(out/'emulator.log',kinds={'cpu'})
    profile=analyze_events(events,{**d['timeline'],'spans':{}},include_segments=True)
    worker=profile['worker_dp']
    timelines={dp:Timeline(profile['segments'],dp) for dp in d['timeline']['task_dps']}
    cs,unfinished=calls(events,d['entries'],set(d['returns']),worker,set(d['exits']))
    spans=native_calls(events,d['timeline']['spans'])+[dict(s,dp=worker) for s in cs]
    raw=json.loads((out/'menu-action-samples.json').read_text());samples=[]
    for sample in raw:
        start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        pixels=start+((sample['pixels_end']-sample['start'])&0xffffffff)
        end=start+((sample['end']-sample['start'])&0xffffffff)
        rows=[]
        for s in spans:
            if start<=s['start']<s['end']<=end:
                t=timelines[s['dp']]
                rows.append(dict(s,**t.measure(s['start'],s['end']),
                    start_ms=(s['start']-start)*1000/BASE_HZ,end_ms=(s['end']-start)*1000/BASE_HZ))
        rows.sort(key=lambda s:(s['start'],s['end']))
        window=[s for s in spans if s['dp']==worker]
        costs=bookkeeping_costs(events,window,timelines[worker],start,pixels)
        boundaries=[dict(ms=(t-start)*1000/BASE_HZ,name=d['points'][int(e[4],16)])
            for t,e in events if start<=t<=end and int(e[4],16) in d['points']
            and d['points'][int(e[4],16)] not in
            ('turn','selected','native_irq','native_nmi','interrupt_schedule')]
        before_pixels=[s for s in rows if s['end']<=pixels]
        updates=[s for s in rows if s['kind']=='LAYERS_UPDATEDAMAGE']
        queries=[s for s in before_pixels if s['kind']=='LAYERS_DAMAGED' and not any(
            parent['start']<=s['start']<s['end']<=parent['end'] for parent in updates)]
        copies=[]
        for copy in (s for s in before_pixels if s['kind']=='CONSOLEBITMAP_COPYSTART'):
            parent_names={s['kind'] for s in rows if s['start']<=copy['start']<copy['end']<=s['end']}
            role=next((role for name,role in (
                ('DESKMENUCACHE_CAPTUREPOPUP','popup_capture'),
                ('DESKMENUCACHE_RESTOREPOPUP','popup_restore'),
                ('DESKMENUCACHE_CAPTURE','background_capture'),
                ('DESKMENUCACHE_RESTORE','background_restore')) if name in parent_names),'unknown')
            irq=next((b['ms'] for b in boundaries if b['name']=='blitter_irq_complete'
                      and b['ms']>=copy['start_ms']),None)
            poll=next((s for s in rows if s['kind']=='VbxeOwnerPoll' and not s['return_a']
                       and irq is not None and s['start_ms']>=irq),None)
            finish_kind='DESKMENUCACHE_POPUPRESTORED' if role=='popup_restore' else 'LAYERS_FINISHSAVE'
            finish=next((s for s in rows if s['kind']==finish_kind
                         and irq is not None and s['start_ms']>=irq),None)
            copies.append(dict(role=role,start_ms=copy['start_ms'],return_ms=copy['end_ms'],
                cpu_ms=copy['charged_cpu_ms'],irq_ms=irq,
                poll_return_ms=poll['end_ms'] if poll else None,
                retirement_ms=finish['end_ms'] if finish else None))
        samples.append(dict(sample,start=start,pixels_end=pixels,end=end,spans=rows,
            boundaries=boundaries,bookkeeping=costs,
            copies=copies,damage_queries=dict(calls=len(queries),
                cpu_ms=sum(s['charged_cpu_ms'] for s in queries)),
            task_charges={str(dp):t.measure(start,pixels) for dp,t in timelines.items()}))
    serial=Counter();serial_all=Counter()
    with (out/'emulator.log').open() as source:
        for line in source:
            if '[SIOTXN] ' not in line:continue
            f=line.split('[SIOTXN] ',1)[1].split()
            if f[0] not in ('command','rxstart','receive','read'):continue
            serial_all[f[0]]+=1
            if any(s['start']<=int(f[1])<=s['end'] for s in samples):serial[f[0]]+=1
    result=dict(tier='development',qualification=False,guest_changes=False,
        archive_sha256=sha256(out/'exec816-demo.zip'),observer_sha256=sha256(Path(__file__)),
        feedback_sha256=sha256(Path(__file__).with_name('measure_menu_feedback.py')),
        presenter_dp=worker,samples=samples,serial_events=dict(capture=dict(serial_all),timed=dict(serial)),
        scope='Passive original menu interactions; per-action cache counters include a settled tail. CPU costs stop at the PAL-frame pixel sample. Inclusive spans overlap; off-presenter time is not DMA time.')
    (out/'menu-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    for s in samples:
        print(s['action'],round(s['pixels_ms'],3),'ms; presenter',round(s['bookkeeping']['measured']['charged_cpu_ms'],3),
            'ms CPU; cache',s['transfers']['popupRestores'],s['transfers']['popupMisses'],flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--analyze',action='store_true')
    a=p.parse_args();out=a.output.resolve()
    if a.analyze:return analyze(out)
    require(a.bundle is not None and not out.exists(),'Supply a bundle and fresh output directory')
    shutil.copytree(a.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    d=setup(out)
    (out/'menu-definition.json').write_text(json.dumps(d,indent=2)+'\n')
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS');saved={k:os.environ.get(k) for k in keys}
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in response.pcs(d)))
    probe=Feedback(3,trace=True,application_only=True)
    try:
        result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
        result.update(menus=probe.results,qualification=False)
        (out/'menu-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        for k,v in saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    return analyze(out)


if __name__=='__main__':main()
