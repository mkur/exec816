"""Independent interval semantics for classic Exec memory qualification."""
import random


class Pool:
    def __init__(self, low, high):
        assert 0 < low < high <= 0x1000000 and not (low|high)&7
        self.low,self.high=low,high
        self.free=[(low,high)]

    @property
    def available(self): return sum(b-a for a,b in self.free)

    def allocate(self, size, contained=False):
        if not size or size>0xfffffff8: return 0
        rounded=(size+7)//8*8
        if contained and rounded>65536:return 0
        for a,b in self.free:
            candidates=[a]
            if contained:candidates += list(range((a//65536+1)*65536,b,65536))
            for start in candidates:
                end=start+rounded
                if end>b or contained and start//65536!=(end-1)//65536:continue
                self.free=sorted([(x,y) for x,y in self.free if (x,y)!=(a,b)]+[(x,y) for x,y in ((a,start),(end,b)) if x<y])
                return start
        return 0

    def release(self, start, size):
        if not size:return
        low=start//8*8;high=(start+size+7)//8*8
        assert self.low<=low<high<=self.high
        assert all(high<=a or low>=b for a,b in self.free)
        intervals=sorted(self.free+[(low,high)])
        merged=[]
        for a,b in intervals:
            if merged and merged[-1][1]==a:merged[-1]=(merged[-1][0],b)
            else:merged.append((a,b))
        self.free=merged


class System:
    def __init__(self, regions):
        # Independent ordered region/interval model, not linked headers.
        self.regions=[(priority,attributes,Pool(a,b)) for a,b,priority,attributes in regions]
        self.regions.sort(key=lambda r:(-r[0],r[2].low))

    @staticmethod
    def valid(flags, query=False):
        allowed=0x80110019 | (0xa0000 if query else 0)
        return not (flags&~allowed or flags&8 and flags&0x100010 or flags&0xa0000==0xa0000)

    def matching(self,flags):
        required=flags&0x19
        if not required&8:required|=0x10
        return [p for _,attrs,p in self.regions if attrs&required==required]

    def allocate(self,size,flags=0):
        if not self.valid(flags):return 0
        for pool in self.matching(flags):
            result=pool.allocate(size,not flags&0x100000)
            if result:return result
        return 0

    def release(self,address,size):
        if not size:return
        assert address and not address&7
        pool=next(p for _,_,p in self.regions if p.low<=address<p.high)
        pool.release(address,size)

    def query(self,flags=0):
        if not self.valid(flags,True):return 0
        pools=self.matching(flags)
        if flags&0x80000:return sum(p.high-p.low for p in pools)
        if not flags&0x20000:return sum(p.available for p in pools)
        intervals=[(a,b) for p in pools for a,b in p.free]
        if flags&0x100000:return max((b-a for a,b in intervals),default=0)
        return max((min(b,(bank+1)*65536)-max(a,bank*65536)
                    for a,b in intervals for bank in range(a//65536,(b-1)//65536+1)),default=0)

    def memory_type(self,address):
        return next((attrs for _,attrs,p in self.regions if p.low<=address<p.high),0)


def system_trace(regions,seed=0x8165011):
    heap=System(regions);slots=[None]*8;operations=[];snapshots=[]
    def op(code,slot=0,size=0,flags=0):
        result=0
        if code==0:
            assert slots[slot] is None
            result=heap.allocate(size,flags)
            if result:slots[slot]=(result,size)
        elif code==1:
            address,n=slots[slot];heap.release(address,n);slots[slot]=None
        elif code==2:result=heap.query(flags)
        elif code==3:result=heap.memory_type(size)
        operations.append((code,slot,0,0,size,flags,0))
        extents=[(p.low,a,b-a) for _,_,p in heap.regions for a,b in p.free]
        snapshots.append((result,heap.query(),heap.query(0x20000),heap.query(0x120000),heap.query(0x80000),extents))
    op(0,0,8);op(0,1,65536);op(0,2,13);op(1,0);op(1,2);op(1,1)
    op(0,0,65537);op(0,0,65537,0x100000);op(0,1,65528);op(1,0);op(1,1)
    for flags in (2,4,256,512,1024,0x40000,0x20000000,0x20000,0x80000,0x18,0x100008,8):
        op(0,0,8,flags);op(2,flags=flags)
    for flags in (0,1,0x10,0x80000000,0x10000,0x100000,0x80000,0x20000,0x120000,0xa0000):op(2,flags=flags)
    for size in (0,0xffffffff,0xfffffff8,0xfffffff9):op(0,0,size,0x100000)
    for address in (0,1,0x10000,0x70000,0xffffff,*[r[0] for r in regions],*[r[1]-1 for r in regions]):op(3,size=address)
    rng=random.Random(seed)
    for _ in range(80):
        slot=rng.randrange(8)
        if slots[slot]:op(1,slot)
        else:op(0,slot,rng.choice((1,9,63,4097,65528,65536,65537,131073)),rng.choice((0,1,0x10,0x100000,0x80100011)))
    for slot in range(8):
        if slots[slot]:op(1,slot)
    return operations,snapshots


def trace(seed=0x816a110c):
    pool=Pool(0x40000,0x60000)
    slots=[None]*8;operations=[];snapshots=[]
    def op(code,slot,size=0,contained=0,offset=0):
        result=0
        if code==0:
            assert slots[slot] is None
            result=pool.allocate(size,contained)
            if result:slots[slot]=(result,size)
        elif code==1:
            address,n=slots[slot];pool.release(address,n);slots[slot]=None
        elif code==2:
            address,_=slots[slot];pool.release(address+offset,size)
        operations.append((code,slot,contained,0,size,offset))
        snapshots.append((result,pool.available,list(pool.free)))
    op(0,0,65537);op(0,1,13);op(1,0);op(1,1)
    # A prefix before a whole-bank ordinary block, then two-sided coalescing.
    op(0,0,8);op(0,1,65536,1);op(0,2,24);op(1,0);op(1,2);op(1,1)
    op(0,0,131072);op(0,1,1);op(1,0)
    op(0,0,0);op(0,0,0xffffffff)
    rng=random.Random(seed)
    for _ in range(160):
        slot=rng.randrange(8)
        if slots[slot] is not None:op(1,slot)
        else:op(0,slot,rng.choice([1,7,8,9,24,63,512,4097,65528,65535,65536,65537]),rng.randrange(2))
    for slot in range(8):
        if slots[slot] is not None:op(1,slot)
    # Explicit private subranges: include the unaligned interval [base+9,+16).
    op(0,0,64);op(2,0,7,offset=9);op(2,0,8);op(2,0,48,offset=16)
    assert pool.free==[(pool.low,pool.high)]
    return operations,snapshots
