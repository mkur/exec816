#!/usr/bin/env python3
"""Build the desktop's classic big-endian RSC from reviewable JSON trees."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT


def resource(source=None):
    trees=json.loads((source or ROOT/'examples/gem-browser/resource.json').read_text())
    nodes=[o for tree in trees for o in tree]
    icons=[o[6] for o in nodes if isinstance(o[6],dict)]
    object_at=36;icon_at=object_at+24*len(nodes)
    tree_at=icon_at+34*len(icons);bits_at=tree_at+4*len(trees)
    bits=bytearray();icon_offsets=[]
    for icon in icons:
        width,height=icon['width'],icon['height']
        if width not in (16,32,48,64) or not 1<=height<=64:
            raise ValueError('ICONBLK dimensions outside the supported subset')
        offsets=[]
        for name in ('mask','data'):
            values=[int(v,0) if isinstance(v,str) else v for v in icon[name]]
            if len(values)!=width//16*height:raise ValueError('Wrong icon plane length')
            offsets.append(bits_at+len(bits))
            bits.extend(struct.pack('>'+str(len(values))+'H',*values))
        icon_offsets.append(offsets)
    strings_at=bits_at+len(bits)
    strings=bytearray();objects=bytearray();index=bytearray();records=bytearray();position=object_at
    def string(text):
        offset=strings_at+len(strings);strings.extend(text.encode('ascii')+b'\0');return offset
    def coord(n):return ((n%8)<<8)|(n//8)
    number=0
    for tree in trees:
        index.extend(struct.pack('>I',position));position+=24*len(tree)
        for o in tree:
            spec=o[6]
            if isinstance(spec,str):spec=string(spec)
            elif isinstance(spec,dict):
                icon=spec;mask,data=icon_offsets[number]
                records.extend(struct.pack('>IIIH10h',mask,data,string(icon.get('label','')),
                    (icon.get('fg',1)<<12)|(icon.get('bg',0)<<8)|icon.get('char',0),
                    icon.get('char_x',0),icon.get('char_y',0),icon.get('x',0),icon.get('y',0),
                    icon['width'],icon['height'],icon.get('text_x',0),icon.get('text_y',icon['height']+2),
                    icon.get('text_width',o[9]),icon.get('text_height',8)))
                spec=icon_at+number*34;number+=1
            objects.extend(struct.pack('>hhhHHHIHHHH',*o[:6],spec,*(coord(n) for n in o[7:])))
    header=[0,object_at,0,icon_at if icons else 0,0,0,strings_at,0,0,tree_at,
            len(nodes),len(trees),0,len(icons),0,0,0,strings_at+len(strings)]
    return struct.pack('>18H',*header)+objects+records+index+bits+strings

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_bytes(resource())
