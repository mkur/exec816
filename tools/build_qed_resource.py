#!/usr/bin/env python3
"""Adapt the pinned English QED RSC, retaining native-scope object identities."""
import argparse,json,re,struct
from pathlib import Path
from native_program import ROOT,require,sha256
from prepare_qed import PORT,prepare


def resource(work):
    work=Path(work); donor=work/'source/qed'
    data=(donor/'en/qed_en.rsc').read_bytes()
    original=work/'qed-donor.h'
    header=(original if original.exists() else donor/'src/qed.h').read_text(encoding='latin1')
    ids={name:int(value) for name,value in re.findall(r'^#define\s+(\w+)\s+(\d+)',header,re.M)}
    selection=json.loads((PORT/'resource-selection.json').read_text())
    h=struct.unpack_from('>18H',data)
    def string(at):return data[at:data.index(0,at)].decode('latin1')
    def decode(n):return (n&255)*8+((n>>8)-256 if n&32768 else n>>8)
    trees=[];mapping={};teds=[];icons=[]
    for tree_name in selection['trees']:
        mapping[tree_name]=len(trees)
        at=struct.unpack_from('>I',data,h[9]+4*ids[tree_name])[0];tree=[]
        while True:
            o=list(struct.unpack_from('>hhhHHHIHHHH',data,at+24*len(tree)))
            o[3]&=255;old_flags=o[4];o[4]&=1|2|4|8|16|32|128;o[5]&=1|4|8
            if old_flags&64:o[4]|=1|4
            if o[3]==23:o[3]=25;o[6]=0 # unused image decoration
            elif o[3]==27:o[3]=26;o[6]='v'
            elif o[3] in (26,28,32):o[6]=string(o[6])
            elif o[3] in (21,22,29,30):
                ted=list(struct.unpack_from('>III8h',data,o[6]));teds.append(ted)
                for i in range(3):ted[i]=string(ted[i])
                o[6]=('ted',len(teds)-1)
            elif o[3]==31:
                icon=list(struct.unpack_from('>IIIH10h',data,o[6]));n=(icon[8]//16)*icon[9]*2
                icon[:3]=[data[icon[0]:icon[0]+n],data[icon[1]:icon[1]+n],string(icon[2])]
                icons.append(icon);o[6]=('icon',len(icons)-1)
            else:require(o[3] in (20,25),'Unclassified retained QED object')
            o[7:]=map(decode,o[7:]);tree.append(o)
            if old_flags&32:break
        if tree_name=='MENUTREE':tree=menu(selection['menu'],mapping)
        if tree_name=='REPLACE':
            for name in selection['disabled_find_objects']:
                require(name in ids,'Unknown deferred Find object: '+name)
                tree[ids[name]][5]|=8
        trees.append(tree)
    # Repack only retained descriptors, strings and bitmap planes. Every TED text
    # has separate writable backing; its capacity survives the load relocation.
    count=sum(map(len,trees));object_at=36;ted_at=object_at+24*count
    icon_at=ted_at+28*len(teds);tree_at=icon_at+34*len(icons)
    free_at=tree_at+4*len(trees);blob_at=free_at+4*h[15];blob=bytearray()
    def put(value,capacity=0):
        value=value.encode('latin1')+b'\0' if isinstance(value,str) else value
        offset=blob_at+len(blob);blob.extend(value.ljust(max(len(value),capacity),b'\0'))
        if len(blob)&1:blob.append(0)
        return offset
    ted_bytes=bytearray();icon_bytes=bytearray()
    for t in teds:
        t[0]=put(t[0],max(t[9],1));t[1]=put(t[1]);t[2]=put(t[2])
        ted_bytes.extend(struct.pack('>III8h',*t))
    for icon in icons:
        icon[:3]=[put(v) for v in icon[:3]]
        icon_bytes.extend(struct.pack('>IIIH10h',*icon))
    free=[string(struct.unpack_from('>I',data,h[5]+4*i)[0]) for i in range(h[15])]
    free_bytes=b''.join(struct.pack('>I',put(s)) for s in free)
    objects=bytearray();index=bytearray();offset=object_at
    def encode(n):return ((n%8)<<8)|(n//8)
    for tree in trees:
        index.extend(struct.pack('>I',offset));offset+=24*len(tree)
        for o in tree:
            spec=o[6]
            if isinstance(spec,str):spec=put(spec)
            elif isinstance(spec,tuple):spec=(ted_at+spec[1]*28 if spec[0]=='ted' else icon_at+spec[1]*34)
            objects.extend(struct.pack('>hhhHHHIHHHH',*o[:6],spec,*(encode(n) for n in o[7:])))
    total=blob_at+len(blob)
    require(count<=256 and len(trees)<=16 and max(map(len,trees))<=64 and total<=65535,
            'Adapted QED resource exceeds bounded native capacities')
    words=[0,object_at,ted_at,icon_at,0,free_at,blob_at,0,0,tree_at,count,len(trees),len(teds),len(icons),0,len(free),0,total]
    payload=struct.pack('>18H',*words)+objects+ted_bytes+icon_bytes+index+free_bytes+blob
    require(len(payload)==total,'QED resource extent mismatch')
    # Preserve other local indices. Discard donor menu identifiers, including
    # deferred entries, so stale code fails compilation rather than aliasing.
    header=re.sub(r'^#define\s+\w+\s+\d+[^\n]*tree MENUTREE[^\n]*\n','',header,flags=re.M)
    updates=dict(mapping,NUM_OBS=count,NUM_TREE=len(trees),NUM_TI=len(teds),NUM_IB=len(icons),NUM_BB=0,NUM_IMAGES=len(icons)*2)
    for name,value in updates.items():
        header=re.sub(r'^(#define\s+'+name+r'\s+)\d+',lambda m:m[1]+str(value),header,flags=re.M)
    header+='\n/* Native compact menu identifiers. */\n'+''.join(f'#define {k} {v}\n' for k,v in mapping.items() if k.startswith(('M','T')) and k not in selection['trees'])
    return payload,header,dict(trees={name:len(tree) for name,tree in zip(selection['trees'],trees)},
        objects=count,teds=len(teds),icons=len(icons),free_strings=len(free),bytes=total,identifiers=mapping)


def menu(groups,mapping):
    def node(kind,x,y,w,h,spec=0,flags=0):return [-1,-1,-1,kind,flags,0,spec,x,y,w,h]
    # Standard root -> bar -> active headings, and root -> popup boxes.
    height=json.loads((ROOT/'abi/desktop.json').read_text())['constants']['MENU_BAR_HEIGHT']
    tree=[node(25,0,0,640,240),node(20,0,0,640,height,0x1170),node(25,0,0,432,height)]
    x=8
    for title,label,items in groups:
        mapping[title]=len(tree);tree.append(node(32,x,0,len(label)*8,height,label));x+=len(label)*8
    boxes=len(tree);tree.append(node(25,0,height,640,240-height));popups=[]
    for title,label,items in groups:
        popups.append(len(tree));tree.append(node(20,tree[mapping[title]][7],0,176,len(items)*12,0x1170))
    for popup,(_,_,items) in zip(popups,groups):
        children=[]
        for name,label in items:
            parts=label.rsplit(' ',1)
            # CFLIB recognizes a shortcut only at the end (at most one trailing
            # blank). Keep its four-byte suffix intact for mutable Copy labels.
            caption='  '+(parts[0].rstrip().ljust(17)+parts[1] if len(parts)==2 and parts[1].startswith('^') else label.ljust(19))
            mapping[name]=len(tree);children.append(len(tree));tree.append(node(28,0,len(children)*12-12,176,12,caption))
        link(tree,popup,children)
    link(tree,0,[1,boxes]);link(tree,1,[2]);link(tree,2,list(range(3,3+len(groups))));link(tree,boxes,popups)
    tree[-1][4]|=32
    require(len(tree)<=33,'QED menu exceeds service capacity')
    return tree


def link(tree,parent,children):
    tree[parent][1:3]=[children[0],children[-1]]
    for i,child in enumerate(children):tree[child][0]=children[i+1] if i+1<len(children) else parent


def build(output,work=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if work is None:work=output/'inputs';prepare(work)
    payload,header,record=resource(work)
    (output/'QED.RSC').write_bytes(payload);(output/'qed.h').write_text(header,encoding='latin1')
    record.update(source_sha256=sha256(Path(work)/'source/qed/en/qed_en.rsc'),
        generator_sha256=sha256(Path(__file__)),
        desktop_geometry_sha256=sha256(ROOT/'abi/desktop.json'),
        selection_sha256=sha256(PORT/'resource-selection.json'),resource_sha256=sha256(output/'QED.RSC'),header_sha256=sha256(output/'qed.h'))
    (output/'resource.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work',type=Path);args=p.parse_args();print(build(args.output,args.work))
