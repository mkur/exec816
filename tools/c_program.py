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


def binding(image, output):
    """One fixed provider per desktop build; no runtime library discovery."""
    symbols=image['symbols']
    require(all(name in symbols for name in (*ABI['imports'],'ExecProgramRun')),
            'Incomplete C application provider')
    table=' '.join(f'${symbols[name]:x}' for name in ABI['imports'])
    source=f'''MODULE CPROGRAMBIND
USE AESBOOT
USE AESPROCESS
USE CALYPSICALL
USE EXEC

ADDRESS ARRAY entries=[{table}]
TYPE Invocation=[LONGCARD entry,service,stopFlags]

PUBLIC ADDRESS FUNC Import(CARD ordinal)

  IF ordinal>={len(ABI['imports'])} THEN
    RETURN(ADDRESS(0))
  FI

RETURN(entries(ordinal))

PUBLIC ADDRESS FUNC Runner()

  IF AESBOOT.Port()=NULL THEN
    RETURN(ADDRESS(0))
  FI

RETURN(ADDRESS(${symbols['ExecProgramRun']:x}))

PUBLIC LONGINT FUNC Run(ADDRESS entry BYTE POINTER stopFlags)
  Invocation invocation

  invocation.entry=LONGCARD(entry)
  invocation.service=LONGCARD(ADDRESS(AESBOOT.Port()))
  invocation.stopFlags=LONGCARD(ADDRESS(stopFlags))

RETURN(CALYPSICALL.Invoke(ADDRESS(${symbols['ExecProgramRun']:x}),
    LONGCARD(ADDRESS(@invocation))))

PUBLIC PROC Stop(EXEC.Task POINTER task)

  AESPROCESS.RequestClose(task)

RETURN

ENDMODULE
'''
    path=Path(output)/'cprogrambind.act';path.write_text(source)
    image['provenance']['c_program_provider']=dict(abi=ABI['version'],imports=ABI['imports'],
        runner=symbols['ExecProgramRun'])
    return path
