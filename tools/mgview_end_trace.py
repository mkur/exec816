"""Passive END_UPDATE journal, release and peer-Task attribution.

Resolve instruction boundaries in the frozen native image. No guest tracing
code, builds, synchronization or scheduling changes are introduced.
"""
from collections import defaultdict
import re

from aes_latency_trace import routine
from console_turn_profile import Timeline,analyze_events
from g4bench_trace import calls
from mgview_frame_trace import partition
from native_program import ROOT,require
from sio_transaction_trace import BASE_HZ,read_events


PREFIXES=('AESLOCKS_','AESWINDOWSTATE_','AESSNAPSHOT_','DESKCACHE_',
          'DESKCACHEWORK_','LAYERS_','LAYERCACHE_','REGIONS_','SCRENMGR_',
          'AESHOST_','AESCORE_','AESCURSOR_','AESMOUSE_','DESKINPUT_',
          'DESKDRAG_','AESINPUT_','CONSOLEBITMAP_','DISPLAY_')
KERNEL=('tasks_forbid','tasks_permit','tasks_signal','tasks_wait',
        'tasks_set_signal','exec_yield','semaphores_release','semaphores_obtain')
C_NAMES=('ExecAESContext','ExecAESLocal','_AESLocalCall','ConsoleBitmapEntry',
         'GemDrawingMouse','DisplayOwnerEnter','DisplayOwnerEnd')
PEER_PHASES={'AESHOST_SERVICE':'service_and_input_refresh',
             'DESKINPUT_PRESENT':'mouse_presentation',
             'DESKINPUT_INTERACTIONPENDING':'interaction_checks',
             'SCRENMGR_COLLECT':'signal_collection','tasks_wait':'wait'}
JOURNAL_PHASES={'AESWINDOWSTATE_PREPAREUPDATE':'change_preparation',
                'LAYERS_REQUIREPAINT':'invalidation',
                'LAYERS_PAINTED':'paint_completion',
                'DESKCACHE_ENDCHANGE':'existing_cache_completion',
                'DESKCACHEWORK_MAINTAIN':'cache_candidate_scan'}


def definition(program,foreign):
    decoder={'__name__':'end_decoder'}
    path=ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(),str(path),'exec'),decoder)
    labels={r['address']:r['name'].rsplit('_',1)[0][2:]
            for r in program['image']['routines'] if r['name'].startswith('M_')}
    labels.update({program['labels'][n]:n for n in KERNEL})
    entries={};returns=set();exits=set();sites={}
    for base,name in list(labels.items()):
        if not name.startswith(PREFIXES):continue
        _,raw=routine(program,name)
        listing=decoder['disassemble']({**program['image'],'version':3,
            'segments':[dict(address=base,executable=True,bytes=list(raw))]})
        entries[base]=name
        for line in listing.splitlines():
            match=re.match(r'^([0-9A-F]{6})\s+((?:[0-9A-F]{2} )+)\s*(.*)$',line)
            if not match:continue
            pc=int(match[1],16);code=bytes.fromhex(match[2])
            if code[0]==0x22:
                target=int.from_bytes(code[1:],'little');returns.add(pc+4)
                sites[pc]=dict(caller=name,target=labels.get(target,hex(target)))
            if code==b'\x6b':exits.add(pc)
    for name in KERNEL:
        entries[program['labels'][name]]=name
        exits.add(program['labels'][name+'_end']-1)
    for name in C_NAMES:
        require(name in foreign['symbols'],'Missing END binding boundary: '+name)
        entries[foreign['symbols'][name]]=name
    require('AESWINDOWSTATE_ENDUPDATE' in entries.values(),'Missing END journal')
    return dict(entries=entries,returns=sorted(returns),exits=sorted(exits),sites=sites,
                pcs=sorted(set(entries)|returns|exits|set(sites)))


def resource_stages(rows,start,end):
    """Disjoint semantic intervals; ownership ends at native Release's return."""
    def one(name):
        matches=[r for r in rows if r['kind']==name and start<=r['start']<r['end']<=end]
        require(len(matches)==1,'Expected one END stage: '+name)
        return matches[0]
    lock=one('AESLOCKS_CALL');release=one('AESLOCKS_RELEASE')
    journal=one('AESWINDOWSTATE_ENDUPDATE');handoff=one('AESLOCKS_RETURNRESOURCE')
    native=one('semaphores_release')
    points=[('binding_and_dispatch',start,lock['start']),
            ('lock_entry',lock['start'],release['start']),
            ('window_update_flags',release['start'],journal['start']),
            ('journal_and_cache',journal['start'],journal['end']),
            ('release_accounting',journal['end'],release['end']),
            ('snapshot_and_release_dispatch',release['end'],handoff['start']),
            ('notify_and_native_release',handoff['start'],native['end']),
            ('post_release_permit_and_return',native['end'],handoff['end']),
            ('binding_return',handoff['end'],end)]
    require(all(left<=right for _,left,right in points),'Out-of-order END stages')
    return [dict(kind=name,start=left,end=right) for name,left,right in points]


def charged_peers(segments,start,end,viewer,roles):
    """Count CPU and interrupt residency once, keeping peer IRQs separate."""
    charges=defaultdict(lambda:dict(charged_cpu_ms=0.,interrupt_ms=0.))
    for left,right,dp,interrupt in segments:
        left=max(start,left);right=min(end,right)
        if left>=right:continue
        key='interrupt_ms' if interrupt else 'charged_cpu_ms'
        charges[dp][key]+=(right-left)*1000/BASE_HZ
    return [dict(dp=dp,role=roles.get(dp,'other Task'),**charge)
            for dp,charge in sorted(charges.items()) if dp!=viewer]


def analyze(out,definition,audit):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={definition['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,definition['timeline'],include_segments=True)
    selected=definition['end_update'];viewer=audit['samples'][0]['viewer_dp']
    returns=set(definition['returns'])|set(selected['returns'])
    exits=set(definition['exits'])|set(selected['exits'])
    entries={**definition['entries'],**selected['entries']}
    roles={viewer:'MGVIEW',profile['worker_dp']:'SCRENMGR',
           definition['timeline']['task_dps'][0]:'test controller'}
    by_dp={dp:calls(events,entries,returns,dp,exits)[0]
           for dp in definition['timeline']['task_dps']}
    timeline=Timeline(profile['segments'],viewer);result=[]
    for sample in audit['samples']:
        end_call=[r for r in sample['spans'] if r['kind']=='wind_update']
        require(len(end_call)==1 and end_call[0]['argument']==0,'Expected one END_UPDATE')
        start,end=end_call[0]['start'],end_call[0]['end']
        rows=[dict(r,**timeline.measure(r['start'],r['end'])) for r in by_dp[viewer]
              if start<=r['start']<r['end']<=end]
        stages=resource_stages(rows,start,end)
        for stage in stages:stage.update(timeline.measure(stage['start'],stage['end']))
        measured=timeline.measure(start,end)
        for key in measured:
            require(abs(sum(s[key] for s in stages)-measured[key])<1e-6,
                    'END stage accounting does not reconcile: '+key)
        functions=defaultdict(list)
        for row in rows:functions[row['kind']].append(row)
        peers={}
        for dp,role in roles.items():
            if dp==viewer:continue
            t=Timeline(profile['segments'],dp)
            clipped=[r for r in by_dp[dp] if r['start']<end and start<r['end']]
            peers[role]=dict(dp=dp,measured=t.measure(start,end),
                exclusive_cpu_ms=partition(clipped,t,start,end,{r['kind']:r['kind'] for r in clipped}),
                phase_cpu_ms=partition([r for r in clipped if r['kind'] in PEER_PHASES],
                                       t,start,end,PEER_PHASES),
                spans=[dict(r,**t.measure(max(start,r['start']),min(end,r['end']))) for r in clipped])
        kernel=[dict(r,**timeline.measure(r['start'],r['end'])) for r in rows if r['kind'] in KERNEL]
        sites=[dict(tick=t,**selected['sites'][int(e[4],16)]) for t,e in events
               if start<=t<=end and int(e[9],16)==viewer and int(e[4],16) in selected['sites']
               and selected['sites'][int(e[4],16)]['target'] in KERNEL]
        release=next(r for r in rows if r['kind']=='semaphores_release')
        peer_charges=charged_peers(profile['segments'],start,end,viewer,roles)
        require(abs(sum(p['charged_cpu_ms']+p['interrupt_ms'] for p in peer_charges)
                    -measured['off_cpu_ms'])<1e-6,'END peer accounting does not reconcile')
        journal=next(r for r in rows if r['kind']=='AESWINDOWSTATE_ENDUPDATE')
        result.append(dict(action=sample['action'],start=start,end=end,
            measured=measured,stages=stages,
            journal_cpu_ms=partition([r for r in rows if r['kind'] in JOURNAL_PHASES],
                timeline,journal['start'],journal['end'],JOURNAL_PHASES),
            resource_release_tick=release['end'],
            before_resource_release=timeline.measure(start,release['end']),
            after_resource_release=timeline.measure(release['end'],end),
            peer_charges=peer_charges,
            peers_before_release=charged_peers(profile['segments'],start,release['end'],viewer,roles),
            peers_after_release=charged_peers(profile['segments'],release['end'],end,viewer,roles),
            peers=peers,kernel_calls=kernel,kernel_sites=sites,
            routines={n:dict(calls=len(v),**{k:sum(r[k] for r in v)
                for k in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')})
                for n,v in functions.items()},spans=rows))
    return dict(samples=result,scope='Final wind_update(END_UPDATE), synchronous caller journal and native release. Task CPU excludes interrupts and other Tasks; stages are disjoint. Native Release return is a conservative ownership-release boundary, not a hardware-store timestamp.')
