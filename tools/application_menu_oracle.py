"""Recompose an application menu from its source OBJECT tree, never hit caches."""
import struct
import sys
from native_program import ROOT, require
from generate_aes_server import ABI, layout, expected_layout


def active_tree(bridge, contexts, bounds):
    records=layout();request=records['Request'];view=records['WindowView']
    offset=dict(expected_layout())['C context menuTree']
    found=[]
    for (at,) in struct.iter_unpack('<I',bridge.memdump(contexts,4*ABI['constants']['CONTEXTS'])):
        if not at:continue
        raw=bridge.memdump(at,offset+4)
        target=int.from_bytes(raw[request['fields']['view']:request['fields']['view']+3],'little')
        tree=int.from_bytes(raw[offset:offset+4],'little')
        if not target or not tree:continue
        state=bridge.memdump(target,view['fields']['visibleCount'])
        if struct.unpack_from('<4h',state,view['fields']['bounds'])==tuple(bounds) and \
                int.from_bytes(state[view['fields']['shown']:view['fields']['shown']+2],'little'):
            found.append(tree)
    require(len(found)<=1,'Ambiguous menu source owner')
    return found[0] if found else 0


def source(bridge, address):
    objects=[];labels={}
    for i in range(32):
        obj=list(struct.unpack('<hhhHHHIhhhh',bridge.memdump(address+24*i,24)))
        if obj[3] in (28,32):
            labels[i+1]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii')
            obj[6]=i+1
        objects.append(obj)
        if obj[4]&32:break
    parents={}
    for i,obj in enumerate(objects):
        child=obj[1]
        while child>=0 and child!=i:
            parents[child]=i
            child=objects[child][0]
    positions=[]
    for i,obj in enumerate(objects):
        x=y=0;at=i
        while at>0:
            x+=objects[at][7];y+=objects[at][8];at=parents[at]
        positions.append((x,y))
    return objects,labels,positions


def draw(bridge,result,address,popup=False,heading=0,selected=-1,opened=False):
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    objects,labels,positions=source(bridge,address)
    bar=objects[0][1];active=objects[bar][1];boxes=objects[0][2]
    title=objects[active][1];box=objects[boxes][1]
    for _ in range(heading):title=objects[title][0];box=objects[box][0]
    if popup:
        width,height=objects[box][9:11]
        x=max(0,min(positions[box][0],640-width))
        y=max(16,min(positions[box][1],240-height))
        bounds=(x,y,x+width,y+height);scope=box
        origin=(x-positions[box][0],y-positions[box][1])
        if selected>=0:objects[selected][5]|=1
    else:
        bounds=(0,0,432,16);scope=bar;origin=(0,-positions[bar][1])
        if opened:objects[title][5]|=1
    objects[0][7:9]=origin
    tree=[a.Obj(*obj) for obj in objects]
    device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
    device.dev.s.mem[:76800]=result.packed()
    aes=a.AES(device,tree,{k:a.Text(value) for k,value in labels.items()})
    aes.gsx_start()
    left,top,right,bottom=bounds
    aes.gsx_sclip(a.Rect(left,top,right-left,bottom-top))
    aes.ob_draw(scope,7)
    result.pixels[:]=bytes(n for byte in device.dev.s.mem[:76800] for n in (byte>>4,byte&15))
    return bounds
