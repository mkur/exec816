"""Passive emitted-C timings using the pinned emulator's existing PC observer."""
import os
import re
from contextlib import contextmanager
from native_program import require
from sio_transaction_trace import BASE_HZ, read_events


def markers(output, foreign):
    names=('GemPrepare','GemSubmit','VbxeFill','VbxeBlit','VbxeCopyRect','VbxeSubmit','submit','transfer','idle')
    result={}
    for path in output.glob('*.lst'):
        current=None
        previous=""
        for line in path.read_text().splitlines():
            start=re.search(r'\\ ([0-9a-f]{6})\s+(?:[0-9a-f.]+\s+)?([A-Za-z_][A-Za-z_0-9]*):',line)
            if '.section ' in line: current=None
            if start:
                name=start[2]
                current=name if name in names and name in foreign['symbols'] else None
                if current:
                    result[current]=dict(entry=foreign['symbols'][current],returns=[])
            launch=re.search(r'\\ ([0-9a-f]{6}) 8f53d600\s+sta',line)
            if current and launch and 'lda     #1' in previous:
                result['launch_'+current]=dict(entry=result[current]['entry']+int(launch[1],16)+4,returns=[])
            previous=line
            ret=re.search(r'\\ ([0-9a-f]{6}) 6b\s+rtl',line)
            if current and ret:
                result[current]['returns'].append(result[current]['entry']+int(ret[1],16))
    result['measure']=dict(entry=foreign['symbols']['BenchmarkStart'],returns=[foreign['symbols']['BenchmarkEnd']])
    return result


@contextmanager
def observation(output, foreign, enabled):
    marks=markers(output,foreign) if enabled else {}
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')
    previous={k:os.environ.get(k) for k in keys}
    try:
        for key in keys: os.environ.pop(key,None)
        if enabled:
            pcs={pc for m in marks.values() for pc in [m['entry'],*m['returns']]}
            os.environ['EXEC816_LATENCY_TRACE']='1'
            os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in sorted(pcs))
        yield marks
    finally:
        for key,value in previous.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value


def summarize(path,marks):
    active={};cases=[];case=None
    for tick,event in read_events(path):
        if event[0]!='cpu': continue
        pc=int(event[4],16)
        for name,mark in marks.items():
            if pc==mark['entry']:
                if name=='measure':
                    require(case is None,'Nested measurement')
                    case={'start':tick,'routines':{},'entries':{}}
                if case is not None:
                    if name=='GemPrepare':case['prepare']=tick
                    if name=='GemSubmit' and 'prepare' in case:
                        case['routines'].setdefault('packet_construction',[]).append((tick-case.pop('prepare'))/BASE_HZ*1000)
                    if name.startswith('launch_'):case['launch']=tick
                    case['entries'][name]=case['entries'].get(name,0)+1
                    if mark['returns']:
                        require(name not in active,'Nested measured routine: '+name)
                        active[name]=tick
            elif pc in mark['returns'] and name in active:
                # Timestamp at RTL, excluding the return instruction itself.
                elapsed=(tick-active.pop(name))/BASE_HZ*1000
                values=case['routines'].setdefault(name,[]);values.append(elapsed)
                if name=='idle' and 'launch' in case:
                    case['routines'].setdefault('launch_to_confirmed_idle',[]).append((tick-case.pop('launch'))/BASE_HZ*1000)
                if name=='measure':
                    require('launch' not in case and 'prepare' not in case,'Incomplete packet or DMA')
                    require(not active,'Incomplete measurement')
                    case['end']=tick;cases.append(case);case=None
    require(case is None and cases,'Incomplete/no measured intervals')
    for case in cases:
        case['routines']={name:dict(calls=len(v),total_ms=sum(v),max_ms=max(v))
                          for name,v in case['routines'].items()}
    return cases
