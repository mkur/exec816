"""Physical QED navigation/geometry with independent document and pixel oracles."""
import struct
from native_program import require
from qed_editing_observe import Editor
from gem_render_oracle import DESKTOP_PALETTE


def document(e):
    w=e.get(e.sy['used_list'],4)
    return list(struct.unpack('<4i',e.b.memdump(w+e.offsets[21],16)))


def origin(e,x=None,y=None):
    address=e.get(e.sy['used_list'],4)+e.offsets[21]
    conditions=[]
    for offset,value in ((0,x),(4,y)):
        if value is not None:
            conditions.extend(['dw($%x)=%d'%(address+offset,value&65535),
                'dw($%x)=%d'%(address+offset+2,value>>16)])
    if conditions:e.reach('&'.join(conditions))
    values=document(e)
    require(x is None or values[0]==x,'Wrong horizontal viewport: '+str(values))
    require(y is None or values[1]==y,'Wrong vertical viewport: '+str(values))
    return values


def wait_columns(e,value=None,different=None):
    address=e.get(e.sy['used_list'],4)+e.offsets[22]-4
    e.reach('dw($%x)%s%d'%(address,'=' if value is not None else '!=',
        value if value is not None else different))
    e.frames(2)


def drag(e,start,end):
    phase=next(d['address'] for d in e.p['image']['data'] if d['name'].startswith('M_DESKDRAG_PHASE_'))
    e.move(*start);e.b._cmd_ok('MOUSE AT 2000 0 0 1')
    e.reach('db($%x)!=0'%phase)
    e.move(*end);e.frames(2)
    e.b._cmd_ok('MOUSE AT 2000 0 0 0')
    e.reach('db($%x)=0'%phase);e.frames(50)


def accepted_geometry(e,work):
    # Wait for the application to accept the physical gesture's proposal.
    w=e.get(e.sy['used_list'],4)+e.offsets[22]
    e.reach('&'.join('dw($%x)=%d'%(w+i*2,v) for i,v in enumerate(
        [work[0],work[1],work[2]-work[0],work[3]-work[1]])))
    e.frames(40)


def peer_pixels(e,name,covered=()):
    for attempt in range(120):
        try:return _peer_pixels(e,name,covered)
        except RuntimeError as error:
            if ': peer pixel ' not in str(error) or attempt==119:raise
            e.frames(2)


def _peer_pixels(e,name,covered):
    target=e.p['output'].parent/(name+'.bgra')
    frame=e.b.rawscreen(str(target));raw=target.read_bytes()
    colors=[bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[i*3:i*3+3])[::-1] for i in range(4)]
    # Accepted peer outer (0,60,224,112); work (8,71,208,99).
    checked=0
    pointer=[e.get(e.input_at(n)) for n in ('cursorX','cursorY')]
    for y in range(71,170):
        for x in range(8,216):
            if any(l<=x<r and t<=y<b for l,t,r,b in covered):continue
            if pointer[0]<=x<pointer[0]+16 and pointer[1]<=y<pointer[1]+16:continue
            pen=3
            if 16<=x<48 and 79<=y<87:
                ch=b'Peer'[(x-16)//8]
                if e.font[(y-79)*256+ch]&(128>>((x-16)%8)):pen=1
            at=y*frame.stride+64+x*4
            require(raw[at:at+3]==colors[pen],f'{name}: peer pixel {x},{y}')
            checked+=1
    e.scene.setdefault('peer_pixels',[]).append(dict(name=name,checked=checked))


def interact(b,p,app,record,owner,scenario='all'):
    e=Editor(b,p,app,record,owner);cycle=e.native('cycle')
    e.scene['scenario']=scenario
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    e.check('viewport-empty',[b''],0,0)
    if cycle:
        b.memload(e.at('control'),struct.pack('<H',cycle+1))
        return None if cycle==3 else e.retire_key('Q',ctrl=True)

    e.key('RETURN');e.key('A')
    tabs=2 if scenario=='geometry' else 513
    for i in range(tabs):
        e.key('TAB',settle=2)
        if i%64==63:print('QED viewport: literal tabs',i+1,flush=True)
    e.key('Z');line=b'a'+b'\t'*tabs+b'z';lines=[b'',line];end=len(line)
    prefix='short' if tabs==2 else 'wide'
    if tabs==513:require(len(line.expandtabs(8))*8>32767,'Long-line pixel coordinate did not cross WORD')
    e.check(prefix+'-line-end',lines,end,1)
    columns=e.get(e.get(e.sy['used_list'],4)+e.offsets[22]-4)
    origin(e,x=max(0,len(line.expandtabs(8))+1-columns))
    e.caret_pixels(prefix+'-line-caret',lines,end,1)
    e.key('MINUS',ctrl=True);e.check(prefix+'-up',lines,0,0);origin(e,x=0)
    e.key('EQUALS',ctrl=True);e.check(prefix+'-desired-column',lines,end,1)
    e.key('MINUS',ctrl=True);e.key('ASTERISK',ctrl=True)
    e.check(prefix+'-line-start',lines,0,1);origin(e,x=0)
    e.caret_pixels(prefix+'-start-caret',lines,0,1)

    b.memload(e.at('control'),struct.pack('<H',1))
    e.reach('dw($%x)=100'%e.at('phase'));e.frames(40)
    e.covered=[(0,60,224,172)]
    e.check('covered-document',lines,0,1);peer_pixels(e,'peer-on-top')
    # Native title presses on an inactive GEM window first request topping.
    e.click(100,44)
    drag(e,(100,44),(116,44));e.covered=[]
    accepted_geometry(e,[40,60,624,228])
    e.check('moved-document',lines,0,1)
    require(e.geometry()['bounds']==[32,39,640,239],'Move was not accepted')
    peer_pixels(e,'peer-behind',covered=[(32,39,640,239)])
    e.click(28,65);e.covered=[(0,60,224,172)]
    e.check('covered-after-move',lines,0,1);peer_pixels(e,'peer-restored')
    b.memload(e.at('control'),struct.pack('<H',100))
    e.reach('dw($%x)=101'%e.at('phase'));e.covered=[]
    e.check('exposed-document',lines,0,1)
    e.caret_pixels('exposed-caret',lines,0,1)
    if scenario=='long':
        b.memload(e.at('control'),struct.pack('<H',101))
        e.key('Q',ctrl=True);return e.alert(2,retiring=True)

    old=e.geometry()['bounds'];e.click(old[2]-8,old[1]+5)
    wait_columns(e,different=73)
    e.check('full-document',lines,0,1)
    require(e.geometry()['work'][2]-e.geometry()['work'][0]>584,'Full did not enlarge the work area')
    full=e.geometry()['bounds'];e.click(full[2]-8,full[1]+5)
    wait_columns(e,value=73)
    e.check('restored-document',lines,0,1)
    require(e.geometry()['bounds']==old,'Full did not restore accepted geometry')
    drag(e,(old[2]-8,old[3]-6),(old[2]-88,old[3]-46))
    wait_columns(e,value=63)
    e.check('resized-document',lines,0,1)
    bounds=e.geometry()['bounds'];work=e.geometry()['work']
    require(bounds[2]-bounds[0]<old[2]-old[0],'Sizer did not shrink the document')

    for _ in range(32):e.key('RETURN',settle=2)
    lines=[b'']*33+[line]
    e.check('vertical-end',lines,0,33)
    rows=e.get(e.get(e.sy['used_list'],4)+e.offsets[22]-2)
    maximum=len(lines)-rows;origin(e,y=maximum)
    e.click(bounds[2]-8,work[1]+5)
    e.check('vertical-up',lines,0,33);origin(e,y=maximum-1)
    e.click(bounds[2]-8,bounds[3]-16)
    e.check('vertical-down',lines,0,33);origin(e,y=maximum)
    e.click(bounds[2]-8,work[1]+15)
    e.check('vertical-page-up',lines,0,33);origin(e,y=max(0,maximum-rows))
    e.click(bounds[2]-8,bounds[3]-26)
    e.check('vertical-page-down',lines,0,33);origin(e,y=maximum)
    top,bottom=work[1]+11,bounds[3]-22
    thumb=(bottom-top)*(rows*1000//len(lines))//1000
    drag(e,(bounds[2]-8,bottom-thumb//2),(bounds[2]-8,top+thumb//2))
    e.check('vertical-thumb-top',lines,0,33);origin(e,y=0)
    e.key('EQUALS',ctrl=True);e.check('cursor-revealed',lines,0,33)
    origin(e,y=maximum);e.caret_pixels('scrolled-caret',lines,0,33)
    b.memload(e.at('control'),struct.pack('<H',101))
    e.key('Q',ctrl=True);return e.alert(2,retiring=True)
