"""Deterministic sector patterns in ATR containers; no filesystem interpretation."""
import struct
from os_boundary import require

def disk_image(path,sector_size=128,sectors=720):
    require(sector_size in (128,256) and 3<=sectors<=65535,'Invalid sector fixture')
    header=bytearray(16)
    paragraphs=(384+(sectors-3)*sector_size)//16
    struct.pack_into('<HHHH',header,0,0x296,paragraphs&65535,sector_size,paragraphs>>16)
    body=bytes((i ^ (sector*15))&255 for sector in range(1,sectors+1)
               for i in range(128 if sector<=3 else sector_size))
    path.write_bytes(header+body)
    return body[384:384+sector_size]
