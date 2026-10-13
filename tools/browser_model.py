"""Private Files observation offsets, checked by the emitted C layout probe."""
FIELDS=dict(ready=8,work=26,tree=170,menu=174,path=178,status=306,target=434,
    entries=2094,count=2358,first=2360,visible=2362,selected=2364,down=2366,
    armed=2368,truncated=2370,launches=2372,paints=2376,child=2380,result=2384,
    bar=2428,menuInstalled=2740,menuEnabled=2742,dialogTree=2744,dialogTed=2888,
    editText=2916,dialog=3044,focus=3046,editIndex=3048,dialogError=3050)
SIZE=3861
for name in ('menuInstalled','menuEnabled','dialogTree','dialogTed','editText','dialog','focus','editIndex','dialogError'):
    FIELDS[name]+=144
FIELDS.update(stock=3218,icons=3222,iconView=3766,sortNames=3768,columns=3770,armedClicks=3772,full=3774,restore=3776,totalBytes=3784,information=3788,applicationMenu=3853,desktop=3857)
for name in FIELDS:
    if FIELDS[name]>FIELDS['bar']:FIELDS[name]+=48
FIELDS.update(selection=3909,selectionCount=3941,selectionDirectories=3943,armedModifiers=3945)
SIZE=3947
for name in FIELDS:
    if FIELDS[name]>FIELDS['dialogTree']:FIELDS[name]+=24
SIZE+=24
FIELDS['refreshPending']=SIZE
SIZE+=2
for name in FIELDS:
    if FIELDS[name]>FIELDS['icons']:FIELDS[name]+=64
SIZE+=64
FIELDS['keyboardFocus']=SIZE
SIZE+=2
FIELDS['scan']=FIELDS['stock']-20
CONTENT_TOP=20
LAYOUT=[('Browser size',SIZE)]+[('Browser '+n,v) for n,v in FIELDS.items()]
ROWS=16
OBJECTS=25
ENTRY_BYTES=112


def listing(session,base):
    count=session.number(base+FIELDS['count'],2)
    at=session.number(base+FIELDS['entries'],4)
    raw=session.b.memdump(at,count*ENTRY_BYTES)
    return [raw[i*ENTRY_BYTES:i*ENTRY_BYTES+108].split(b'\0')[0].decode('ascii') for i in range(count)]


def wait_listing(session,base,limit=50):
    """Wait for navigation to release its directory lock before heap baselines.

    FileScan is the 20-byte public helper immediately before stock. The status
    can still describe the previous directory while the new scan owns its lock.
    """
    from native_program import require
    for _ in range(limit):
        status=session.b.memdump(base+FIELDS['status'],128).split(b'\0')[0]
        path=session.b.memdump(base+FIELDS['path'],128).split(b'\0')[0]
        if not session.number(base+FIELDS['scan'],4) and (b' bytes in ' in status or b' selected' in status or status.startswith((b'First 256 entries',b'Delete complete',b'Delete cancelled',b'Delete failed'))):
            session.frames(80);return
        session.frames(40)
    require(False,'Directory snapshot did not finish: '+repr((path,status)))


def select(session,base,name,click,stable_snapshot=False):
    """Reach a retained directory entry through the actual scrollbar, then click."""
    from native_program import require
    # Directory enumeration can span many disk turns. The application publishes
    # its path as status after the complete snapshot, then redraws the rows.
    for attempt in range(50):
        names=listing(session,base)
        status=session.b.memdump(base+FIELDS['status'],128).split(b'\0')[0]
        path=session.b.memdump(base+FIELDS['path'],128).split(b'\0')[0]
        if name in names and (status==path or not status.startswith(b'SYS:')):break
        session.frames(40)
    require(name in names,'Missing Files entry '+name+': '+repr((path,status,names)))
    for _ in range(256):
        # A mutation may finish rebuilding/sorting the retained snapshot while
        # the first scrollbar click is in flight. Resolve the name again; an
        # index captured from the preceding directory can become unreachable.
        if not stable_snapshot:names=listing(session,base)
        if name not in names:
            session.frames(40);continue
        index=names.index(name)
        first=session.number(base+FIELDS['first'],2)
        visible=session.number(base+FIELDS['visible'],2)
        x,y,w,h=[session.number(base+FIELDS['work']+i*2,2) for i in range(4)]
        if first<=index<first+visible:
            if session.number(base+FIELDS["iconView"],2):
                columns=session.number(base+FIELDS["columns"],2)
                click(x+48+(index-first)%columns*104,y+CONTENT_TOP+12+(index-first)//columns*40)
            else:click(x+40,y+CONTENT_TOP+4+(index-first)*12)
            return
        click(x+w+8,y+8 if index<first else y+h-8)
        session.frames(60)
    raise RuntimeError('Files scrollbar did not reach '+name)
