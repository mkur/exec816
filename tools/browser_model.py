"""Private Files observation offsets, checked by the emitted C layout probe."""
FIELDS=dict(ready=8,work=26,tree=170,menu=174,path=178,status=306,target=434,
    entries=2094,count=2358,first=2360,visible=2362,selected=2364,down=2366,
    armed=2368,truncated=2370,launches=2372,paints=2376,child=2380,result=2384,
    bar=2428,menuInstalled=2668,menuEnabled=2670)
SIZE=2672
LAYOUT=[('Browser size',SIZE)]+[('Browser '+n,v) for n,v in FIELDS.items()]
ROWS=16
OBJECTS=21
ENTRY_BYTES=112


def listing(session,base):
    count=session.number(base+FIELDS['count'],2)
    at=session.number(base+FIELDS['entries'],4)
    raw=session.b.memdump(at,count*ENTRY_BYTES)
    return [raw[i*ENTRY_BYTES:i*ENTRY_BYTES+108].split(b'\0')[0].decode('ascii') for i in range(count)]


def select(session,base,name,click):
    """Reach a retained directory entry through the actual scrollbar, then click."""
    from native_program import require
    names=listing(session,base)
    require(name in names,'Missing Files entry '+name)
    index=names.index(name)
    for _ in range(256):
        first=session.number(base+FIELDS['first'],2)
        visible=session.number(base+FIELDS['visible'],2)
        x,y,w,h=[session.number(base+FIELDS['work']+i*2,2) for i in range(4)]
        if first<=index<first+visible:
            click(x+40,y+36+(index-first)*12);return
        click(x+w+8,y+8 if index<first else y+h-8)
        session.frames(60)
    raise RuntimeError('Files scrollbar did not reach '+name)
