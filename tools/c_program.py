"""Bounded Calypsi application image and whole-bank relocation proof."""
import json
import struct
from pathlib import Path

from native_program import ROOT, require

ABI = json.loads((ROOT/'abi/c-program.json').read_text())
BASE = ABI['link_bank'] << 16


def shape(image, bank):
    base=bank << 16
    segments=[dict(offset=s['address']-base,payload=bytes(s['bytes']),size=len(s['bytes']),
                   flags=int(s['executable']) | (int(s['writable']) << 1)) for s in image['segments']]
    segments += [dict(offset=s['address']-base,payload=b'',size=s['size'],flags=2)
                 for s in image['zero_fill']]
    return sorted(segments,key=lambda s:s['offset'])


def fixups(original, shifted):
    before,after=shape(original,ABI['link_bank']),shape(shifted,ABI['link_bank']+1)
    require(len(before)==len(after),'Relinking changed C segments')
    result=[]
    for a,b in zip(before,after):
        require(all(a[k]==b[k] for k in ('offset','size','flags')) and len(a['payload'])==len(b['payload']),
                'Relinking changed C placement')
        for offset,(x,y) in enumerate(zip(a['payload'],b['payload'])):
            if x!=y:
                require(y==x+1,'Unsupported address arithmetic in C image')
                result.append(a['offset']+offset)
    return result


def verify(original, linked, bank, relocations):
    before,after=shape(original,ABI['link_bank']),shape(linked,bank)
    require(len(before)==len(after),'Relinking changed C segments')
    changes=set(relocations)
    for a,b in zip(before,after):
        require(all(a[k]==b[k] for k in ('offset','size','flags')),'Relinking changed C placement')
        predicted=bytes(v+bank-ABI['link_bank'] if a['offset']+i in changes else v
                        for i,v in enumerate(a['payload']))
        require(predicted==b['payload'],'Bank relocation does not reproduce independently linked C bytes')
    require(original['symbols']['main']-BASE==linked['symbols']['main']-(bank<<16),
            'Relinking changed the entry')
    for name,address in original['symbols'].items():
        if any(s['offset']<=address-BASE<=s['offset']+s['size'] for s in before):
            require(linked['symbols'].get(name)==address+(bank-ABI['link_bank'])*65536,
                    'Relinking changed C symbol placement: '+name)


def pack(image, relocations):
    segments=shape(image,ABI['link_bank'])
    require(0<len(segments)<=ABI['segment_limit'],'Too many C application segments')
    span=max(s['offset']+s['size'] for s in segments)
    require(0<span<=ABI['span_limit'],'C application exceeds supported banks')
    require(all(s['offset']>=0 and s['size']>0 for s in segments),'Invalid C application segment')
    imports=[]
    for ordinal,name in enumerate(ABI['imports']):
        if name not in image['symbols']:continue
        at=image['symbols'][name]-BASE
        candidate=[s for s in segments if s['flags']==1 and s['offset']<=at<at+4<=s['offset']+len(s['payload'])]
        require(len(candidate)==1 and candidate[0]['payload'][at-candidate[0]['offset']]==0x5c,
                'C import is not a long tail-jump thunk: '+name)
        imports.append((ordinal,at+1))
    body=b''.join(struct.pack('<IIII',s['offset'],len(s['payload']),s['size'],s['flags']) for s in segments)
    body+=b''.join(struct.pack('<HHI',ordinal,0,at) for ordinal,at in imports)
    body+=b''.join(struct.pack('<I',at) for at in relocations)
    body+=b''.join(s['payload'] for s in segments)
    header=struct.pack('<4sHHBBHIIIHHI',ABI['magic'].encode(),1,ABI['version'],ABI['link_bank'],
        ABI['max_banks'],len(segments),span,image['symbols']['main']-BASE,len(relocations),
        len(imports),image['provenance']['dp_workspace_bytes'],ABI['header_bytes']+len(body))
    require(len(header)+len(body)<=ABI['file_limit'],'C application file too large')
    return header+body,dict(span=span,entry=image['symbols']['main']-BASE,relocations=relocations,
                            imports=imports,segments=[{k:v for k,v in s.items() if k!='payload'} for s in segments])


def import_assembly():
    lines=['; Generated from abi/c-program.json. Bound once by PROGRAM.Load.',
           '              .section farcode,text']
    for name in ABI['imports']:
        lines += ['              .public '+name,name+':','              jmp long:0x123456']
    lines += ['              .rtmodel version,"1"','              .rtmodel codeModel,"large"',
              '              .rtmodel dataModel,"huge"','              .rtmodel core,"65816"','']
    return '\n'.join(lines)
