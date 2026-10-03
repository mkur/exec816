"""Passive operation counts for bitmap console intervals; no target mutation."""
import os
from contextlib import contextmanager
from collections import Counter
from sio_transaction_trace import read_events

@contextmanager
def observation(foreign,program,enabled,performance=None):
    marks={k:foreign['symbols'][k] for k in ('GemDrawingText','GemDrawingCopy','GemDrawingFill','blit_glyph','VbxeSubmit','submit') if k in foreign['symbols']}
    for routine,key in [('READY','ready'),('CONTINUING','continuing')]:
        rows=[r for r in program['image']['routines'] if r['name'].startswith('M_BITMAPSCROLL_'+routine+'_')]
        if len(rows)!=1:raise RuntimeError('Missing trace marker '+routine)
        marks[key]=rows[0]['address']
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')
    old={k:os.environ.get(k) for k in keys}
    try:
        for k in keys:os.environ.pop(k,None)
        if enabled:
            extra={pc for m in (performance or {}).values() for pc in [m['entry'],*m['returns']]}
            os.environ['EXEC816_LATENCY_TRACE']='1'
            os.environ['EXEC816_LATENCY_PCS']=','.join(f'{a:x}' for a in sorted(set(marks.values()) | extra))
        yield marks
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def intervals(log,marks,stages=12):
    names={pc:name for name,pc in marks.items()}
    events=[(tick,names[int(e[4],16)]) for tick,e in read_events(log) if e[0]=='cpu' and int(e[4],16) in names]
    result=[];stage=1;kind='work';counts=Counter();start=None
    for tick,name in events:
        if start is None:start=tick
        if name in ('ready','continuing'):
            expected='ready' if kind=='work' else 'continuing'
            if name!=expected:raise RuntimeError('Unmatched trace interval')
            result.append(dict(stage=stage,kind=kind,start=start,end=tick,calls=dict(counts)))
            counts=Counter();start=tick
            if name=='ready':kind='idle'
            else:kind='work';stage+=1
        else:counts[name]+=1
    if stage!=stages+1 or kind!='work':raise RuntimeError('Incomplete scroll trace')
    return result
