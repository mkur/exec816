"""Passive cycle boundaries for console CPU work and fenced drawing.

Elapsed routine time includes preemption and is an upper bound on its CPU time.
The launch-to-idle-read interval bounds hardware occupancy; it is not a BUSY-edge
measurement. Host screenshot/fixture Sleep intervals are outside these spans.
"""
import re
from native_program import ROOT,require
from sio_transaction_trace import BASE_HZ,read_events


def native_markers(program, routines):
    """Optional native routines, including their checked machine-code returns."""
    decoder={'__name__':'bitmap_decoder'}
    path=ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(),str(path),'exec'),decoder)
    image=program['image'];result={}
    for routine,key in routines:
        matches=[r for r in image['routines'] if r['name'].startswith('M_'+routine+'_')]
        if not matches:continue
        require(len(matches)==1,'Ambiguous performance routine '+routine)
        r=matches[0];segments=[]
        for s in image['segments']:
            lo=max(s['address'],r['address']);hi=min(s['address']+len(s['bytes']),r['address']+r['size'])
            if lo<hi:segments.append(dict(address=lo,executable=True,bytes=s['bytes'][lo-s['address']:hi-s['address']]))
        listing=decoder['disassemble']({**image,'version':3,'segments':segments})
        result[key]=dict(entry=r['address'],returns=[int(line[:6],16) for line in listing.splitlines() if line.endswith(' RTL')])
    return result


def input_markers(program):
    result=native_markers(program,[('CONSOLEINPUT_PENDING','input_pending'),
        ('CONSOLEINPUT_PUMP','pump'),('CONSOLEDRIVER_COLLECT','input_collect'),('CONSOLEINPUT_SERVICE','input_service'),
        ('INPUT_PENDING','public_pending'),('INPUT_TAKE','input_take'),
        ('INPUT_EXTENT','input_extent'),('TASKMEMORY_WRITABLE','writable'),
        ('CONSOLEDRIVER_RUNNABLE','runnable')])
    for label,key in [('tasks_find_task','find_task'),('tasks_set_signal','signal_collect')]:
        result[key]=dict(entry=program['labels'][label],returns=[program['labels'][label+'_end']-1])
    return result


def markers(program,foreign,output):
    result=native_markers(program,[('CONSOLEDISPLAY_'+routine,key) for routine,key in
        [('PRESENT','present'),('ADVANCE','advance'),('BITMAPEDIT','edit'),('CELLS','cells'),
         ('BITMAPCOMPLETE','bitmap_complete'),('POLL','bitmap_poll')]])
    image=program['image'];result.update(input_markers(program))
    result.update(native_markers(program,[('DISPLAY_CHECK','display_check'),
        ('DISPLAY_VALID','display_valid')]))
    # Count public C entries without guessing their shared/tail-call epilogues.
    # The ordinary-call boundary supplies complete drawing-call elapsed time;
    # native DISPLAY.Check spans isolate its validation work by owning Task DP.
    for name in ('DisplayCheck','GemDrawingCopy','GemDrawingFill','GemDrawingText',
                 'GemDrawingFence','GemDrawingScrollStart','GemDrawingScrollPoll',
                 'VbxeCopyRect','VbxeFill','VbxeSubmit','VbxeFence'):
        if name in foreign['symbols']:
            result[name]=dict(entry=foreign['symbols'][name],returns=[],entry_only=True)
    if 'input_collect' in result:
        from dos_concurrent_trace import call_marker
        # Observe caller-side stores, flag arguments and branch decisions too.
        # Keep control processing outside the input charge; it already existed.
        targets=dict(collect=result['input_collect']['entry'],service=result['input_service']['entry'])
        for name,routine in [('control','CONSOLECONTROL_PROCESS'),('arrival','CONSOLEDRIVER_ARRIVAL')]:
            targets[name]=next(r['address'] for r in image['routines'] if r['name'].startswith('M_'+routine+'_'))
        mapped={**program,'labels':{**program['labels'],**targets}}
        if 'bitmap_poll' in result:
            targets['poll']=result['bitmap_poll']['entry']
            mapped['labels']['poll']=targets['poll']
        calls={name:call_marker(mapped,'M_CONSOLEDRIVER_WORKER_',name) for name in targets}
        result['input_collect_turn']=dict(entry=calls['collect'],returns=[calls.get('poll',calls['control'])])
        result['input_service_turn']=dict(entry=calls['control']+4,returns=[calls['arrival']])
    result['call']=dict(entry=program['labels']['console_bitmap_call'],returns=[program['labels']['console_bitmap_done']])
    repaint=[r for r in image['routines'] if r['name'].startswith('M_BITMAPSCROLL_REPAINTBEGIN_')]
    if repaint:result['repaint']=dict(entry=repaint[0]['address'],returns=[])
    # The ordinary call has one return irrespective of C tail-call epilogues.
    # Only idle has a standalone return; other optimized C exits may be shared.
    if 'complete_scroll' in foreign['symbols']:
        result['complete_scroll']=dict(entry=foreign['symbols']['complete_scroll'],returns=[],entry_only=True)
    current=None;busy_next=False
    for path in output.glob('*vbxe.lst'):
        for line in path.read_text().splitlines():
            if '.section ' in line:current=None
            start=re.search(r'\\ ([0-9a-f]{6})\s+(?:[0-9a-f.]+\s+)?(idle|submit|launch):',line)
            if start:
                current=start[2]
                if current=='idle':result['idle']=dict(entry=foreign['symbols']['idle'],returns=[])
            if current in ('submit','launch') and busy_next and 'jsl ' in line:
                address=int(re.search(r'\\ ([0-9a-f]{6})',line)[1],16)
                result['launch']=dict(entry=foreign['symbols'][current]+address,returns=[])
                busy_next=False
            if current in ('submit','launch') and re.search(r'\\ ([0-9a-f]{6}) 8f53d600\s+sta',line):
                address=int(re.search(r'\\ ([0-9a-f]{6})',line)[1],16)
                result['launch']=dict(entry=foreign['symbols'][current]+address+4,returns=[])
            busy_next=current in ('submit','launch') and bool(re.search(r' a901\s+lda\s+#1$',line))
            ret=re.search(r'\\ ([0-9a-f]{6}) 6b\s+(?:`[^`]+`: *)?rtl',line)
            if current=='idle' and ret:result['idle']['returns'].append(foreign['symbols']['idle']+int(ret[1],16))
    require(result.get('idle',{}).get('returns') and 'launch' in result,'Missing hardware fence markers')
    return result


def spans(path,marks):
    active={};samples=[];launch={}
    for tick,e in read_events(path):
        if e[0]!='cpu':continue
        pc=int(e[4],16);dp=int(e[9],16)
        for name,m in marks.items():
            key=(name,dp)
            if pc==m['entry']:
                # Optimized C may inline complete_scroll. Native completion is
                # also proof of an idle read, before caret drawing can start.
                if name in ('complete_scroll','bitmap_complete') and dp in launch:
                    start=launch.pop(dp)
                    samples.append(dict(kind='launch_to_idle',dp=dp,start=start,end=tick,ms=(tick-start)/BASE_HZ*1000))
                if name=='launch':
                    require(dp not in launch,'Overlapping hardware launch');launch[dp]=tick
                elif name=='repaint' or m.get('entry_only'):
                    samples.append(dict(kind=name,dp=dp,start=tick,end=tick,ms=0))
                elif m['returns']:
                    require(key not in active,'Nested performance routine '+name);active[key]=tick
            elif pc in m['returns'] and key in active:
                start=active.pop(key);samples.append(dict(kind=name,dp=dp,start=start,end=tick,ms=(tick-start)/BASE_HZ*1000))
                if name=='idle' and dp in launch:
                    start=launch.pop(dp)
                    samples.append(dict(kind='launch_to_idle',dp=dp,start=start,end=tick,ms=(tick-start)/BASE_HZ*1000))
    require(not active and not launch,'Unfinished performance span')
    return samples


def totals(rows):
    kinds={name:[r['ms'] for r in rows if r['kind']==name] for name in {r['kind'] for r in rows}}
    return {k:dict(calls=len(v),total_ms=sum(v),max_ms=max(v)) for k,v in kinds.items()}


def summarize(path,marks,windows):
    samples=spans(path,marks)
    result=[]
    for window in windows:
        if window['kind']!='work':continue
        rows=[r for r in samples if window['start']<=r['start']<=r['end']<=window['end']]
        item=dict(stage=window['stage'],routines=totals(rows))
        repaint=[r for r in rows if r['kind']=='repaint']
        calls=[r for r in rows if r['kind']=='call']
        if repaint and calls:
            item['repaint_request_to_final_fence_ms']=(calls[-1]['end']-repaint[0]['start'])/BASE_HZ*1000
        edits=[r for r in rows if r['kind']=='edit'];advances=[r for r in rows if r['kind'] in ('advance','bitmap_complete')]
        if edits and advances:
            # Consecutive edits delimit independent continuations; the last
            # Advance return is the final copy/fill fence plus acknowledgement.
            scroll=[];input_checks=[]
            for i,edit in enumerate(edits):
                limit=edits[i+1]['start'] if i+1<len(edits) else window['end']
                ends=[r['end'] for r in advances if edit['end']<=r['start']<limit]
                if ends:
                    end=max(ends);scroll.append((end-edit['start'])/BASE_HZ*1000)
                    inside=[r for r in rows if r['dp']==edit['dp'] and edit['start']<=r['start']<=r['end']<=end]
                    measured=totals(inside)
                    # Disjoint new-path spans; count the entire Runnable helper
                    # conservatively when it executes. Old Pending is inside it.
                    components=('input_pending',)
                    if 'input_service' in marks:components=('input_service','input_collect','runnable')
                    if 'input_service_turn' in marks:components=('input_service_turn','input_collect_turn','runnable')
                    input_checks.append(dict(worker_dp=edit['dp'],routines=measured,
                        input_check_ms=sum(measured.get(k,{}).get('total_ms',0) for k in components),
                        components=components))
            item['edit_through_final_chunk_ms']=scroll
            item['scroll_input']=input_checks
        result.append(item)
    idle=[dict(stage=w['stage'],routines=totals([r for r in samples if w['start']<=r['start']<=r['end']<=w['end'] and r['kind'] in ('input_pending','input_service','pump','input_take','signal_collect')])) for w in windows if w['kind']=='idle']
    return dict(scope=__doc__,stages=result,idle_input=idle,limits_ms=dict(cpu_quantum=4,list_occupancy=2,scroll=20,repaint=500,input_visible=40))
