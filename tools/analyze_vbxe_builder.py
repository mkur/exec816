#!/usr/bin/env python3
"""Decompose passive presenter traces; report list limits and CPU/latency costs."""
import argparse
import json
import math
from pathlib import Path
from collections import defaultdict,Counter
from statistics import median
from sio_transaction_trace import read_events
from console_turn_profile import analyze_events,Timeline
from native_program import require,sha256


def analyze(out):
    out=out.resolve()
    j=json.loads((out/'results.json').read_text());d=json.loads((out/'presenter-definition.json').read_text())
    events=read_events(out/'emulator.log',kinds={'cpu'})
    p=analyze_events(events,d,include_segments=True);tl=Timeline(p['segments'],p['worker_dp']);spans=p['routine_spans']
    align=lambda t:t+round((events[0][0]-t)/(1<<32))*(1<<32)
    def group(s):return d['spans'][s['kind']].get('callee',s['kind'])
    def decompose(row):
        a,b=row['start'],row['end']
        enclosed=[s for s in spans if s['start']<b and s['end']>a]
        edges=sorted({a,b,*(max(a,s['start']) for s in enclosed),*(min(b,s['end']) for s in enclosed)})
        buckets=defaultdict(float)
        for x,y in zip(edges,edges[1:]):
            inside=[s for s in enclosed if s['start']<=x<y<=s['end']]
            key=group(max(inside,key=lambda s:s['start'])) if inside else 'other_worker'
            buckets[key]+=tl.measure(x,y)['charged_cpu_ms']
        require(abs(sum(buckets.values())-row['charged_cpu_ms'])<1e-6,'Exclusive costs disagree')
        inclusive=defaultdict(lambda:dict(calls=0,charged_cpu_ms=0,max_cpu_ms=0))
        for s in enclosed:
            if a<=s['start']<s['end']<=b:
                r=inclusive[group(s)];r['calls']+=1;r['charged_cpu_ms']+=s['charged_cpu_ms'];r['max_cpu_ms']=max(r['max_cpu_ms'],s['charged_cpu_ms'])
        submissions=[]
        for v in enclosed:
            if group(v)!='VbxeOwnerSubmit' or not a<=v['start']<v['end']<=b:continue
            fence=next((f for f in sorted(enclosed,key=lambda x:x['start']) if group(f)=='VbxeOwnerFence' and v['start']<f['start']<f['end']<v['end']),None)
            require(fence is not None,'Missing submit fence')
            submissions.append(dict(start=v['start'],end=v['end'],charged_cpu_ms=v['charged_cpu_ms'],before_first_fence_cpu_ms=tl.measure(v['start'],fence['start'])['charged_cpu_ms'],from_first_fence_cpu_ms=tl.measure(fence['start'],v['end'])['charged_cpu_ms']))
        return dict(**{k:v for k,v in row.items() if k!='routines'},submissions=submissions,exclusive_cpu_ms=dict(sorted(buckets.items(),key=lambda x:-x[1])),inclusive_routines=dict(sorted(inclusive.items(),key=lambda x:-x[1]['charged_cpu_ms'])))
    turnticks=[t for t,e in events if int(e[4],16)==d['points']['worker_turn'] and int(e[9],16)==p['worker_dp']]
    serviceticks=[t for t,e in events if int(e[4],16)==d['spans']['deskinput_service']['entry'] and int(e[9],16)==p['worker_dp']]
    def gaps(ticks):return [dict(start=a,end=b,**tl.measure(a,b)) for a,b in zip(ticks,ticks[1:])]
    turns=gaps(turnticks);services=gaps(serviceticks)
    windows={k:list(map(align,v)) for k,v in j.get('windows',{}).items()} if 'windows' in j else {'scroll':list(map(align,j['window']))}
    windows['whole_presenter_run']=[turnticks[0],turnticks[-1]]
    windows['before_worker_loop']=[events[0][0],turnticks[0]]
    kinds=['consoledisplay_present','consoledisplay_cells','consolebitmap_text','consolebitmap_clippedtext','pump','paint','deskhost_controls','commit','deskinput_service','deskinput_advance','consoledriver_writequantum','deskhost_cache','consolebitmap_run']
    result=dict(status=j['status'],scope='Optimized development replay, unchanged guest binary. Inclusive routine costs overlap; exclusive costs reconcile to each unit. CPU excludes native interrupts and off-Task time, includes kernel/C tails and bus stalls. RTL endpoints exclude the RTL instruction; C call sites include JSL through the return continuation.',image_sha256=j.get('xex_sha256',j.get('build',{}).get('xex_sha256')),trace_sha256=sha256(out/'emulator.log'),worker_dp=p['worker_dp'],source_trace=str(out/'emulator.log'),definition=d,windows={})
    for load,(a,b) in windows.items():
        selected=[s for s in spans if a<=s['start']<s['end']<=b]
        maxima={}
        for k in kinds:
            rows=[s for s in selected if s['kind']==k]
            if rows:maxima[k]=decompose(max(rows,key=lambda r:r['charged_cpu_ms']))
        summary={}
        for name in sorted({group(s) for s in selected}):
            rows=[s for s in selected if group(s)==name]
            summary[name]=dict(calls=len(rows),total_cpu_ms=sum(s['charged_cpu_ms'] for s in rows),max_cpu_ms=max(s['charged_cpu_ms'] for s in rows))
        workpcs={v for k,v in d['points'].items() if k.startswith('list_work_')}
        work=[int(e[5],16) for t,e in events if a<=t<=b and int(e[4],16) in workpcs and int(e[9],16)==p['worker_dp']]
        if work:require(max(work)<=8192,'List work overflow')
        counts=defaultdict(list)
        submit=j['marks']['VbxeOwnerSubmit']
        drawing=[s for s in spans if s['kind']=='paint'];console=[s for s in spans if s['kind']=='consoledisplay_present']
        sites={s['entry']:s.get('caller','unknown') for s in d['spans'].values() if s.get('callee')=='VbxeOwnerSubmit'}
        lastcaller={}
        for t,e in events:
            pc,dp=int(e[4],16),int(e[9],16)
            if pc in sites:lastcaller[dp]=sites[pc]
            if not a<=t<=b or int(e[4],16)!=submit or int(e[9],16)!=p['worker_dp']:continue
            count=int(e[5],16);require(1<=count<=64,'List record overflow')
            key='widget_drawing' if any(s['start']<t<s['end'] for s in drawing) else 'console_drawing' if any(s['start']<t<s['end'] for s in console) else 'other_prepared'
            caller=lastcaller.get(dp,'unknown')
            if caller in ('cursor_render','cursor_submit'):key='cursor'
            elif caller=='outline_toggle':key='outline'
            counts[key].append(count)
        lists={}
        for name,values in counts.items():
            ordered=sorted(values);n=len(values)
            lists[name]=dict(lists=n,mean=sum(values)/n,median=median(values),p95=ordered[math.ceil(.95*n)-1],maximum=max(values),histogram=dict(sorted(Counter(values).items())))
        result['windows'][load]=dict(begin=a,end=b,maxima=maxima,routines=summary,prepared_lists=lists,maximum_queued_work=max(work) if work else None)
        for k,rows in [('actual_worker_turn',turns),('input_service_gap',services)]:
            rows=[r for r in rows if a<=r['start']<r['end']<=b]
            if rows:result['windows'][load][k]=decompose(max(rows,key=lambda r:r['charged_cpu_ms']))
        if 'input_breakdown' in j:
            rows=[r for r in j['input_breakdown']['records'] if r['load']==load]
            result['windows'][load]['slowest_input_samples']=[decompose(dict(r,start=r['capture'],end=r['consumed'])) for r in sorted(rows,key=lambda r:r['elapsed_ms'],reverse=True)[:2]]
    result['runtime']={k:j[k] for k in ('runtime','ownership','AESChecks','AESFailures','stack_usage','feedback') if k in j}
    (out/'work-unit-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    for load,w in result['windows'].items():
        print(load)
        for k,r in w['maxima'].items():print(k,round(r['charged_cpu_ms'],3),round(r['elapsed_ms'],3),list((x,round(v,3)) for x,v in r['exclusive_cpu_ms'].items())[:4])
        for k in ('actual_worker_turn','input_service_gap'):
            if k in w:print(k,round(w[k]['charged_cpu_ms'],3),round(w[k]['elapsed_ms'],3))

    return result


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('output',type=Path)
    args=a.parse_args();analyze(args.output)
