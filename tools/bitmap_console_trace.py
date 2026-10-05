"""Passive operation counts for bitmap console intervals; no target mutation."""
import os
from contextlib import contextmanager
from collections import Counter
from sio_transaction_trace import BASE_HZ,read_events


def echo_order(log,marks,windows):
    """Measure model-update entry through drawing return and write retirement."""
    names={marks[k]:k for k in ('echo_feed','write_reply','drawing_done')}
    events=[(tick,names[int(e[4],16)]) for tick,e in read_events(log)
            if e[0]=='cpu' and int(e[4],16) in names]
    result=[]
    for w in windows:
        rows=[(t,n) for t,n in events if w['start']<=t<=w['end']]
        feeds=[t for t,n in rows if n=='echo_feed']
        replies=[t for t,n in rows if n=='write_reply']
        drawings=[t for t,n in rows if n=='drawing_done']
        if len(feeds)!=1 or len(replies)!=1 or not drawings:
            raise RuntimeError('Incomplete short-write trace: '+str(w))
        result.append(dict(stage=w['stage'],drawing_before_reply=drawings[-1]<replies[0],
            feed_to_drawing_done_ms=(drawings[-1]-feeds[0])/BASE_HZ*1000,
            feed_to_reply_ms=(replies[0]-feeds[0])/BASE_HZ*1000))
    return result

@contextmanager
def observation(foreign,program,enabled,performance=None,module='BITMAPSCROLL'):
    marks={k:foreign['symbols'][k] for k in ('GemDrawingText','GemDrawingTextFill','GemDrawingCopy','GemDrawingScrollStart',
        'GemDrawingPoll','GemDrawingFill','blit_glyph','_text_record','VbxeSubmit','submit',
        'DisplayCheck','start') if k in foreign['symbols']}
    if module=='BITMAPTEST':
        for routine,key in [('CONSOLECORE_FEED','echo_feed'),('CONSOLEDRIVER_FINISHWRITE','write_reply')]:
            rows=[r for r in program['image']['routines'] if r['name'].startswith('M_'+routine+'_')]
            if len(rows)!=1:raise RuntimeError('Missing echo marker '+routine)
            marks[key]=rows[0]['address']
        marks['drawing_done']=program['labels']['console_bitmap_done']
    for routine,key in [('READY','ready'),('CONTINUING','continuing')]:
        rows=[r for r in program['image']['routines'] if r['name'].startswith('M_'+module+'_'+routine+'_')]
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
