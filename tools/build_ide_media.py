#!/usr/bin/env python3
"""Construct the IDE-only demo's two-partition APT, with independent audits."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from filesystem_audit import Audit
from ideplus_media import put_sector,filesystem_atr
from mydos_fixtures import Image

SECTORS=2880
SECTOR_BYTES=256
DISK_BYTES=4*1024*1024

def digest(data):return hashlib.sha256(data).hexdigest()

def build(system,work):
    inputs=[bytes(system),bytes(work)]
    media=bytearray(DISK_BYTES)
    media[0]=0x10;media[1:4]=b'APT';media[4]=1;media[5]=18
    mappings=[]
    for ordinal,(name,atr,start,readonly) in enumerate(zip(
            ('SYSTEM','WORK'),inputs,(64,1536),(True,False))):
        image=Image(atr)
        if (image.count,image.size)!=(SECTORS,SECTOR_BYTES):
            raise ValueError('IDE demo partitions require 2880 x 256 geometry')
        count=SECTORS//2
        # Fifteen mapping slots precede the actual partition entries. IDs count
        # actual partitions from one, excluding headers and mapping slots.
        entry=struct.pack('<BBIIHBBH',0x4e,0,start,count,ordinal+1,
                          0xc0 if readonly else 0x40,0,0)
        media[(ordinal+1)*16:(ordinal+2)*16]=entry
        actual=bytearray(entry);actual[10:12]=b'\0\0'
        media[(16+ordinal)*16:(17+ordinal)*16]=actual
        leader=(start-1)*512
        media[leader:leader+8]=b'APT\0META'
        media[leader+16:leader+16+len(name)]=name.encode('ascii')
        for sector in range(1,SECTORS+1):
            put_sector(media,start,3,256,sector-1,image.sector(sector))
        mappings.append(dict(name=name,unit=ordinal+1,id=ordinal+1,start=start,
                             leader=start-1,physical=count,mode=3,size=256,
                             sectors=SECTORS,readonly=readonly))
    reports=[]
    for mapping,atr in zip(mappings,inputs):
        reconstructed=filesystem_atr(media,mapping,atr)
        if reconstructed!=atr:raise ValueError('APT packing changed filesystem bytes')
        audit=Audit(reconstructed);report=audit.sdfs()
        reports.append(dict(**mapping,sha256=digest(atr),audit=report))
    return bytes(media),dict(format='exec816-ide-only-apt-v1',bytes=DISK_BYTES,
                             boot_unit=1,partitions=reports,image_sha256=digest(media))

def write(path,system,work):
    raw,record=build(Path(system).read_bytes(),Path(work).read_bytes())
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    path.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);v=p.parse_args()
    write(v.output,v.system,v.work)
