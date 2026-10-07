"""Counter update ownership and bounded physical access on the native timeline."""
import os
from console_turn_profile import markers,flat_markers,analyze_events,Timeline
from bitmap_console_performance import native_markers
from native_program import require
from sio_transaction_trace import read_events
from measure_desktop import distribution


def setup(p,foreign,lean=False,notifications=False):
    definition=markers(p,foreign,p['output'].parent/'drawing')
    if lean:definition["spans"]={}
    points=flat_markers(definition)
    spans=native_markers(p,[('DISPLAY_ENTER','access'),('DISPLAY_LEAVE','leave')])
    sy=foreign['symbols']
    for name in ('CounterUpdateBegin','CounterUpdateOwned','CounterPaintDone','CounterUpdateEnd'):
        points[name]=sy[name]
    for name,span in spans.items():
        points[name]=span['entry']
        for i,pc in enumerate(span['returns']):points[name+str(i)]=pc
    if notifications:
        for index in (1,2):
            name='notice'+str(index)
            notice=native_markers(p,[('AESGUI_NOTICE'+str(index),name)])[name]
            points[name]=notice['entry']
            points['received'+str(index)]=sy['CounterNoticeOne' if index==1 else 'CounterNoticeTwo']
        definition['notifications']={k:v for k,v in points.items() if k.startswith(('notice','received'))}
    saved={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{v:x}' for v in set(points.values())))
    return definition,spans,sy,saved


def restore(config):
    for k,v in config[3].items():
        if v is None:os.environ.pop(k,None)
        else:os.environ[k]=v


def result(out,config):
    definition,spans,sy,_=config;events=read_events(out/'emulator.log')
    profile=analyze_events(events,definition,include_segments=True)
    timelines={};active={};rows=[]
    def end(kind,dp,tick,start_kind=None):
        begin=active.pop((start_kind or kind,dp))
        if dp not in timelines:timelines[dp]=Timeline(profile['segments'],dp)
        rows.append(dict(kind=kind,dp=dp,start=begin,end=tick,**timelines[dp].measure(begin,tick)))
    for tick,event in events:
        if event[0]!='cpu':continue
        pc,dp=int(event[4],16),int(event[9],16)
        if pc==spans['access']['entry']:active['access_wait',dp]=tick
        elif pc in spans['access']['returns']:
            end('access_wait',dp,tick);active['physical_unit',dp]=tick
        elif pc==spans['leave']['entry']:end('physical_unit',dp,tick)
        elif pc==sy['CounterUpdateBegin']:
            active['update_wait',dp]=active['repaint',dp]=tick
        elif pc==sy['CounterUpdateOwned']:
            end('update_wait',dp,tick);active['update_owned',dp]=active['logical_hold',dp]=tick
        elif pc==sy['CounterPaintDone']:end('drawing',dp,tick,'update_owned');active['unlock',dp]=tick
        elif pc==sy['CounterUpdateEnd']:
            end('unlock',dp,tick);end('logical_hold',dp,tick);end('repaint',dp,tick)
    require(not active,'Incomplete counter timing spans: '+str(active))
    kinds=sorted({r['kind'] for r in rows})
    summary={kind:{metric:distribution([r[metric] for r in rows if r['kind']==kind])
                   for metric in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')} for kind in kinds}
    return dict(summary=summary,scope='Instrumented functional fixture, including deliberately delayed event consumers and assertion/controller load. Update wait is before BEG_UPDATE to its caller return; drawing is owned redraw to before END_UPDATE; repaint includes both RPCs. Physical units start at successful native DISPLAY.Enter return and end at DISPLAY.Leave entry, including bridge return, pixels and fences. These are development timings, not PI4/HY4 acceptance.',rows=rows)
