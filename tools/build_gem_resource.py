#!/usr/bin/env python3
"""Build the desktop's classic big-endian RSC from reviewable JSON trees."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT


def resource(source=None):
    trees=json.loads((source or ROOT/'examples/gem-browser/resource.json').read_text())
    nodes=[o for tree in trees for o in tree]
    object_at=36;tree_at=36+24*len(nodes);strings_at=tree_at+4*len(trees)
    strings=bytearray();objects=bytearray();index=bytearray();position=object_at
    def coord(n):return ((n%8)<<8)|(n//8)
    for tree in trees:
        index.extend(struct.pack('>I',position));position+=24*len(tree)
        for o in tree:
            spec=o[6]
            if isinstance(spec,str):
                offset=strings_at+len(strings);strings.extend(spec.encode('ascii')+b'\0');spec=offset
            objects.extend(struct.pack('>hhhHHHIHHHH',*o[:6],spec,*(coord(n) for n in o[7:])))
    header=[0,object_at,0,0,0,0,strings_at,0,0,tree_at,len(nodes),len(trees),0,0,0,0,0,strings_at+len(strings)]
    return struct.pack('>18H',*header)+objects+index+strings

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_bytes(resource())
