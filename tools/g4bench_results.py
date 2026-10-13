"""Decode application-owned G4BENCH samples; no target timing service."""
import statistics
from native_program import require

NAMES=('solid bars','text even X','text odd X','text clipped','five-object dialog')
STATES=('pending','complete','low resolution','cancelled','invalidated','error')


def read(bridge,symbols):
    def values(name,count,width=2):
        raw=bridge.memdump(symbols[name],count*width)
        return [int.from_bytes(raw[i:i+width],'little') for i in range(0,len(raw),width)]
    rate=values('g4b_rate',1,4)[0]
    status=values('g4b_status',5);counts=values('g4b_counts',5)
    operations=values('g4b_operations',15);ticks=values('g4b_ticks',15,4)
    stamps=values('g4b_times',90,4);clips=values('g4b_clips',20)
    rows=[]
    for row,name in enumerate(NAMES):
        samples=[]
        for sample in range(3):
            i=row*3+sample;start=stamps[i*6:i*6+3];end=stamps[i*6+3:i*6+6]
            if operations[i]:
                require(start[2]==end[2]==rate,'Changed sample clock rate')
                require(((end[0]<<32)|end[1])-((start[0]<<32)|start[1])==ticks[i],
                        'Clock snapshots disagree with elapsed ticks')
                require(operations[i]==counts[row],'Changed sample operation count')
            samples.append(dict(operations=operations[i],ticks=ticks[i],start=start,end=end))
        complete=status[row] in (1,2)
        require(not complete or all(s['operations'] for s in samples),'Incomplete row reported as complete')
        rows.append(dict(name=name,status=STATES[status[row]],clip=clips[row*4:row*4+4],samples=samples,
                         median_ms_per_operation=statistics.median(s['ticks']*1000/rate/s['operations'] for s in samples) if complete else None))
    return dict(workload='Exec816 subset v1',rate=rate,canvas=values('g4b_canvas',4),
                rows=rows,save=values('g4b_save',1)[0],runs=values('g4b_runs',1)[0])
