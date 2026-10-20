"""Passive S samples at emitted entries and frame reservations, grouped by lifetime."""
from collections import defaultdict
from pathlib import Path
import json,re
from c_program import ABI
from program_image_layout import LAYOUT as IMAGE_LAYOUT,FIELDS as IMAGE_FIELDS
from native_program import require


def markers(program,app):
    points={}
    resident=json.loads((program['output'].parent/'c-image.json').read_text())
    public={'ExecProgramRun','_DOSCall',*ABI['imports']}
    def entries(image,prefix,delta=0,application=False):
        executable=[s for s in image['segments'] if s['executable']]
        for name,pc in image['symbols'].items():
            if name.startswith('?') or (application and name in ABI['imports']):continue
            if not application and name not in public:continue
            if any(s['address']<=pc<s['address']+len(s['bytes']) for s in executable):
                points.setdefault(pc+delta,prefix+name)
    def frames(image,directory,prefix,delta=0):
        for obj in image['provenance']['link_objects']:
            listing=Path(obj).with_suffix('.lst')
            if not listing.exists():continue
            name=None;base=0
            for line in listing.read_text(errors='replace').splitlines():
                if '.section ' in line:name=None
                label=re.search(r'\\ ([0-9a-f]{6})\s+(?:[0-9a-f.]+\s+)?(`?[^\s:`]+`?):',line)
                if label and name is None and label[2].strip('`') in image['symbols']:
                    name=label[2].strip('`');base=image['symbols'][name]-int(label[1],16)
                at=re.search(r'\\ ([0-9a-f]{6}) 1b\s+tcs',line)
                if at and name:points.setdefault(base+int(at[1],16)+1+delta,prefix+name+':after-tcs')
    entries(resident,'provider:')
    frames(resident,program['output'].parent/'drawing','provider:')
    for routine in program['image']['routines']:
        if routine['name'].startswith(('M_PROCESS_RUN_','M_PROCESS_FINISH_',
                'M_DOSCLIENT_','M_DOSCALLS_','M_HEAP_','M_HEAPCORE_',
                'M_TASKPOLICY_PROCESS')):
            points[routine['address']]=routine['name']
    # An APP cannot occupy resident storage. Exclude those bases, so candidate
    # relocation markers cannot masquerade as a different resident routine.
    occupied=[(s['address'],s['address']+len(s['bytes'])) for im in (program['image'],resident) for s in im['segments']]
    for bank in app['verified_banks']:
        low=bank*65536;high=low+app['span']
        if any(low<b and a<high for a,b in occupied):continue
        delta=(bank-ABI['link_bank'])*65536
        entries(app['image'],'app:',delta,True)
        frames(app['image'],program['output'].parent/'app','app:',delta)
    for name in ('native_irq','native_nmi','cop_handler','context_restore'):
        if name in program['labels']:points[program['labels'][name]]=name
    return points


def summarize(path,points,memory,window=None):
    pools=list(enumerate(memory['task_pools']));rows={};lifetimes=defaultdict(int);runs={}
    low,high=memory['regions']['kernel-stack']
    pools.append(('kernel',dict(stack_base=low+16,stack_bytes=high-low-32)))
    with path.open() as source:
        for line in source:
            match=re.search(r'\[(?:SIOPOC|SIOTXN)\] cpu (.*)',line)
            if not match:continue
            fields=match[1].split();pc,s,dp=(int(fields[i],16) for i in (3,7,8))
            if pc not in points:continue
            owner=next(((n,p) for n,p in pools if p['stack_base']<=s<p['stack_base']+p['stack_bytes']),None)
            if owner is None:continue
            slot,pool=owner;name=points.get(pc,'unknown')
            if name.startswith('M_PROCESS_RUN_'):
                lifetimes[slot]+=1
                runs[slot,lifetimes[slot]]=dict(slot=slot,ordinal=lifetimes[slot],dp=dp,clock=int(fields[0]))
            if name=='app:main' and (slot,lifetimes[slot]) in runs:
                runs[slot,lifetimes[slot]]['app_entry']=pc
            kind='async' if name in ('native_irq','native_nmi','context_restore') else ('frame-reservation' if name.endswith(':after-tcs') else 'ordinary-sample')
            key=f'{slot}:{lifetimes[slot]}:{kind}'
            if key not in rows or s<rows[key]['minimum_s']:
                rows[key]=dict(slot=slot,lifetime=lifetimes[slot],kind=kind,minimum_s=s,dp=dp,
                    pool_bytes=pool['stack_bytes'],expected_dp=pool.get('dp'),headroom=s+1-pool['stack_base']-256,
                    pc=pc,marker=name,clock=int(fields[0]))
    if window is not None:
        rows={k:v for k,v in rows.items() if v['slot']==window['slot'] and v['lifetime']==1}
        runs={k:{**v,'identity':window['identity']} for k,v in runs.items() if v['slot']==window['slot'] and v['ordinal']==1}
    require(rows,'No passive stack samples')
    for row in rows.values():
        if row['lifetime']>0 and row['kind']!='async':
            require(row['expected_dp'] is None or row['dp']==row['expected_dp'],
                    'Process sample lost direct-page ownership: '+str(row))
            require(row['headroom']>=128,'Process stack headroom below 128: '+str(row))
    return dict(scope='Selected entries and emitted after-TCS sites. Per-pool Process lifetime ordinal starts at Process.Run; actual entry PC, DP and physical pool are recorded. Later native finalization is included until slot reuse. No watermark inference.',lifetimes=list(runs.values()),minima=list(rows.values()))


def capture(bridge,program,record,index=0,during_run=None,retirement_timeout=600):
    """Profile one complete child, after Load and before the next disk load.

    Pause at existing bank-zero COP/restore rendezvous points. No guest code or
    data is changed. The PREPARING row is already owned and has its Image.
    """
    import json
    from native_program import ROOT
    from os_boundary import run_to
    table=next(d['address'] for d in program['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
    layout=json.loads((ROOT/'abi/process.json').read_text())
    fields={name:offset for name,kind,offset in layout['record']}
    count=(next(d['size'] for d in program['image']['data'] if d['address']==table)-4)//layout['record_bytes']
    preparing='|'.join(f'(db(${table+slot*128+fields["state"]:x})=1)' for slot in range(1,count))
    for attempt in range(index+1):
        bridge.bp_clear_all();bridge.bp_set(program['labels']['native_cop'],condition=preparing)
        run_to(bridge,program['labels']['native_cop'],timeout=180,frame_limit=10000,condition=preparing)
        owners=[]
        for slot in range(1,count):
            at=table+slot*128;row=bridge.memdump(at,128)
            if row[fields['state']]!=1:continue
            def number(name,size):
                at=fields[name];return int.from_bytes(row[at:at+size],'little')
            owners.append(dict(slot=slot,identity=number('identity',4),image=number('image',3),record=at))
        require(len(owners)==1,'Ambiguous prepared Process observation')
        owner=owners[0];require(owner['image']!=0,'Prepared observation preceded Image ownership')
        image=bridge.memdump(owner['image'],IMAGE_LAYOUT['size'])
        require(image[IMAGE_FIELDS['kind']]==1,'Observation selected a non-C Image')
        owner.update(image_base=int.from_bytes(image[IMAGE_FIELDS['text']:IMAGE_FIELDS['text']+3],'little'),app_entry=int.from_bytes(image[IMAGE_FIELDS['entry']:IMAGE_FIELDS['entry']+3],'little'))
        at=owner['record'];identity=owner['identity']
        retired=(f'(db(${at+fields["state"]:x})>=4)|'
                 f'(dw(${at+fields["identity"]:x})!={identity&65535})|'
                 f'(dw(${at+fields["identity"]+2:x})!={identity>>16})')
        bridge.bp_clear_all();bridge.bp_set(program['labels']['context_restore'],condition=retired)
        if attempt==index:
            owner['clock_start']=bridge.eval_expr('@clk') & 0xffffffff
            bridge.profile_start('basicblock')
        try:
            if during_run:during_run(owner)
            bridge.bp_clear_all();bridge.bp_set(program['labels']['context_restore'],condition=retired)
            run_to(bridge,program['labels']['context_restore'],timeout=retirement_timeout,frame_limit=30000,condition=retired)
        finally:
            if attempt==index:bridge.profile_stop()
        if attempt==index:owner['clock_end']=bridge.eval_expr('@clk') & 0xffffffff
        bridge.bp_clear_all()
    record['stack_window']=dict(**owner,scope='Selected owned C Process from PREPARING through retirement. Analysis selects its physical slot and first observed lifetime; later history samples are excluded.')
