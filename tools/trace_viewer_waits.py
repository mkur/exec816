#!/usr/bin/env python3
"""Audit viewer waits, signal sources and supervisory work on a frozen demo."""
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
import json
import hashlib
from pathlib import Path
from unittest.mock import patch

from aes_timing_breakdown import scheduler_states
from bitmap_console_performance import native_markers
from gem_applications import instances
from g4bench_trace import native_calls
import measure_gui_baseline as viewer
from native_program import ROOT,read_build,require,sha256
from sio_transaction_trace import BASE_HZ,read_events
from text_performance_trace import extend_clock,timeline
from console_turn_profile import Timeline
from dos_concurrent_trace import call_marker
from text_performance_trace import sites
from terminal_model import FIELDS as TERMINAL_FIELDS,SESSION_FIELDS,SESSION_SIZE

NATIVE='''SHELLAPP_SHELLCONTROLLERSTEP SHELLAPP_SHELLCONTROLLERREQUESTS
SHELLAPP_SHELLCONTROLLERREADY SHELLAPP_SHELLCONTROLLERSELECTION
SHELLAPP_SHELLCONTROLLERCOLLECT SHELLAPP_SHELLSESSIONQUERYREPLY
SHELLAPP_DESKTOPWATCH SHELLAPP_DESKTOPSERVICE
SHELLAPP_SHELLREADSTEP DOSCLIENT_SERVICEWAIT PROCESS_COLLECT PROCESS_COMPLETIONMASK
TASKPOLICY_PROCESSOWNED TASKPOLICY_PROCESSFIND TASKPOLICY_PROCESSCHANGE
TASKPOLICY_POSTSIGNAL TASKPOLICY_SIGNALTASK AESGATE_ENTERTASK AESGATE_RELEASE
AESGATE_WAKECALLERS AESLOCAL_CALL AESWAIT_SIGNAL DISPLAY_ENTER DISPLAY_OWNERWAKE
DISPLAY_RELEASE AESINBOX_WAKE PROCESS_PUBLISHSETUP TASKPOLICY_PROCESSREMOVED'''.split()


def image_bytes(p,start,end):
    for segment in p['image']['segments']:
        offset=start-segment['address']
        if 0<=offset and offset+end-start<=len(segment['bytes']):
            return bytes(segment['bytes'][offset:offset+end-start])
    raise RuntimeError('Missing observer bytes')


def atomic_markers(p):
    """Check existing atomic instructions; all offsets are matched to bytes."""
    result={};spans={}
    for kind,label in (('signal','signal_change'),('wait','signal_wait_begin'),('complete','signal_wait_complete')):
        start,end=p['labels'][label],p['labels'][label+'_end'];raw=image_bytes(p,start,end)
        require(raw[-3:]==bytes.fromhex('2b986b'),'Unknown atomic return')
        spans[kind]=dict(entry=start,returns=[end-1])
        # Match complete LDA/STA instruction pairs from atomic_task_argument
        # or atomic_context_task, including this build's linked context table.
        table=p['build']['task_storage']['BASE']+p['build']['task_storage']['TCB_ITEM']
        patterns=dict(target_low=('bf'+table.to_bytes(3,'little').hex()+'8501',4),
            target_high=('bf'+(table+2).to_bytes(3,'little').hex()+'8503',4))
        if kind=='signal':patterns.update(target_low=('a5128501',2),target_high=('a5148503',2),
            old_low=('b7018505',2),old_high=('b7018507',2),
            xor_low=('4516251a',2),xor_high=('4518251c',2),
            new_low=('45059701',2),new_high=('45079701',2))
        if kind=='wait':patterns.update(mask_low=('a5169701',2),mask_high=('a5189701',2))
        for name,(hexbytes,offset) in patterns.items():
            needle=bytes.fromhex(hexbytes);hits=[i for i in range(len(raw)-len(needle)+1) if raw[i:i+len(needle)]==needle]
            require(len(hits)==1,'Ambiguous atomic observer '+kind+'/'+name)
            pc=start+hits[0]+offset
            result[kind+'_'+name]=pc
    return dict(points=result,spans=spans)


def prepare(bundle):
    p=read_build(bundle);d=viewer_prepare(bundle)
    spans=native_markers(p,[(n,n) for n in NATIVE])
    require(set(spans)==set(NATIVE),'Missing audit routine')
    retry=call_marker(p,'M_SHELLAPP_SHELLCONTROLLERRUN_','exec_yield')
    spans['controller_retry_yield']=dict(entry=retry,returns=[retry+4])
    atom=atomic_markers(p)
    # Sparse companion: scheduler, waits and native supervisory/admission scopes.
    pcs=set(d['points'][k] for k in ('native_irq','native_nmi','interrupt_schedule','selected'))
    pcs.update(d['scheduler']['points'].values());pcs.update(atom['points'].values())
    for m in [*spans.values(),*atom['spans'].values()]:pcs.update([m['entry'],*m['returns']])
    folder=bundle/'bitmap-console/apps/terminal';app=json.loads((folder/'app.json').read_text())
    local={pc:s for pc,s in sites(folder,app['image'],{n:'terminal' for n in
        ('TerminalPlatformRefresh','TerminalPlatformWait','ExecAESWait','exchange')}).items() if s['category']=='terminal'}
    for pc,s in local.items():
        for bank in p['build']['memory']['usable_banks']:pcs.update(((bank<<16)|(pc&65535),(bank<<16)|(s['end']&65535)))
    d.update(pcs=sorted(pcs),audit_spans=spans,atomic=atom,terminal_sites=local,
        terminal_reference=app['abi']['link_bank']<<16,audit_observer_sha256=sha256(Path(__file__)))
    return d


def roster(s,label):
    """Read only while the debugger is stopped; retain live incarnation names."""
    t=s.p['build']['task_storage'];process=json.loads((ROOT/'abi/process.json').read_text())
    fields={f[0]:f[2] for f in process['record']}
    table=next(d for d in s.p['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
    raw=s.far(table['address'],table['size']);apps={a['task']:a for a in instances(s.b,s.p,s.directory)}
    names={r['address']:r['name'] for r in s.p['image']['routines']};rows=[]
    for slot,pool in enumerate(s.p['build']['memory']['task_pools']):
        ctx=t['BASE']+slot*t['SIZE'];task=s.number(ctx+t['TCB_ITEM'],3)
        if not task:continue
        record=dict(slot=slot,dp=pool['dp'],task=task,state=s.number(task+t['TASK_TC_STATE'],1),
            received=s.number(task+t['TASK_TC_SIGRECVD']),waiting=s.number(task+t['TASK_TC_SIGWAIT']),
            forbid=s.number(task+t['TASK_TC_TDNESTCNT'],1),entry=names.get(s.number(ctx+t['TCB_ENTRY'],3),'?'))
        if task in apps:
            app=apps[task]
            record.update(name=app['name'],identity=app['identity'],image_base=app['base'])
            if app['name']=='terminal':
                at=s.number(app['symbols']['GEMTerminal'])
                record['terminal_paints']=s.number(at+TERMINAL_FIELDS['paints'])
                record['terminal_cells_sha256']=hashlib.sha256(b''.join(s.far(
                    at+TERMINAL_FIELDS['sessions']+i*SESSION_SIZE+SESSION_FIELDS['cells'],1280)
                    for i in range(4))).hexdigest()
        for i in range(0,len(raw)-4,process['record_bytes']):
            row=raw[i:i+process['record_bytes']]
            if not row[fields['state']] or table['address']+i+fields['task']!=task:continue
            value=lambda name,size=4:int.from_bytes(row[fields[name]:fields[name]+size],'little')
            record.update(process_identity=value('identity'),completion_mask=value('mask'),parent=value('owner',3),
                process_entry=names.get(value('entry',3),'loaded program'))
            if record['process_entry'].startswith('M_SHELLAPP_SHELLPROCESSENTRY_'):record['name']='shell session'
        if slot==0:record['name']='shell controller'
        if slot==len(s.p['build']['memory']['task_pools'])-1:record['name']='idle'
        record.setdefault('name',record['entry'])
        rows.append(record)
    result=dict(label=label,clock=s.b.eval_expr('@clk'),tasks=rows,
        shortcut_mask=s.number(s.at('shortcutMask')),controller_retry=s.number(s.at('controllerRetry'),1))
    s.report.setdefault('audit_rosters',[]).append(result)
    s.report['inputs']['tools/trace_viewer_waits.py']=sha256(Path(__file__))
    return result


def atomic_events(events,definition,selected):
    entries={m['entry']:kind for kind,m in definition['spans'].items()}
    returns={m['returns'][0]:kind for kind,m in definition['spans'].items()}
    fields={pc:tuple(name.split('_',1)) for name,pc in definition['points'].items()}
    active={};rows=[];owner=None
    for tick,e in events:
        pc,a,x,sp,dp=(int(e[i],16) for i in (4,5,6,8,9))
        if pc==selected:owner=dp
        if pc in entries:
            kind=entries[pc];require(kind not in active,'Overlapping atomic call')
            active[kind]=dict(kind=kind,start=tick,stack=sp,entry_dp=dp,source_dp=owner)
        if pc in fields:
            kind,field=fields[pc];require(kind in active,'Atomic field without entry')
            active[kind][field]=a&255 if field=='target_high' else a
        if pc in returns:
            kind=returns[pc];require(kind in active,'Atomic return without entry')
            row=active.pop(kind);require(row['stack']==sp,'Atomic stack mismatch')
            row.update(end=tick,result=a|(x<<16),target=row['target_low']|(row['target_high']<<16))
            if kind=='signal':
                row['bits']=(row['xor_low']^row['old_low'])|((row['xor_high']^row['old_high'])<<16)
                if 'new_low' in row:row['new_received']=row['new_low']|(row['new_high']<<16)
            if kind=='wait' and not row['result']:
                row['mask']=row['mask_low']|(row['mask_high']<<16)
            rows.append(row)
    require(not active,'Incomplete atomic trace')
    return rows


def ready_episodes(changes,selections,end):
    """Repeated READY publication does not begin another scheduling interval."""
    for i,(tick,state) in enumerate(changes):
        if state!='ready' or (i and changes[i-1][1]=='ready'):continue
        j=bisect_right(selections,tick)
        stop=selections[j] if j<len(selections) else end
        previous=changes[i-1][1] if i else 'unknown'
        cause={'blocked':'after wait','selected':'preemption/reschedule'}.get(previous,'initial/unknown')
        yield tick,stop,cause


def analyze(out,d,r):
    events=read_events(out/'cpu-trace.log',kinds={'cpu'})
    while events and int(events[-1][1][4],16) in (d['points']['native_irq'],d['points']['native_nmi']):events.pop()
    segments=timeline(events,d['points']);states,selections=scheduler_states(events,d['scheduler'],d['points']['selected'])
    worker=next(t['dp'] for t in r['audit_rosters'][0]['tasks'] if t.get('name')=='text')
    samples=[{**s,**{k:extend_clock(s[k],events[0][0]) for k in ('start','model','first_band','complete')}} for s in r['samples']]
    windows=[(s['start'],s['complete']) for s in samples]
    inside=lambda t:any(a<=t<b for a,b in windows)
    roles={t['task']:t for snap in r['audit_rosters'] for t in snap['tasks']}
    bydp={t['dp']:t for t in roles.values()};clock=Timeline(segments,worker)
    marks=dict(d['audit_spans'])
    term=next(t for t in roles.values() if t['name']=='terminal')
    terminal_sites={}
    if 'terminal_sites' in d:
        delta=term['image_base']-d['terminal_reference']
        for pc,site in d['terminal_sites'].items():
            name='terminal:'+site['callee']+':'+str(pc)
            marks[name]=dict(entry=int(pc)+delta,returns=[site['end']+delta])
            terminal_sites[name]=site['callee']
    spans=native_calls(events,marks);atom=atomic_events(events,d['atomic'],d['points']['selected'])
    clocks={worker:clock}
    def charged(span,dp):
        if dp not in clocks:clocks[dp]=Timeline(segments,dp)
        return clocks[dp].measure(span['start'],span['end'])['charged_cpu_ms']
    # Publish per-peer CPU and IRQ separately; off-CPU time is not all peer work.
    changes=states[worker];ticks=[t for t,_ in changes];cost=defaultdict(float)
    for begin,end in windows:
        for a,b,dp,irq in segments:
            lo,hi=max(a,begin),min(b,end)
            if hi<=lo:continue
            i=bisect_right(ticks,lo)-1
            state='unknown' if i<0 else ('blocked' if changes[i][1]=='blocked' else 'runnable')
            cost[dp,'viewer' if dp==worker else state,'irq' if irq else 'cpu']+=hi-lo
    scope_cost=defaultdict(lambda:dict(calls=0,cpu_ms=0))
    for span in spans:
        if not any(a<=span['start']<span['end']<=b for a,b in windows):continue
        dp=span['dp']
        if dp not in bydp:continue
        row=scope_cost[dp,span['kind']];row['calls']+=1;row['cpu_ms']+=charged(span,dp)
    completions=defaultdict(list)
    for a in atom:
        if a['kind']=='complete':completions[a['target']].append(a)
    completion_ticks={task:[a['start'] for a in rows] for task,rows in completions.items()}
    def completion_for(row):
        rows=completions[row['target']];ticks=completion_ticks.get(row['target'],[])
        i=bisect_right(ticks,row['end'])
        return rows[i] if i<len(rows) else None
    posts=[];waits=[];updates=[]
    for row in atom:
        if row['kind']=='wait':
            complete=None if row['result'] else completion_for(row)
            end=complete['end'] if complete else row['end']
            if not any(row['start']<b and end>a for a,b in windows):continue
        elif row['kind']!='signal' or not inside(row['start']):continue
        enclosing=[s for s in spans if s['start']<=row['start']<row['end']<=s['end']
            and s['dp'] in (row['source_dp'],row['entry_dp'])]
        row={**row,'scopes':[s['kind'] for s in sorted(enclosing,key=lambda s:s['end']-s['start'])]}
        if row['kind']=='signal' and inside(row['start']):
            updates.append(row)
            if 'TASKPOLICY_POSTSIGNAL' in row['scopes']:posts.append(row)
        elif row['kind']=='wait':waits.append(row)
    for row in waits:
        row['role']=roles.get(row['target'],{}).get('name','?')
        if row['result']:continue
        completion=completion_for(row)
        if not completion:continue
        row.update(completed=completion['end'],returned_bits=completion['result'])
        selected=next((t for t in selections[roles[row['target']]['dp']] if t>=completion['end']),None)
        if selected is not None:row['selected']=selected
        dp=roles[row['target']]['dp'];ready=next((t for t,state in states[dp] if state=='ready' and row['start']<=t<=completion['start']),None)
        if ready is not None:
            row.update(ready=ready,blocked_ms=(ready-row['start'])*1000/BASE_HZ,
                ready_to_completion_ms=(completion['end']-ready)*1000/BASE_HZ)
        row['matching_posts']=[p for p in posts if p['target']==row['target'] and p['bits']&row['mask'] and row['start']<=p['start']<=completion['start']]
    waits=[w for w in waits if inside(w['start']) or any(w['start']<b and w.get('selected',w.get('completed',w['end']))>a for a,b in windows)]
    wait_summary=[]
    for task,role in roles.items():
        selected=[w for w in waits if w['target']==task];completed=[w for w in selected if 'completed' in w]
        if not selected:continue
        wait_summary.append(dict(name=role['name'],dp=role['dp'],calls=len(selected),
            immediate=sum(w['result']!=0 for w in selected),blocked=len(completed),
            masks=dict(Counter(hex(w['mask']) for w in completed)),
            immediate_bits=dict(Counter(hex(w['result']) for w in selected if w['result'])),
            returned_bits=dict(Counter(hex(w['returned_bits']) for w in completed)),
            sources=dict(Counter((bydp.get(p['source_dp'],{}).get('name','?')+' / '+
                next((s for s in p['scopes'] if s not in ('TASKPOLICY_POSTSIGNAL','TASKPOLICY_SIGNALTASK')),'direct'))
                for w in completed for p in w['matching_posts']))))
    budget=defaultdict(lambda:dict(episodes=0,blocked_off_cpu_ms=0,ready_off_cpu_ms=0))
    for w in waits:
        if w['target']!=r['app']['task'] or 'ready' not in w:continue
        if 'AESGATE_ENTERTASK' in w['scopes']:reason='scene admission'
        elif 'DISPLAY_ENTER' in w['scopes']:reason='display admission'
        elif 'AESLOCAL_CALL' in w['scopes']:reason='UPDATE/window admission'
        elif any('AESINBOX_WAKE' in p['scopes'] for p in w['matching_posts']):reason='input/events'
        else:reason='unresolved'
        row=budget[reason];row['episodes']+=1
        for a,b in windows:
            lo,hi=max(a,w['start']),min(b,w['ready'])
            if hi>lo:row['blocked_off_cpu_ms']+=clock.measure(lo,hi)['off_cpu_ms']
            lo,hi=max(a,w['ready']),min(b,w.get('selected',w['completed']))
            if hi>lo:row['ready_off_cpu_ms']+=clock.measure(lo,hi)['off_cpu_ms']
    terminal_calls=[dict(s,callee=terminal_sites[s['kind']]) for s in spans if s['kind'] in terminal_sites
        and s['dp']==term['dp'] and any(a<=s['start']<s['end']<=b for a,b in windows)]
    feedback={}
    if terminal_calls:
        reply_masks={p['bits'] for p in posts if p['target']==term['task']
            and 'SHELLAPP_SHELLSESSIONQUERYREPLY' in p['scopes']}
        require(len(reply_masks)==1,'Missing unique Terminal query-reply signal')
        reply_mask=reply_masks.pop()
        waits_c=[s for s in terminal_calls if s['callee']=='ExecAESWait']
        exchanges=[s for s in terminal_calls if s['callee']=='exchange']
        clears=[u for u in updates if u['target']==term['task'] and u['source_dp']==term['dp']
            and u['bits']==0 and u['result']&reply_mask and not(u.get('new_received',reply_mask)&reply_mask)
            and any(s.startswith('terminal:ExecAESWait:') for s in u['scopes'])]
        feedback=dict(reply_mask=reply_mask,events=dict(Counter(hex(s['return_a']) for s in waits_c)),
            completed_event_calls=len(waits_c),successful_exchanges=sum(s['return_a']!=0 for s in exchanges),
            exchanges_without_wait=sum(not any(w['target']==term['task'] and s['start']<=w['start']<w['end']<=s['end']
                for w in waits) for s in exchanges),cleared_reply_bit_in_event_wait=len(clears),
            controller_retry_yields=sum(s['calls'] for (dp,name),s in scope_cost.items() if name=='controller_retry_yield'))
        chains=0
        for w in waits_c:
            if not w['return_a']&0x8000:continue
            prior=max((s for s in exchanges if s['end']<=w['start']),key=lambda s:s['end'],default=None)
            if prior is None:continue
            if any(x['target']==term['task'] and prior['start']<=x['start']<x['end']<=prior['end'] for x in waits):continue
            reply=any(p['target']==term['task'] and 'SHELLAPP_SHELLSESSIONQUERYREPLY' in p['scopes']
                and prior['start']<=p['start']<p['end']<=prior['end'] for p in posts)
            clear=any(w['start']<=u['start']<u['end']<=w['end'] for u in clears)
            if reply and clear:chains+=1
        feedback['fully_contained_feedback_chains']=chains
        feedback['event_calls_without_contained_prior_exchange']=sum(bool(w['return_a']&0x8000) for w in waits_c)-chains
    ready_budget=defaultdict(lambda:dict(episodes=0,off_cpu_ms=0))
    for tick,end,cause in ready_episodes(changes,selections[worker],clock.ticks[-1]):
        value=0
        for a,b in windows:
            lo,hi=max(tick,a),min(end,b)
            if hi>lo:value+=clock.measure(lo,hi)['off_cpu_ms']
        if value:
            ready_budget[cause]['episodes']+=1;ready_budget[cause]['off_cpu_ms']+=value
    expected=sum(v for (dp,state,kind),v in cost.items() if dp!=worker and state=='runnable')*1000/BASE_HZ
    require(abs(sum(r['off_cpu_ms'] for r in ready_budget.values())-expected)<0.000001,
        'Ready episode attribution does not reconcile')
    result=dict(status='pass',tier='development',qualification=False,scope=__doc__,viewer_dp=worker,rosters=r['audit_rosters'],
        per_action=[dict(dp=dp,role=bydp.get(dp,{}).get('name','?'),viewer_state=state,kind=kind,
            mean_ms=value/len(samples)*1000/BASE_HZ) for (dp,state,kind),value in sorted(cost.items(),key=lambda x:-x[1])],
        native_scopes=[dict(dp=dp,role=bydp[dp]['name'],scope=name,**value) for (dp,name),value in scope_cost.items()],
        wait_summary=wait_summary,waits=waits,posts=posts,signal_updates=updates,samples=samples,
        terminal_calls=terminal_calls,feedback=feedback,viewer_wait_budget=dict(budget),ready_episode_budget=dict(ready_budget),
        capture_observer_sha256=d['audit_observer_sha256'],analyzer_sha256=sha256(Path(__file__)),
        trace_sha256=sha256(out/'cpu-trace.log'))
    (out/'wait-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Audit waits:',json.dumps(wait_summary),flush=True)
    return dict(audit='wait-audit.json',viewer_dp=worker)


viewer_prepare=viewer.prepare
viewer_pixels=viewer.pixels

def pixels(s,app,label):
    result=viewer_pixels(s,app,label);roster(s,label)
    if label=='initial':
        stop=s.b.profile_stop
        def dump():
            result=stop()
            (s.out/'instruction-profile.json').write_text(json.dumps(s.b.profile_dump(top=5000),indent=2)+'\n')
            return result
        s.b.profile_stop=dump
        (s.out/'wait-observer.py').write_text(Path(__file__).read_text())
    return result


def run(bundle,out,count,load,observe):
    with patch.object(viewer,'prepare',prepare),patch.object(viewer,'pixels',pixels),patch.object(viewer,'analyze',analyze):
        return viewer.run(bundle,out,count,load,observe)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=4)
    parser.add_argument('--load',type=Path)
    parser.add_argument('--observe',action='store_true')
    parser.add_argument('--analyze-only',action='store_true')
    args=parser.parse_args()
    if args.analyze_only:
        out=args.output.resolve();r=json.loads((out/'results.json').read_text());d=json.loads((out/'text-performance-markers.json').read_text())
        analyze(out,d,r)
    else:
        run(args.bundle.resolve(),args.output.resolve(),args.count,args.load.resolve() if args.load else None,args.observe)
