"""Parent-based traversal expectations and donor primitive pixel rendering."""
import copy
import hashlib
import struct
import sys

from native_program import ROOT, require


def make_tree(parents, positions, sizes=None, kind=20):
    children={i:[] for i in range(len(parents))}
    for i,parent in enumerate(parents):
        if parent>=0:children[parent].append(i)
    nodes=[]
    for i,parent in enumerate(parents):
        siblings=children.get(parent,[])
        next_=siblings[siblings.index(i)+1] if parent>=0 and siblings[-1]!=i else parent
        nodes.append([next_,children[i][0] if children[i] else -1,
            children[i][-1] if children[i] else -1,kind,
            32 if i==len(parents)-1 else 0,0,0x1170+i%7,
            *positions[i],*(sizes[i] if sizes else (24,12))])
    return dict(parents=parents,nodes=nodes)


def corpus():
    parents=[-1,0,1,1,0,4,4]
    positions=[(57,81),(10,10),(5,5),(36,8),(120,8),(6,6),(40,20)]
    sizes=[(220,100),(64,40),(24,12),(24,12),(80,48),(24,12),(24,12)]
    cousins=make_tree(parents,positions,sizes)
    chain=make_tree([-1]+list(range(17)),[(48,44)]+[(2,3)]*17,
        [(180-i*3,140-i*3) for i in range(18)])
    wide=make_tree([-1]+[0]*32,[(48,56)]+[(8+i%8*38,8+i//8*28) for i in range(32)],
        [(320,128)]+[(24,12)]*32)
    fail=make_tree([-1,0,1],[(57,81),(4,10),(4,10)],[(80,8),(64,8),(48,8)])
    result=[]
    def add(name,tree,start=0,depth=8,clip=(0,0,640,240),mode=0,hidden=()):
        tree=copy.deepcopy(tree)
        for i in hidden:tree['nodes'][i][4]|=128
        result.append(dict(name=name,tree=tree,start=start,depth=depth,clip=clip,mode=mode))
    add('single_leaf',make_tree([-1],[(57,81)]))
    add('wide_siblings',wide)
    add('cousins',cousins)
    add('maximum_relative_depth',make_tree([-1]+list(range(8)),
        [(64,60)]+[(2,3)]*8,[(180-i*8,140-i*8) for i in range(9)]))
    add('depth_zero',cousins,depth=0)
    add('depth_negative',cousins,depth=-2)
    add('depth_clamped',chain,depth=99)
    add('nonroot_leaf',cousins,start=3)
    add('nonroot_subtree',cousins,start=4)
    add('nonroot_relative_limit',chain,start=8)
    add('hidden_root',cousins,hidden=(0,))
    add('hidden_branch',cousins,hidden=(1,))
    add('hidden_leaf',cousins,hidden=(2,))
    outside=make_tree([-1,0],[(40,40),(100,50)],[(24,12),(100,20)],kind=25)
    outside['nodes'][1][3]=20
    add('child_outside_clipped_parent',outside,clip=(130,80,150,40))
    add('negative_origin',make_tree([-1,0,1],[(-40,-20),(100,100),(25,-12)],
        [(240,180),(80,40),(32,16)]))
    outlined=copy.deepcopy(cousins);outlined['nodes'][0][6]=0xff1173
    add('partial_damage_outward_border',outlined,clip=(75,75,40,8))
    add('empty_width',cousins,clip=(0,0,0,240))
    add('disjoint_visibility',wide,mode=1)
    add('covered_owner',cousins,mode=2)
    add('borrow_failure_after_descent',fail,mode=3)
    add('recovery_after_failure',fail)
    moved=copy.deepcopy(cousins);moved['nodes'][0][7:9]=[211,50]
    moved['nodes'][1][7:9]=[-40,30]
    add('changed_positions_next_call',moved)
    add('empty_height',cousins,clip=(0,0,640,0))
    require(len(result)==23,'Traversal corpus and emitted fixture differ')
    return result


def visits(case):
    """Interpret explicit parents, independently of GEM next/head/tail walking."""
    tree=case['tree'];parents=tree['parents'];nodes=tree['nodes']
    result=[]
    def absolute(i):
        x=y=0
        while i>=0:
            x+=nodes[i][7];y+=nodes[i][8];i=parents[i]
        return x,y
    def descend(i,level):
        if nodes[i][4]&128:return
        result.append((i,*absolute(i)))
        if level<min(case['depth'],8):
            for child,parent in enumerate(parents):
                if parent==i:descend(child,level+1)
    if case['clip'][2]>0 and case['clip'][3]>0:descend(case['start'],0)
    return result


def intersection(a,b):
    l,t,r,bt=max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])
    return (l,t,r,bt) if l<r and t<bt else None


def geometry(case,work):
    x,y,w,h=case['clip'];clip=(x,y,x+w,y+h)
    wx,wy,ww,wh=work;visible=[(wx,wy,wx+ww,wy+wh)]
    if case['mode']==1:visible=[(wx,wy,173,wy+wh),(181,wy,wx+ww,wy+wh)]
    if case['mode']==2:visible=[]
    damage=[];borrows=0
    for i,x,y in visits(case):
        node=case['tree']['nodes'][i]
        thickness=(node[6]>>16)&255
        border=256-thickness if thickness>127 else 0
        full=(x-border,y-border,x+node[9]+border,y+node[10]+border)
        area=intersection(full,clip)
        if not area:continue
        damage.append(area)
        rows=32 if full[3]-full[1]<=32 else 16
        for part in visible:
            hit=intersection(area,part)
            if hit:borrows+=(hit[3]-hit[1]+rows-1)//rows
    if damage:
        bounds=(min(v[0] for v in damage),min(v[1] for v in damage),
                max(v[2] for v in damage),max(v[3] for v in damage))
        bounds=intersection(bounds,(wx,wy,wx+ww,wy+wh))
    else:bounds=None
    return visible,bounds,min(3,borrows) if case['mode']==3 else borrows


def paint(device,case,work):
    import aesref as a
    nodes=[a.Obj(*node) for node in case['tree']['nodes']]
    aes=a.AES(device,nodes,{});aes.gsx_start()
    visible,_,_=geometry(case,work)
    x,y,w,h=case['clip'];clip=(x,y,x+w,y+h)
    # Render primitive objects at parent-derived coordinates in preorder.
    for obj,x,y in visits(case):
        for part in visible:
            hit=intersection(clip,part)
            if hit:
                l,t,r,b=hit;aes.gsx_sclip(a.Rect(l,t,r-l,b-t))
                aes.just_draw(obj,x,y)


def physical(b,p,foreign,report,reach):
    from gem_render_oracle import DESKTOP_PALETTE as palette,PENS,font_bytes
    from test_gem_interactive import pixels
    from desktop_oracle import compose
    from bitmap_console_oracle import Terminal
    from desktop_mouse import schedule
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import vdiref as v
    sy=foreign['symbols'];out=p['output'].parent
    get=lambda name,n=2:int.from_bytes(b.memdump(sy[name],n),'little')
    def phase(n):reach('dw($%x)=%d'%(sy['TreePhase'],n))
    def frames():reach('@frame>=%d'%(b.eval_expr('@frame')+12))
    position=schedule(b,p,(68,87),(639,239))
    frames()
    rgb=bytes((c&254)+(c>>7) for c in palette)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    cases=corpus();report['object_traversal']=[]
    for i,case in enumerate(cases):
        phase(i*2+1)
        nodes=case['tree']['nodes']
        b.memload(sy['TreeObjects'],b''.join(struct.pack('<hhhHHHIhhhh',*n) for n in nodes))
        request=[case['start'],case['depth'],*case['clip'],case['mode'],0]
        b.memload(sy['TreeRequest'],struct.pack('<8h',*request))
        b.poke16(sy['TreeGo'],i*2+1);phase(i*2+2);frames()
        work=struct.unpack('<4h',b.memdump(sy['TreeWork'],8))
        state=struct.unpack('<8h',b.memdump(sy['TreeState'],16))
        visible,damage,borrows=geometry(case,work)
        require(state[0]==(case['mode']!=3),'Traversal result: '+case['name'])
        require(not state[2] and state[3]==(case['mode']==3),'Traversal failure/busy state')
        require(bool(state[4]&1)==bool(damage),'Traversal changed extent presence: '+case['name'])
        if damage:require(struct.unpack('<4h',b.memdump(sy['TreeDamage'],8))==damage,
            'Traversal changed extent: '+case['name'])
        require(state[5]==borrows,'Traversal borrow count: '+case['name'])
        row=dict(case=case['name'],state=list(state),expected_damage=damage,borrows=borrows)
        if case['mode']!=3:
            device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
            x,y,w,h=work;device.dev.fill_rect(x,y,x+w-1,y+h-1,5)
            paint(device,case,work)
            expected=device.dev.s.mem[:76800]
            frame=b.rawscreen(str(out/'tree-scanout.bgra'));raw=(out/'tree-scanout.bgra').read_bytes()
            actual=bytearray()
            for yy in range(y,y+h):
                for xx in range(x,x+w):
                    want=colors[(expected[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
                    offset=yy*frame.stride+(xx+16)*4
                    require(raw[offset:offset+3]==want,'Traversal pixels '+case['name']+f' at {xx},{yy}')
                    actual+=want
            row['pixel_sha256']=hashlib.sha256(actual).hexdigest()
        report['object_traversal'].append(row)
        print('Traversal pass:',case['name'],flush=True)
        b.poke16(sy['TreeGo'],i*2+2)
    phase(1000);frames()
    raw=b.memdump(sy['TreePeerObjects'],4*24)
    peer=dict(tree=dict(parents=[-1,0,1,0],nodes=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(4)]),
        start=1,depth=8,clip=(0,0,640,240),mode=0)
    primary=copy.deepcopy(cases[-1]);primary.update(start=0,depth=8,clip=(0,0,640,240),mode=0)
    def external(r,title,bounds):
        require(title in (b'Tree primary',b'Tree peer'),'Unexpected traversal client')
        is_peer=title==b'Tree peer'
        work=struct.unpack('<4h',b.memdump(sy['TreePeerWork' if is_peer else 'TreeWork'],8))
        device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
        x,y,w,h=work;device.dev.fill_rect(x,y,x+w-1,y+h-1,7 if is_peer else 5)
        paint(device,peer if is_peer else primary,work)
        packed=device.dev.s.mem
        for yy in range(y,y+h):
            for xx in range(x,x+w):r.pixels[yy*640+xx]=(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15
    expected=compose(b,p,font_bytes(out/'selected/src/vdi/font8x8.c'),Terminal(64,20),
        position,external,menu_contexts=sy['contexts'])
    report['object_traversal_pair']=dict(main_draws=get('TreeMainDraws'),peer_draws=get('TreePeerDraws'),
        pixels=pixels(b,out,expected,palette=palette))
    require(get('TreeMainDraws')==32 and get('TreePeerDraws')>0,'Traversal caller concurrency')
    b.poke16(sy['TreeGo'],1000)
