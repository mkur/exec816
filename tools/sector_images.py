"""Deterministic sector patterns in ATR containers; no filesystem interpretation."""
import struct
from os_boundary import require

class ATRImage:
    """Validated sector view; 512-byte ATRs contain no short boot sectors."""
    def __init__(self,data):
        self.data=bytearray(data)
        require(len(data)>=16 and data[:2]==b'\x96\x02','Not an ATR')
        self.size=int.from_bytes(data[4:6],'little')
        require(self.size in (128,256,512),'Unsupported sector size')
        length=16*(int.from_bytes(data[2:4],'little')+
                   (int.from_bytes(data[6:8],'little')<<16))
        require(len(data)-16==length,'ATR length mismatch')
        self.short=3 if self.size<512 else 0
        prefix=self.short*128
        require(length>=prefix and (length-prefix)%self.size==0,
                'Incomplete ATR sector')
        self.count=self.short+(length-prefix)//self.size

    def offset(self,sector):
        require(1<=sector<=self.count,'Out-of-range fixture sector')
        if sector<=self.short:return 16+(sector-1)*128
        return 16+self.short*128+(sector-self.short-1)*self.size

    def sector(self,sector):
        at=self.offset(sector)
        return bytes(self.data[at:at+(128 if sector<=self.short else self.size)])

def disk_image(path,sector_size=128,sectors=720):
    require(sector_size in (128,256) and 3<=sectors<=65535,'Invalid sector fixture')
    header=bytearray(16)
    paragraphs=(384+(sectors-3)*sector_size)//16
    struct.pack_into('<HHHH',header,0,0x296,paragraphs&65535,sector_size,paragraphs>>16)
    body=bytes((i ^ (sector*15))&255 for sector in range(1,sectors+1)
               for i in range(128 if sector<=3 else sector_size))
    path.write_bytes(header+body)
    return body[384:384+sector_size]
