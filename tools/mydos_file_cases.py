"""Known original-MyDOS contents and controlled chain mutations."""
import json
from native_program import ROOT


def generated(size):
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    volume=next(v for v in manifest['volumes'] if v['sector_bytes']==size)
    blob=bytearray(b'\0TOOLS/SUB/DATA.BIN\0');lines=[];cases=[]
    for path in ('EMPTY','TEXT.TXT','EXT.BIN','LOCKED.BIN','TOOLS/SUB/DATA.BIN')+ (('LARGE.BIN',) if size==256 else ()):
        entry=next(e for e in volume['files'] if e['path']==path)
        at=len(blob);blob+=path.encode()+b'\0'
        lines.append(f"  FileCase({at},{entry['bytes']},{entry['seed']}) FileSeeks({entry['bytes']},{entry['seed']})")
        cases.append(dict(path=path,size=entry['bytes'],seed=entry['seed']))
    extended=next(e for e in volume['files'] if e['path']=='EXT.BIN')
    ext=blob.index(b'EXT.BIN')
    for phase in (40,41,42,43,44,45,46,47,50,51,52):
        lines.append(f'  Corrupt({phase},{ext})')
        cases.append(dict(phase=phase,error=213,path='EXT.BIN'))
    lines.append('  AncestorLink(0)')
    lines.append(f'  EndFirst({ext},600)')
    lines.append(f'  CorruptSeek(51,{ext})')
    lines.append(f'  CorruptSeek(41,{ext})')
    lines.append(f'  TinyCycle(40,{ext})')
    lines.append(f'  TinyCycle(41,{ext})')
    lines.append(f'  EmptyForms({ext})')
    lines.append(f'  TenBit({ext})')
    lines.append(f'  ZeroPayload({ext},{600-(size-3)})')
    lines.append('  HighSectors(0)')
    lines.append('  OutputExtents(0) Guards(0)')
    procedures=[];calls=[]
    for n,line in enumerate(lines):
        procedures += [f'PROC FileGroup{n}(BYTE unused)',line,'RETURN'];calls.append(f'FileGroup{n}(0)')
    return '\n'.join(procedures)+'\n',' '.join(calls),bytes(blob),cases

# Replace sectors only. Guest code supplies the expected failure and limits.
def sector(image,phase,number):
    if phase==60:
        raw=bytearray(image.size)
        if number==360:
            raw[0]=35;raw[1:3]=(65535-11-8448//image.size).to_bytes(2,'little')
        elif number in (32768,65535):
            used=image.size-3 if number==32768 else 20
            origin=0 if number==32768 else image.size-3
            raw[:used]=bytes(((origin+i)&255)^91 for i in range(used))
            raw[-3:]=bytes([255,255,used]) if number==32768 else bytes([0,0,used])
        return bytes(raw)
    raw=bytearray(image.sector(number))
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    volume=next(v for v in manifest['volumes'] if v['sector_bytes']==image.size)
    entry=next(e for e in volume['files'] if e['path']=='EXT.BIN');a,b=entry['chain'][:2]
    if phase==54 and number==4:raw[-3:-1]=(369).to_bytes(2,'big')
    if number==a:
        if phase==40:raw[-3:-1]=a.to_bytes(2,'big')
        if phase==42:raw[-3]^=4
        if phase==43:raw[-1]=255
        if phase==44:raw[-3:-1]=bytes(2)
        if phase==45:raw[-3:-1]=(360).to_bytes(2,'big')
        if phase==46:raw[-3:-1]=(361).to_bytes(2,'big')
        if phase==47:raw[-3:-1]=(image.count+1).to_bytes(2,'big')
        if phase==48:raw[-1]=0 # zero payload on a nonterminal sector is legal
    if phase==49 and number in entry['chain']:
        raw[-3]=(raw[-3]&3)|(entry['ordinal']<<2)
    if number==b and phase==41:raw[-3:-1]=a.to_bytes(2,'big')
    return bytes(raw)

def fault_sector(image):
    manifest=json.loads((ROOT/'tests/fixtures/mydos/manifest.json').read_text())
    volume=next(v for v in manifest['volumes'] if v['sector_bytes']==image.size)
    return next(e for e in volume['files'] if e['path']=='EXT.BIN')['chain'][1]
