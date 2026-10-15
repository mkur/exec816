#!/usr/bin/env python3
"""Observe packaged New Window setup, enumeration and painting without guest edits."""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import shutil
import zipfile

from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from gem_applications import instances
from g4bench_trace import calls, listing_returns, native_calls
from measure_frame_exposure import Frames
from native_program import read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run
import window_response_trace as response

NATIVE = '''DESKHOST_CONTROLS DESKHOST_EVENTS DESKHOST_INPUTBOUNDARY DESKHOST_AFTERPAINT
AESHOST_PUMP AESHOST_SETTLE AESCORE_PUMP AESCORE_DISPATCH AESSTATE_REPLY
AESMOUSE_REFRESH AESINBOX_SNAPSHOT AESWINDOWSTATE_SYNC AESWINDOWSTATE_PUBLISH
DESKPAINT_FRAMESTEP DESKPAINT_SYNC DESKPAINT_PAINTSTRIP
CONSOLEINPUT_SERVICE CONSOLEWINDOWS_TAKE CONSOLEDRIVER_ARRIVAL
DESKINPUT_FRESH DESKINPUT_COPY DESKCORE_FOCUS'''.split()
RESIDENT = '''wind_create wind_open wind_get wind_set wind_set_str menu_tnormal
menu_ienable menu_icheck Lock UnLock Examine ExNext AllocMem FreeMem Wait GetMsg
PutMsg ExecAESPainted objc_draw idle start fence_owner drain memcpy memset'''.split()
APPLICATION = '''desktop_new desktop_menu folder_open folder_title refresh refresh_path
FileScanBegin FileScanNext FileScanEnd layout sliders redraw view_checks menu_state
selection_status menu_enable menu_check folder_event desktop_dispatch desktop_draw
desktop_status'''.split()


class Opening(Frames):
    def exercise(self, session):
        self.live = next(a for a in instances(session.b, session.p,
                         session.p['output']/'bitmap-console') if a['name']=='desktop')
        (session.p['output']/'opening-app.json').write_text(json.dumps(self.live,indent=2)+'\n')
        super().exercise(session)


def setup(out):
    p=read_build(out);d=response.setup(out,bookkeeping=True)
    extra=native_markers(p,[(n,n) for n in NATIVE])
    d['timeline']['spans'].update(extra)
    for n,s in extra.items():
        d['points'][s['entry']]=n
        d['points'].update({pc:n+'_return' for pc in s['returns']})
    foreign=json.loads((out/'bitmap-console/c-image.json').read_text())
    d['entries'].update({foreign['symbols'][n]:n for n in RESIDENT if n in foreign['symbols']})
    d['points'].update(d['entries'])
    app=json.loads((out/'bitmap-console/apps/desktop/app.json').read_text())
    d['app_entries']={app['image']['symbols'][n]:'app.'+n for n in APPLICATION if n in app['image']['symbols']}
    # RTL boundaries cover the application, including shared/tail epilogues.
    # Registering every JSL successor in every legal bank exceeds macOS's
    # process environment limit. Resident call successors remain available.
    d['app_returns']=[]
    d['app_exits']=listing_returns(app['image'],out/'bitmap-console/apps/desktop',exits=True)
    d['link_base']=app['abi']['link_bank']<<16
    points=set(response.pcs(d))
    for bank in app['verified_banks']:
        delta=(bank<<16)-d['link_base']
        points.update(pc+delta for pc in set(d['app_entries'])|set(d['app_returns'])|set(d['app_exits']))
    return d,sorted(points)


def analyze(out):
    d=json.loads((out/'opening-definition.json').read_text())
    live=json.loads((out/'opening-app.json').read_text())
    events=read_events(out/'emulator.log',kinds={'cpu'})
    profile=analyze_events(events,{**d['timeline'],'spans':{}},include_segments=True)
    delta=live['base']-d['link_base']
    entries={int(pc):name for pc,name in d['entries'].items()}
    entries.update({int(pc)+delta:name for pc,name in d['app_entries'].items()})
    returns=set(d['returns'])|{pc+delta for pc in d['app_returns']}
    exits=set(d['exits'])|{pc+delta for pc in d['app_exits']}
    new_pc=next(pc for pc,n in entries.items() if n=='app.desktop_new')
    owners={int(e[9],16) for _,e in events if int(e[4],16)==new_pc}
    require(len(owners)==1,'No unique Desktop Task')
    app_dp=owners.pop();worker=profile['worker_dp']
    timelines={dp:Timeline(profile['segments'],dp) for dp in d['timeline']['task_dps']}
    native=native_calls(events,d['timeline']['spans'])
    c=[]
    for dp in (app_dp,worker):
        rows,unfinished=calls(events,entries,returns,dp,exits)
        c.extend(dict(r,dp=dp) for r in rows)
    samples=json.loads((out/'frame-exposure-samples.json').read_text())
    sample=next(s for s in samples if s['action']=='New Window')
    start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
    end=start+sample['window_ms']*BASE_HZ/1000
    spans=[s for s in native+c if start<=s['start']<s['end']<=end]
    for s in spans:
        s.update(timelines[s['dp']].measure(s['start'],s['end']))
        s.update(start_ms=(s['start']-start)*1000/BASE_HZ,end_ms=(s['end']-start)*1000/BASE_HZ)
    spans.sort(key=lambda s:(s['start'],s['end']))
    totals={}
    for s in spans:
        key=('desktop' if s['dp']==app_dp else 'presenter')+':'+s['kind']
        t=totals.setdefault(key,dict(calls=0,elapsed_ms=0,charged_cpu_ms=0,off_cpu_ms=0,interrupt_ms=0))
        t['calls']+=1
        for k in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms'):t[k]+=s[k]
    def one(name):
        found=[s for s in spans if s['kind']==name]
        require(len(found)==1,'Expected one '+name)
        return found[0]
    new,folder,refresh,draw=(one(n) for n in
        ('app.desktop_new','app.folder_open','app.refresh_path','app.redraw'))
    scan_end=max(s['end'] for s in spans if s['kind']=='app.FileScanNext')
    boundaries=[('Input and menu dismissal',start,new['start']),
        ('Browser allocation',new['start'],folder['start']),
        ('Window setup and open',folder['start'],refresh['start']),
        ('Directory enumeration',refresh['start'],scan_end),
        ('Listing preparation',scan_end,folder['end']),
        ('Active menu state',folder['end'],new['end']),
        ('Redraw event dispatch',new['end'],draw['start']),
        ('Content redraw',draw['start'],draw['end']),
        ('Until complete pixel sample',draw['end'],end)]
    phases=[]
    for name,left,right in boundaries:
        phases.append(dict(name=name,start_ms=(left-start)*1000/BASE_HZ,
            end_ms=(right-start)*1000/BASE_HZ,elapsed_ms=(right-left)*1000/BASE_HZ,
            task_charges={str(dp):t.measure(left,right) for dp,t in timelines.items()}))
    frames=[dict(s,task_charges={str(dp):t.measure(s['start'],s['end'])
            for dp,t in timelines.items()}) for s in spans if s['kind']=='CONSOLEBITMAP_FRAME']
    gaps=[]
    for first,second in zip(frames,frames[1:]):
        left,right=first['end'],second['start']
        gaps.append(dict(start_ms=first['end_ms'],end_ms=second['start_ms'],
            task_charges={str(dp):t.measure(left,right) for dp,t in timelines.items()},
            spans=[s for s in spans if s['dp']==worker and left<=s['start']<s['end']<=right]))
    # Boot traffic proves the passive serial observer was enabled. These
    # hardware timestamps are full-width; CPU timestamps are unwrapped above.
    serial_all=Counter();serial_window=Counter()
    with (out/'emulator.log').open() as source:
        for line in source:
            if '[SIOTXN] ' not in line:continue
            fields=line.split('[SIOTXN] ',1)[1].split()
            if fields[0] not in ('command','rxstart','receive','read'):continue
            serial_all[fields[0]]+=1
            if start<=int(fields[1])<=end:serial_window[fields[0]]+=1
    report=dict(tier='development',qualification=False,guest_changes=False,archive_sha256=sha256(out/'exec816-demo.zip'),
        observer_sha256=sha256(Path(__file__)),start=start,end=end,sample=sample,app_dp=app_dp,presenter_dp=worker,
        task_charges={str(dp):t.measure(start,end) for dp,t in timelines.items()},
        spans=spans,inclusive_totals=totals,phases=phases,frames=frames,frame_gaps=gaps,
        serial_events=dict(capture=dict(serial_all),opening=dict(serial_window)),
        scope='One matched warm-directory New Window; inclusive routines overlap. CPU includes kernel/scheduling charges; native interrupts and peer Tasks are separate.')
    (out/'opening-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    for s in spans:
        if s['kind'] in ('app.desktop_new','app.folder_open','app.refresh_path','app.redraw','wind_open'):
            print(s['kind'],*[round(s[k],3) for k in ('start_ms','end_ms','charged_cpu_ms','off_cpu_ms')],flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--analyze',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if args.analyze:return analyze(out)
    require(args.bundle is not None and not out.exists(),'Supply a bundle and fresh output directory')
    shutil.copytree(args.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    d,points=setup(out)
    (out/'opening-definition.json').write_text(json.dumps(d,indent=2)+'\n')
    saved={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
    probe=Opening(1,False,True)
    try:
        result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
        (out/'opening-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        for k,v in saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    # Shareable trace excludes bridge credentials and unrelated diagnostics.
    events=read_events(out/'emulator.log',kinds={'cpu'})
    with gzip.open(out/'opening-cpu.log.gz','wt') as f:
        f.write('[SIOTXN] anchor '+str(int(events[0][0]))+'\n')
        for _,e in events:f.write('[SIOTXN] '+' '.join(e)+'\n')
    return analyze(out)


if __name__=='__main__':main()
