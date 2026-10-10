"""Independent host fixtures for APT tables and the four documented packings."""
import struct
from pathlib import Path

def container_index(mode,logical,index,size):
    if size==512:
        if mode!=0:raise ValueError('512-byte sectors have no packing')
        return index
    # 128-byte sectors use every other byte of the same 256-byte container.
    byte=index*(2 if size==128 else 1)
    if mode==0:return byte*2
    if mode==1:return byte*2+(logical%2)
    if mode==2:return byte
    if mode==3:return byte+(logical%2)*256
    raise ValueError('Unsupported APT packing')

def put_sector(media,start,mode,size,logical,payload):
    physical=start+(logical//2 if mode in (1,3) else logical)
    if len(payload)>size:raise ValueError('Oversized logical sector')
    for index,value in enumerate(payload):media[physical*512+container_index(mode,logical,index,size)]=value

def get_sector(media,start,mode,size,logical,length=None):
    physical=start+(logical//2 if mode in (1,3) else logical)
    return bytes(media[physical*512+container_index(mode,logical,i,size)] for i in range(length or size))

def pattern_fixture(even=False,mbr=False,chained=False,readonly=True):
    media=bytearray([0x96])*(8192*512)
    # Boot unit D1 is deliberately empty. Test units D2..D9 cover all packings.
    entries=[bytes(16)]
    mappings=[]
    for size in (128,256):
        for mode in range(4):
            unit=len(entries)+1;start=64+unit*16;physical=2 if mode in (1,3) else 4
            entry=struct.pack('<BBIIHBBH',mode*4+(1 if size==128 else 2),0,start,physical+1,unit,0xc0 if readonly else 0x40,0,1)
            entries.append(entry);mappings.append(dict(unit=unit,start=start+1,mode=mode,size=size,sectors=4))
            for sector in range(4):
                payload=bytes((i^sector^unit)&255 for i in range(size))
                put_sector(media,start+1,mode,size,sector,payload)
    entries+= [bytes(16)]*(15-len(entries))
    base=32 if mbr else 0
    if mbr:
        media[:512]=bytes(512);media[446+4]=0x7f;struct.pack_into('<II',media,446+8,base,8192-base);media[510:512]=b'\x55\xaa'
    portions=[entries[:5],entries[5:]] if chained else [entries]
    for number,portion in enumerate(portions):
        sector=base+number;header=bytearray(16);header[0]=0x80 if even else 0;header[1:4]=b'APT';header[5]=len(portion)+1
        struct.pack_into('<II',header,8,sector+1 if number+1<len(portions) else 0,sector-1 if number else 0)
        table=header+b''.join(portion)
        media[sector*512:(sector+1)*512]=bytes(512)
        if even:
            if len(table)>256:raise ValueError('Even-byte APT table exceeds 16 entries')
            media[sector*512:sector*512+len(table)*2:2]=table
        else:media[sector*512:sector*512+len(table)]=table
    return media,mappings

def filesystem_fixture(atr,mode=3,unit=2,readonly=True):
    """Wrap an ATR as APT containers, preserving padding and metadata sentinels."""
    from sector_images import ATRImage as Image
    image=Image(atr)
    start=64
    physical=(image.count+1)//2 if mode in (1,3) else image.count
    capacity=max(8192,start+physical+2)
    media=bytearray([0x96])*(capacity*512)
    media[:512]=bytes(512);media[1:4]=b'APT';media[5]=16
    entry=struct.pack('<BBIIHBBH',0x40+mode*4+({128:1,256:2,512:3}[image.size]),0,start,physical+1,unit,0xc0 if readonly else 0x40,0,1)
    media[unit*16:unit*16+16]=entry
    for sector in range(1,image.count+1):put_sector(media,start+1,mode,image.size,sector-1,image.sector(sector))
    return media,dict(unit=unit,start=start+1,mode=mode,size=image.size,sectors=image.count)

def filesystem_atr(media,mapping,template):
    from sector_images import ATRImage as Image
    image=Image(template)
    for sector in range(1,image.count+1):
        value=get_sector(media,mapping['start'],mapping['mode'],mapping['size'],sector-1,len(image.sector(sector)))
        offset=image.offset(sector);image.data[offset:offset+len(value)]=value
    return bytes(image.data)
