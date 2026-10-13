#!/usr/bin/env python3
"""Build the desktop's classic big-endian RSC from reviewable JSON trees."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT

# GEM logical pens to the ST/VBXE hardware colour bits stored in RSC planes.
PENS=(0,15,1,2,4,6,3,5,7,8,9,10,12,14,11,13)

def colour_form(rows,width,height):
    if len(rows)!=height or any(len(row)!=width for row in rows):
        raise ValueError('Wrong colour icon dimensions')
    pixels=[None if ch=='.' else PENS[int(ch,16)] for row in rows for ch in row]
    def plane(test):
        return bytes(sum(128>>bit for bit,v in enumerate(pixels[i:i+8]) if test(v))
                     for i in range(0,len(pixels),8))
    mask=plane(lambda v:v is not None)
    bits=b''.join(plane(lambda v,bit=bit:v is not None and v&(1<<bit)) for bit in range(4))
    mono=plane(lambda v:v is not None and v!=0)
    return bits,mask,mono

def colour_icon(icon):
    width,height=icon['width'],icon['height']
    if width not in (16,32,48,64) or not 1<=height<=64:
        raise ValueError('CICONBLK dimensions outside the supported subset')
    bits,mask,mono=colour_form(icon['pixels'],width,height)
    selected=colour_form(icon['selected_pixels'],width,height) if 'selected_pixels' in icon else None
    label=icon.get('label','').encode('ascii')
    if len(label)>12:raise ValueError('Colour icon label exceeds twelve bytes')
    header=struct.pack('>IIIH10hI',0,0,0,
        (icon.get('fg',1)<<12)|(icon.get('bg',0)<<8)|icon.get('char',0),
        icon.get('char_x',0),icon.get('char_y',0),icon.get('x',0),icon.get('y',0),
        width,height,icon.get('text_x',0),icon.get('text_y',height+2),
        icon.get('text_width',96),icon.get('text_height',8),1)
    return (header+mono+mask+label.ljust(12,b'\0')+
        struct.pack('>hIIIII',4,0,0,int(selected is not None),0,0)+bits+mask+
        (selected[0]+selected[1] if selected else b''))


def resource(source=None):
    trees=json.loads((source or ROOT/'examples/gem-browser/resource.json').read_text())
    nodes=[o for tree in trees for o in tree]
    icons=[o[6] for o in nodes if o[3]==31]
    colours=[o[6] for o in nodes if o[3]==33]
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
    number=colourNumber=0
    for tree in trees:
        index.extend(struct.pack('>I',position));position+=24*len(tree)
        for o in tree:
            spec=o[6]
            if isinstance(spec,str):spec=string(spec)
            elif o[3]==33:
                spec=colourNumber;colourNumber+=1
            elif isinstance(spec,dict):
                icon=spec;mask,data=icon_offsets[number]
                records.extend(struct.pack('>IIIH10h',mask,data,string(icon.get('label','')),
                    (icon.get('fg',1)<<12)|(icon.get('bg',0)<<8)|icon.get('char',0),
                    icon.get('char_x',0),icon.get('char_y',0),icon.get('x',0),icon.get('y',0),
                    icon['width'],icon['height'],icon.get('text_x',0),icon.get('text_y',icon['height']+2),
                    icon.get('text_width',o[9]),icon.get('text_height',8)))
                spec=icon_at+number*34;number+=1
            objects.extend(struct.pack('>hhhHHHIHHHH',*o[:6],spec,*(coord(n) for n in o[7:])))
    if colours and (strings_at+len(strings))&1:strings.append(0)
    classic=strings_at+len(strings)
    extension=b''
    if colours:
        extension=bytes(len(colours)*4)+b'\xff'*4+b''.join(colour_icon(i) for i in colours)
        extension=struct.pack('>III',classic+12+len(extension),classic+12,0)+extension
    header=[4 if colours else 0,object_at,0,icon_at if icons else 0,0,0,strings_at,0,0,tree_at,
            len(nodes),len(trees),0,len(icons),0,0,0,classic]
    if classic+len(extension)>65535:raise ValueError('Resource exceeds 65535 bytes')
    return struct.pack('>18H',*header)+objects+records+index+bits+strings+extension

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_bytes(resource())
