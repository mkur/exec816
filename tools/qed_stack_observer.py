"""Passive S samples at emitted entries and frame reservations, grouped by lifetime."""
from collections import defaultdict
from pathlib import Path
import json,re
from c_program import ABI
from program_image_layout import LAYOUT as IMAGE_LAYOUT,FIELDS as IMAGE_FIELDS
from native_program import require


def markers(program,app,image_bases=None):
    from native_program import ROOT
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
        # Local C names can shadow exported symbols in other translation units.
        # Resolve each retained function through its object section and linker
        # placement, then verify the observed opcode in the emitted image.
        from build_qed import object_symbols
        objects=[Path(obj) for obj in image['provenance']['link_objects']]
        linked=objects[0].parent/'link.lst'
        require(linked.is_file(),'Missing actual linker placement for stack markers')
        pattern=(r"([^\n]+?) in section 'farcode'\s+placed at address ([a-f0-9]+)-([a-f0-9]+) "
                 r"of size [a-f0-9]+\n\([^\n]*?unit (\d+) section index (\d+)\)")
        placements={(int(m[4]),int(m[5])):(int(m[2],16),int(m[3],16)+1)
                    for m in re.finditer(pattern,linked.read_text())}
        for obj in objects:
            listing=obj.with_suffix('.lst')
            if not listing.is_file() or not obj.stem.split('-')[0].isdigit():continue
            symbols=object_symbols(obj);unit=int(obj.stem.split('-')[0])
            chunks=re.split(r'\\ [0-9a-f]{6}\s+\.section ',listing.read_text(errors='replace'))
            for chunk in chunks:
                if not chunk.startswith('farcode,text'):continue
                labels=re.findall(r'\\ ([0-9a-f]{6})\s+(?:[a-f0-9.]+\s+)?(`?[^\s:`]+`?):',chunk,re.M)
                head=next((n.strip('`') for at,n in labels if at=='000000' and n.strip('`') in symbols),None)
                if head is None:continue
                location=placements.get((unit,symbols[head]['section']))
                if location is None:continue
                base,end=location
                label=head if image['symbols'].get(head)==base else obj.stem.split('-',1)[-1]+':'+head
                points.setdefault(base+delta,prefix+label)
                for match in re.finditer(r'\\ ([0-9a-f]{6}) 1b\s+tcs',chunk):
                    pc=base+int(match[1],16)
                    segment=next((s for s in image['segments'] if s['address']<=pc<s['address']+len(s['bytes'])),None)
                    require(pc<end and segment and segment['bytes'][pc-segment['address']]==0x1b,
                            'Stack marker disagrees with linked TCS instruction')
                    points.setdefault(pc+1+delta,prefix+label+':after-tcs')
    entries(resident,'provider:')
    frames(resident,program['output'].parent/'drawing','provider:')
    decoder={'__name__':'qed_stack_decoder'}
    source=ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(source.read_text(),str(source),'exec'),decoder)
    for routine in program['image']['routines']:
        if routine['name'].startswith(('M_PROCESS_RUN_','M_PROCESS_FINISH_',
                'M_DOSCLIENT_','M_DOSCALLS_','M_HEAP_','M_HEAPCORE_',
                'M_TASKPOLICY_PROCESS','M_AESLOCAL_','M_AESLOCKS_',
                'M_AESMOUSE_','M_AESWINDOWSTATE_')):
            points[routine['address']]=routine['name']
            segment=next(s for s in program['image']['segments'] if
                s['address']<=routine['address'] and routine['address']+routine['size']
                    <=s['address']+len(s['bytes']))
            start=routine['address']-segment['address']
            listing=decoder['disassemble']({**program['image'],'version':3,'segments':[
                dict(address=routine['address'],executable=True,
                    bytes=segment['bytes'][start:start+routine['size']])]})
            for line in listing.splitlines():
                if line.endswith(' TCS'):
                    points[int(line[:6],16)+1]=routine['name']+':after-tcs'
    # An APP cannot occupy resident storage. Exclude those bases, so candidate
    # relocation markers cannot masquerade as a different resident routine.
    occupied=[(s['address'],s['address']+len(s['bytes'])) for im in (program['image'],resident) for s in im['segments']]
    for bank in app['verified_banks']:
        low=bank*65536;high=low+app['span']
        if image_bases is not None and low not in image_bases:continue
        if any(low<b and a<high for a,b in occupied):continue
        delta=(bank-ABI['link_bank'])*65536
        entries(app['image'],'app:',delta,True)
        frames(app['image'],program['output'].parent/'app','app:',delta)
    for name in ('native_irq','native_nmi','cop_handler','context_restore'):
        if name in program['labels']:points[program['labels'][name]]=name
    return points


def summarize(path,points,memory,window=None,scoped_points=None):
    pools=list(enumerate(memory['task_pools']));rows={};lifetimes=defaultdict(int);runs={}
    selected={}
    if window is not None:
        windows=window if isinstance(window,list) else [window]
        ordinals=defaultdict(int)
        for owner in windows:
            ordinals[owner['slot']]+=1
            selected[owner['slot'],ordinals[owner['slot']]]=owner['identity']
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
            if name.startswith('M_PROCESS_RUN_') and not name.endswith(':after-tcs'):
                lifetimes[slot]+=1
                runs[slot,lifetimes[slot]]=dict(slot=slot,ordinal=lifetimes[slot],dp=dp,clock=int(fields[0]))
            if scoped_points is not None:
                local=scoped_points.get(selected.get((slot,lifetimes[slot])),points)
                if pc not in local:continue
                name=local[pc]
            if name=='app:main' and (slot,lifetimes[slot]) in runs:
                runs[slot,lifetimes[slot]]['app_entry']=pc
            kind='async' if name in ('native_irq','native_nmi','context_restore') else ('frame-reservation' if name.endswith(':after-tcs') else 'ordinary-sample')
            key=f'{slot}:{lifetimes[slot]}:{kind}'
            if key not in rows or s<rows[key]['minimum_s']:
                rows[key]=dict(slot=slot,lifetime=lifetimes[slot],kind=kind,minimum_s=s,dp=dp,
                    pool_bytes=pool['stack_bytes'],expected_dp=pool.get('dp'),headroom=s+1-pool['stack_base']-256,
                    pc=pc,marker=name,clock=int(fields[0]))
    if window is not None:
        rows={k:v for k,v in rows.items() if (v['slot'],v['lifetime']) in selected}
        runs={k:{**v,'identity':selected[k]} for k,v in runs.items() if k in selected}
    require(rows,'No passive stack samples')
    for row in rows.values():
        if row['lifetime']>0 and row['kind']!='async':
            require(row['expected_dp'] is None or row['dp']==row['expected_dp'],
                    'Process sample lost direct-page ownership: '+str(row))
            require(row['headroom']>=128,'Process stack headroom below 128: '+str(row))
    return dict(scope='Selected entries and emitted after-TCS sites. Per-pool Process lifetime ordinal starts at Process.Run; actual entry PC, DP and physical pool are recorded. Later native finalization is included until slot reuse. No watermark inference.',lifetimes=list(runs.values()),minima=list(rows.values()))



def summarize_owned(path,program,app,memory,windows):
    """Classify APP sites using each captured owner's actual relocation base."""
    owners=windows if isinstance(windows,list) else [windows]
    scoped={w['identity']:markers(program,app,[w['image_base']]) for w in owners}
    result=summarize(path,markers(program,app),memory,windows,scoped_points=scoped)
    result['scope']='Actual captured APP image bases and native/provider sites; per-pool Process ordinals, DP and guards remain checked. Broad candidate-only sites are excluded. Selected-PC observations, not a watermark.'
    return result


def capture(bridge,program,record,index=0,during_run=None,retirement_timeout=600,profile_all=False,observation_count=None):
    """Profile one complete child, after Load and before the next disk load.

    Pause at existing bank-zero COP/restore rendezvous points. No guest code or
    data is changed. The PREPARING row is already owned and has its Image.
    observation_count can keep later interactive lifetimes running without
    adding them to the selected stack window.
    """
    import json
    import adapter_state as adapter
    from native_program import ROOT
    from os_boundary import run_to
    table=next(d['address'] for d in program['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
    layout=json.loads((ROOT/'abi/process.json').read_text())
    fields={name:offset for name,kind,offset in layout['record']}
    count=(next(d['size'] for d in program['image']['data'] if d['address']==table)-4)//layout['record_bytes']
    preparing='|'.join(f'(db(${table+slot*128+fields["state"]:x})=1)' for slot in range(1,count))
    def rendezvous(address,**options):
        original=bridge.regs
        def regs():
            value=original()
            require(not bridge.eval_expr(adapter.STOPPED),
                    'Process fixture stopped before completing the selected lifetimes')
            return value
        bridge.regs=regs
        try:return run_to(bridge,address,**options)
        finally:bridge.regs=original
    interactions=index+1 if observation_count is None else observation_count
    require(interactions>index>=0,'Selected stack lifetime is outside the interaction count')
    for attempt in range(interactions):
        bridge.bp_clear_all();bridge.bp_set(program['labels']['native_cop'],condition=preparing)
        rendezvous(program['labels']['native_cop'],timeout=180,frame_limit=10000,condition=preparing)
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
        if attempt==index or profile_all:
            owner['clock_start']=bridge.eval_expr('@clk') & 0xffffffff
            bridge.profile_start('basicblock')
            # SetProfiler keeps the CPU history flag enabled after End(). The
            # pinned observer writes selected PC/S/D samples from that history
            # path. Aggregate basic-block counts are unused and expensive.
            bridge.profile_stop()
        after=during_run(owner) if during_run else None
        bridge.bp_clear_all();bridge.bp_set(program['labels']['context_restore'],condition=retired)
        rendezvous(program['labels']['context_restore'],timeout=retirement_timeout,frame_limit=30000,condition=retired)
        if after:after()
        if attempt==index or profile_all:
            owner['clock_end']=bridge.eval_expr('@clk') & 0xffffffff
            if profile_all:record.setdefault('stack_windows',[]).append(owner)
            record['stack_window']=dict(**owner,scope='Selected owned C Process from PREPARING through retirement. Analysis selects its physical slot and first observed lifetime; later history samples are excluded.')
        bridge.bp_clear_all()
