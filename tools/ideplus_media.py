"""Independent APT fixtures with native 512-byte partition sectors."""
import struct
from pathlib import Path

def put_sector(media,start,logical,payload):
    if len(payload)!=512:raise ValueError('Expected one complete 512-byte sector')
    at=(start+logical)*512
    if at<0 or at+512>len(media):raise ValueError('Out-of-range physical sector')
    media[at:at+512]=payload

def get_sector(media,start,logical):
    at=(start+logical)*512
    if at<0 or at+512>len(media):raise ValueError('Out-of-range physical sector')
    return bytes(media[at:at+512])

def pattern_fixture(even=False,mbr=False,chained=False,readonly=True):
    media=bytearray([0x96])*(8192*512)
    # Boot unit D1 is empty. D2..D9 exercise independent native sector mappings.
    entries=[bytes(16)]
    mappings=[]
    for unit in range(2,10):
        start=64+unit*16
        entry=struct.pack('<BBIIHBBH',3,0,start,5,unit,
                          0xc0 if readonly else 0x40,0,1)
        entries.append(entry)
        mappings.append(dict(unit=unit,start=start+1,size=512,sectors=4))
        for sector in range(4):
            payload=bytes((i^(i>>8)^sector^unit)&255 for i in range(512))
            put_sector(media,start+1,sector,payload)
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

def filesystem_fixture(atr,unit=2,readonly=True):
    """Wrap uniform SDFS sectors, preserving leader and reserved sentinels."""
    from sector_images import ATRImage as Image
    image=Image(atr)
    if image.size!=512:raise ValueError('IDE requires uniform 512-byte sectors')
    start=64
    capacity=max(8192,start+image.count+2)
    media=bytearray([0x96])*(capacity*512)
    media[:512]=bytes(512);media[1:4]=b'APT';media[5]=16
    entry=struct.pack('<BBIIHBBH',0x43,0,start,image.count+1,unit,
                      0xc0 if readonly else 0x40,0,1)
    media[unit*16:unit*16+16]=entry
    for sector in range(1,image.count+1):
        put_sector(media,start+1,sector-1,image.sector(sector))
    return media,dict(unit=unit,start=start+1,size=512,sectors=image.count)

def filesystem_atr(media,mapping,template):
    from sector_images import ATRImage as Image
    image=Image(template)
    if image.size!=512:raise ValueError('IDE requires uniform 512-byte sectors')
    for sector in range(1,image.count+1):
        value=get_sector(media,mapping['start'],sector-1)
        offset=image.offset(sector);image.data[offset:offset+len(value)]=value
    return bytes(image.data)

def sdfs_image(source,destination,sectors=2000):
    """Reformat independently and import files; relabelling sectors is invalid."""
    import tempfile
    from sdfs_reference import extract
    from make_data_disk import make
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp)/'source'
        extract(source,folder)
        binary=[p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()]
        make(destination,folder,binary_names=binary,sector_bytes=512,sectors=sectors)
    return Path(destination).read_bytes()
