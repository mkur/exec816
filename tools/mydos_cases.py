"""Deterministic metadata perturbations; no host filesystem decisions."""
import struct
from mydos_fixtures import Image

# Each case runs the same guest parser and byte-provider contract.
PATHS=[
 (0,'',0,0),(0,'TOOLS/SUB/DATA.BIN',0,0),(0,'tools/sub/data.bin',0,0),
 (0,'CASE.TXT',0,5),(0,'case.txt',0,6),(0,'CaSe.TxT',210,0),
 (0,'A@_`.BIN',0,7),(0,'MISSING',205,0),(0,'TEXT.TXT/CHILD',212,0),
 (0,'/TOOLS',210,0),(0,'TOOLS/',210,0),(0,'TOOLS//SUB',210,0),
 (0,'D1:TOOLS',210,0),(0,'TOOLONG99',210,0),(0,'TEXT.LONG',210,0),
 (0,'TEXT.',210,0),(0,'A.B.C',210,0),(0,'A'*256,210,0),
 (10,'TOOLS',205,0),(11,'TEXT.TXT',205,0),(12,'TOOLS',213,0),
 (13,'TOOLS',210,0),(14,'TOOLS',213,0),(15,'TOOLS',213,0),
 (16,'TOOLS/SUB',213,0),(17,'TOOLS/SUB',213,0),
 (18,'TOOLS/SUB',0,0),(19,'F55.BIN',205,0),(20,'TRAP.BIN',205,0),
 (21,'TOOLS/'+('D/'*14)+'D',0,0),
 (21,'TOOLS/'+('D/'*15)+'D',217,0),
 (22,'TOOLS',213,0),(23,'TOOLS',213,0),
]
FORMATS=[(0,1),(1,0),(2,0),(3,0),(4,1),(5,0)]

def sector(image,phase,number):
    if phase==30:
        raw=bytearray(image.size)
        if number==360:
            raw[0]=35
            pages=8448//image.size
            raw[1:3]=(65535-11-pages).to_bytes(2,'little')
        if number==361:raw[:16]=bytes([16])+struct.pack('<HH',8,65520)+b'HIGH       '
        if number==65520:raw[:16]=bytes([0x46])+struct.pack('<HH',1,65535)+b'FILE    BIN'
        return bytes(raw)
    raw=bytearray(image.sector(number))
    if number==360:
        if phase==1:raw[0]=1
        if phase==2:raw[3:5]=b'\xff\xff'
        if phase==3:raw[1:3]=b'\xff\xff'
        if phase==4:
            raw[0]=3 if image.size==128 else 4
            raw[1:3]=(image.count-13).to_bytes(2,'little')
        if phase==5:raw[0]=255
    if number==361:
        if phase==10:raw[0]=0x80
        if phase==11:raw[32]=0x43
        if phase==12:raw[0]=0x40
        if phase==13:raw[5:8]=b'A B'
        if phase==14:raw[1:3]=(7).to_bytes(2,'little')
        if phase==15:raw[3:5]=(image.count-3).to_bytes(2,'little')
        if phase==21:raw[3:5]=(500).to_bytes(2,'little')
    if number==369 and phase in (16,17):raw[3:5]=(369 if phase==16 else 370).to_bytes(2,'little')
    if number==377 and phase==18:raw[:128]=bytes(128)
    if number==362 and phase==19:raw[32]=0
    if 361<=number<=368 and phase==20 and image.size==256:
        for i in range(128,256,16):raw[i:i+16]=bytes([0x42])+struct.pack('<HH',1,500)+b'TRAP    BIN'
    if phase==21 and 500<=number<=628:
        raw[:128]=bytes(128)
        if (number-500)%8==0:raw[:16]=bytes([16])+struct.pack('<HH',8,number+8)+b'D          '
    return bytes(raw)

def generated(size):
    # Preserve the basic fixture's three paths at their original offsets.
    last='F55.BIN' if size==128 else 'F53.BIN'
    blob=bytearray(b'\0TOOLS/SUB/DATA.BIN\0'.ljust(20,b'\0')+last.encode()+b'\0')
    lines=[];groups=[];cases=[]
    for index,(phase,path,error,ordinal) in enumerate(PATHS):
        offset=len(blob);blob+=path.encode()+b'\0'
        lines.append(f'  PathCase({phase},{offset},{error},{ordinal})')
        cases.append(dict(phase=phase,path=path,error=error,ordinal=ordinal))
    for n in range(0,len(lines),4):
        name=f'PathGroup{n//4}';groups.append(name)
    procedures=[]
    for i,name in enumerate(groups):procedures += [f'PROC {name}(BYTE unused)',*lines[4*i:4*i+4],'RETURN']
    for i,(phase,success) in enumerate(FORMATS):
        name=f'FormatGroup{i}';groups.append(name);procedures += [f'PROC {name}(BYTE unused)',f'  FormatCase({phase},{success})','RETURN']
    return '\n'.join(procedures)+'\n', ' '.join(f'{g}(0)' for g in groups), bytes(blob),cases
