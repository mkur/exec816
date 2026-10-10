"""Passive call-site and scheduler attribution for the loaded text viewer."""
import json
import re
from bisect import bisect_right
from collections import defaultdict

from aes_timing_breakdown import scheduler_markers, scheduler_states
from console_turn_profile import Timeline
from native_program import read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events

CATEGORIES={
    'format': 'TextRow',
    'load': 'TextStep',
    'dos': 'Read Open Close',
    'event': 'evnt_multi',
    'update': 'wind_update',
    'geometry': 'wind_get wind_set vs_clip',
    'vdi': 'v_gtext v_bar text paint',
    'borrow': 'GemDrawingBorrow DisplayEnter DisplayLeave',
    'renderer': 'GemVdiPaint vdi_v_gtext dev_glyph dev_fill_rect draw_glyph draw_glyph_clipped',
    'builder': 'blit_glyph blit_glyph_run glyph_record blit_mask',
    'upload': 'VbxeOwnerSubmit VbxeOwnerText VbxeOwnerTextFill _VbxeTextUpload launch submit',
    'staging': 'vram_win VbxeOwnerRead VbxeOwnerWrite transfer',
    'fence': 'VbxeOwnerFence fence_owner idle',
    'arithmetic': '_Mul16 _Mul32 _Div16 _UDivMod16 _UDivMod32 _SDivMod16 _SDivMod32',
}


def sites(folder, image):
    """Resolve full emitted sections; static symbol names are not unique."""
    targets={name:category for category,names in CATEGORIES.items() for name in names.split()}
    result={}
    public_names={name for path in folder.glob('*.lst') for name in
            re.findall(r'\.public (\w+)',path.read_text())}
    for path in folder.glob('*.lst'):
        if path.name=='link.lst':continue
        for section in path.read_text().replace('\r\n','\n').split('.section ')[1:]:
            if not section.startswith('farcode,text'):continue
            calls=[(int(m[1],16),m[2]) for m in re.finditer(
                r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:(\w+)\s*$',section,re.M) if m[2] in targets]
            if not calls:continue
            code={}
            for m in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',section):
                for i in range(0,len(m[2]),2):code[int(m[1],16)+i//2]=m[2][i:i+2]
            require(set(code)==set(range(max(code)+1)),'Incomplete text performance section')
            # Relocations remain wildcards except known public callees.
            # Without these operands, tiny tail/call wrappers can match a
            # different function and falsely attribute work to its callee.
            for offset,name in calls:
                if name in public_names and name in image['symbols']:
                    for i,value in enumerate(image['symbols'][name].to_bytes(3,'little')):
                        code[offset+1+i]=f'{value:02x}'
            pattern=b''.join(b'.' if code[i]=='..' else re.escape(bytes.fromhex(code[i])) for i in range(len(code)))
            locations=[s['address']+m.start() for s in image['segments'] if s['executable']
                       for m in re.finditer(pattern,bytes(s['bytes']),re.S)]
            public=re.search(r'\.public (\w+)',section)
            require(locations or public is None or public[1] not in image['symbols'],
                    'Missing linked performance section '+str(path))
            for base in locations:
                for offset,name in calls:
                    result[base+offset]=dict(end=base+offset+4,category=targets[name],callee=name,listing=path.name)
    require(result,'No text performance call sites')
    return result


def prepare(out):
    p=read_build(out);directory=out/'bitmap-console'
    foreign=json.loads((directory/'c-image.json').read_text())
    app=json.loads((directory/'apps/text/app.json').read_text())
    shared=sites(directory/'drawing',foreign);local=sites(directory/'apps/text',app['image'])
    scheduler=scheduler_markers(p)
    address=p['labels']['context_restore']
    hosted=(p['output']/'hosted.bin').read_bytes()
    require(hosted[address-0x1400:address-0x1400+8]==bytes.fromhex('c230ab2b7afa6840'),
            'Unknown restore boundary')
    points={k:p['labels'][k] for k in ('native_irq','native_nmi','interrupt_schedule')}
    points['selected']=address+4
    points.update(scheduler['points'])
    from bitmap_console_performance import markers as hardware_markers
    hardware=hardware_markers(p,foreign,directory/'drawing')
    points['dma_launch']=hardware['launch']['entry']
    points['dma_idle']=hardware['idle']['entry']
    pcs=set(points.values())
    for pc,site in shared.items():pcs.update((pc,site['end']))
    # APP code is bank aligned. Observe candidate banks, then admit only the
    # actual retained Process relocation and Task in the analysis.
    for pc,site in local.items():
        for bank in p['build']['memory']['usable_banks']:
            pcs.update(((bank<<16)|(pc&65535),(bank<<16)|(site['end']&65535)))
    record=dict(shared=shared,local=local,points=points,scheduler=scheduler,
                reference=app['abi']['link_bank']<<16,pcs=sorted(pcs))
    (out/'text-performance-markers.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def timeline(events,points):
    owner=None;interrupts=[];segments=[];previous=events[0][0];last=None
    for tick,e in events:
        if e[0]!='cpu':continue
        if tick>previous:segments.append((previous,tick,owner,bool(interrupts)))
        previous=tick;pc,dp,sp=(int(e[i],16) for i in (4,9,8))
        if pc in (points['native_irq'],points['native_nmi']):
            frame=sp-9
            if not (interrupts and interrupts[-1]==frame and last==e[4:]):interrupts.append(frame)
        elif pc==points['interrupt_schedule']:
            require(interrupts and interrupts.pop()==sp,'Unbalanced performance interrupt')
        elif pc==points['selected']:
            require(not interrupts,'Performance selection inside interrupt');owner=dp
        last=e[4:]
    require(not interrupts,'Incomplete performance interrupt')
    return segments


def analyze(out,definition,record):
    trace=out/'emulator.log'
    require(trace.stat().st_size<256*1024*1024,'Performance trace exceeded 256 MiB cap')
    events=read_events(trace,kinds={'cpu'})
    segments=timeline(events,definition['points'])
    states,_=scheduler_states(events,definition['scheduler'],definition['points']['selected'])
    relocated=record['app']['base']-definition['reference']
    local={int(pc)+relocated:{**v,'end':v['end']+relocated} for pc,v in definition['local'].items()}
    all_sites={**{int(k):v for k,v in definition['shared'].items()},**local}
    owners={int(e[9],16) for _,e in events if int(e[4],16) in local and
            local[int(e[4],16)]['callee']=='TextRow'}
    require(len(owners)==1,'Missing unique viewer Task');worker=owners.pop()
    clock=Timeline(segments,worker);active=[];spans=[];last=None
    for tick,e in events:
        if e[0]!='cpu' or int(e[9],16)!=worker:continue
        pc,sp,a=(int(e[i],16) for i in (4,8,5))
        if active and pc==active[-1]['return_pc'] and sp==active[-1]['stack']:
            spans.append(dict(active.pop(),end=tick))
        if pc in all_sites:
            site=all_sites[pc]
            active.append(dict(start=tick,return_pc=site['end'],stack=sp,argument=a,
                               category=site['category'],callee=site['callee'],depth=len(active)))
        last=e
    require(not active,'Incomplete viewer call-site stack: '+str(active[-2:]))
    changes=states[worker];ticks=[t for t,_ in changes]
    # Launch through the return of the next synchronous idle poll bounds DMA
    # occupancy. It includes CPU/scheduling delay and is not a BUSY-edge clock.
    hardware=[(tick,'launch',int(e[9],16)) for tick,e in events
              if int(e[4],16)==definition['points'].get('dma_launch')]
    hardware += [(s['end'],'idle',worker) for s in spans if s['callee']=='idle']
    transfers=[];launch=None
    for tick,kind,dp in sorted(hardware):
        if kind=='launch' and dp==worker:
            require(launch is None,'Overlapping viewer blitter launch')
            launch=tick
        elif kind=='idle' and launch is not None:
            transfers.append((launch,tick));launch=None
    results=[]
    samples=list(record['samples'])
    if any(s['callee']=='TextStep' for s in spans):
        samples.insert(0,dict(operation='cold_load',index=0,
            start=record['start_load_observation'],complete=record['load_settled_observation']))
    for sample in samples:
        begin,end=sample['start'],sample['complete']
        if sample['operation']=='cold_load':begin=max(begin,clock.ticks[0],changes[0][0])
        selected=[s for s in spans if begin<=s['start']<s['end']<=end]
        boundaries=sorted({begin,end,*(t for s in selected for t in (s['start'],s['end']))})
        buckets=defaultdict(float)
        for a,b in zip(boundaries,boundaries[1:]):
            enclosing=[s for s in selected if s['start']<=a<b<=s['end']]
            category=max(enclosing,key=lambda s:s['depth'])['category'] if enclosing else 'viewer_other'
            buckets[category]+=clock.measure(a,b)['charged_cpu_ms']
        total=clock.measure(begin,end)
        require(abs(sum(buckets.values())-total['charged_cpu_ms'])<1e-7,'Viewer CPU does not reconcile')
        waiting=runnable=0
        for a,b,owner,_ in segments:
            lo,hi=max(a,begin),min(b,end)
            if hi<=lo or owner==worker:continue
            i=bisect_right(ticks,lo)-1;require(i>=0,'No viewer wait state')
            if changes[i][1]=='blocked':waiting+=hi-lo
            else:runnable+=hi-lo
        total.update(blocked_off_cpu_ms=waiting*1000/BASE_HZ,runnable_off_cpu_ms=runnable*1000/BASE_HZ)
        require(abs(total['off_cpu_ms']-total['blocked_off_cpu_ms']-total['runnable_off_cpu_ms'])<1e-7,'Viewer wait totals disagree')
        byname=defaultdict(list)
        for s in selected:byname[s['callee']].append(s)
        routines={k:dict(calls=len(v),charged_cpu_ms=sum(clock.measure(s['start'],s['end'])['charged_cpu_ms'] for s in v),
                        elapsed_ms=sum(s['end']-s['start'] for s in v)*1000/BASE_HZ) for k,v in byname.items()}
        updates=[];beg=None
        for s in byname['wind_update']:
            if s['argument']==1:beg=s
            elif s['argument']==0 and beg:
                updates.append(dict(acquire_ms=(beg['end']-beg['start'])*1000/BASE_HZ,
                                    hold_ms=(s['end']-beg['end'])*1000/BASE_HZ));beg=None
        counts=[s['argument'] for s in byname['VbxeOwnerSubmit']]
        require(byname['TextRow'] and byname['v_gtext'] and byname['GemDrawingBorrow'],
                'Missing viewer drawing markers')
        dma=[(a,b) for a,b in transfers if begin<=a<b<=end]
        work=dict(dma_launch_to_idle_return_ms=[(b-a)*1000/BASE_HZ for a,b in dma],
                  rows=len(byname['TextRow']),text_calls=len(byname['v_gtext']),
                  bar_calls=len(byname['v_bar']),borrows=len(byname['GemDrawingBorrow']),
                  submissions=len(counts),records_per_list=counts,
                  fences=len(byname['VbxeOwnerFence']),staging_windows=len(byname['vram_win']),
                  staging_read_bytes=4096*len(byname['VbxeOwnerRead']),
                  staging_write_bytes=4096*len(byname['VbxeOwnerWrite']))
        result=dict(operation=sample['operation'],index=sample['index'],work=work,**total,
                    exclusive_cpu_ms=dict(buckets),routines=routines,updates=updates)
        text=byname['v_gtext']
        if text:result['first_text_return_ms']=(text[0]['end']-begin)*1000/BASE_HZ
        results.append(result)
    result=dict(scope='Checked call/return sites; conservative Task CPU, IRQ/NMI and observed signal-wait attribution. First text return follows the synchronous fence; scanout is separate.',
                viewer_dp=worker,records=results,trace_bytes=trace.stat().st_size,trace_sha256=sha256(trace))
    (out/'text-performance-breakdown.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
