"""Passive cycle boundaries for console CPU work and fenced drawing.

Elapsed routine time includes preemption and is an upper bound on its CPU time.
The launch-to-idle-read interval bounds hardware occupancy; it is not a BUSY-edge
measurement. Host screenshot/fixture Sleep intervals are outside these spans.
"""
import re
from native_program import ROOT,require
from sio_transaction_trace import BASE_HZ,read_events


def markers(program,foreign,output):
    decoder={'__name__':'bitmap_decoder'}
    path=ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(),str(path),'exec'),decoder)
    image=program['image'];result={}
    for routine,key in [('PRESENT','present'),('ADVANCE','advance'),('BITMAPEDIT','edit'),('CELLS','cells')]:
        r=next(r for r in image['routines'] if r['name'].startswith('M_CONSOLEDISPLAY_'+routine+'_'))
        segments=[]
        for s in image['segments']:
            lo=max(s['address'],r['address']);hi=min(s['address']+len(s['bytes']),r['address']+r['size'])
            if lo<hi:segments.append(dict(address=lo,executable=True,bytes=s['bytes'][lo-s['address']:hi-s['address']]))
        listing=decoder['disassemble']({**image,'version':3,'segments':segments})
        result[key]=dict(entry=r['address'],returns=[int(line[:6],16) for line in listing.splitlines() if line.endswith(' RTL')])
    result['call']=dict(entry=program['labels']['console_bitmap_call'],returns=[program['labels']['console_bitmap_done']])
    r=next(r for r in image['routines'] if r['name'].startswith('M_BITMAPSCROLL_REPAINTBEGIN_'))
    result['repaint']=dict(entry=r['address'],returns=[])
    # The ordinary call has one return irrespective of C tail-call epilogues.
    # Only idle has a standalone return; other optimized C exits may be shared.
    current=None;busy_next=False
    for path in output.glob('*vbxe.lst'):
        for line in path.read_text().splitlines():
            if '.section ' in line:current=None
            start=re.search(r'\\ ([0-9a-f]{6})\s+(?:[0-9a-f.]+\s+)?(idle|submit):',line)
            if start:
                current=start[2]
                if current=='idle':result['idle']=dict(entry=foreign['symbols']['idle'],returns=[])
            if current=='submit' and busy_next and 'jsl ' in line:
                address=int(re.search(r'\\ ([0-9a-f]{6})',line)[1],16)
                result['launch']=dict(entry=foreign['symbols']['submit']+address,returns=[])
                busy_next=False
            if current=='submit' and re.search(r'\\ ([0-9a-f]{6}) 8f53d600\s+sta',line):
                address=int(re.search(r'\\ ([0-9a-f]{6})',line)[1],16)
                result['launch']=dict(entry=foreign['symbols']['submit']+address+4,returns=[])
            busy_next=current=='submit' and bool(re.search(r' a901\s+lda\s+#1$',line))
            ret=re.search(r'\\ ([0-9a-f]{6}) 6b\s+(?:`[^`]+`: *)?rtl',line)
            if current=='idle' and ret:result['idle']['returns'].append(foreign['symbols']['idle']+int(ret[1],16))
    require(result.get('idle',{}).get('returns') and 'launch' in result,'Missing hardware fence markers')
    return result


def summarize(path,marks,windows):
    active={};samples=[];launch=None
    for tick,e in read_events(path):
        if e[0]!='cpu':continue
        pc=int(e[4],16)
        for name,m in marks.items():
            if pc==m['entry']:
                if name=='launch':launch=tick
                elif name=='repaint':samples.append(dict(kind=name,start=tick,end=tick,ms=0))
                elif m['returns']:
                    require(name not in active,'Nested performance routine '+name);active[name]=tick
            elif pc in m['returns'] and name in active:
                start=active.pop(name);samples.append(dict(kind=name,start=start,end=tick,ms=(tick-start)/BASE_HZ*1000))
                if name=='idle' and launch is not None:
                    samples.append(dict(kind='launch_to_idle',start=launch,end=tick,ms=(tick-launch)/BASE_HZ*1000));launch=None
    require(not active and launch is None,'Unfinished performance span')
    result=[]
    for window in windows:
        if window['kind']!='work':continue
        rows=[r for r in samples if window['start']<=r['start']<=r['end']<=window['end']]
        kinds={name:[r['ms'] for r in rows if r['kind']==name] for name in {r['kind'] for r in rows}}
        item=dict(stage=window['stage'],routines={k:dict(calls=len(v),total_ms=sum(v),max_ms=max(v)) for k,v in kinds.items()})
        repaint=[r for r in rows if r['kind']=='repaint']
        calls=[r for r in rows if r['kind']=='call']
        if repaint and calls:
            item['repaint_request_to_final_fence_ms']=(calls[-1]['end']-repaint[0]['start'])/BASE_HZ*1000
        edits=[r for r in rows if r['kind']=='edit'];advances=[r for r in rows if r['kind']=='advance']
        if edits and advances:
            # Consecutive edits delimit independent continuations; the last
            # Advance return is the final copy/fill fence plus acknowledgement.
            scroll=[]
            for i,edit in enumerate(edits):
                limit=edits[i+1]['start'] if i+1<len(edits) else window['end']
                ends=[r['end'] for r in advances if edit['end']<=r['start']<limit]
                if ends:scroll.append((max(ends)-edit['start'])/BASE_HZ*1000)
            item['edit_through_final_chunk_ms']=scroll
        result.append(item)
    return dict(scope=__doc__,stages=result,limits_ms=dict(cpu_quantum=4,list_occupancy=2,scroll=20,repaint=500,input_visible=40))
