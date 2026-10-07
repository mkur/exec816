"""Public GEM application models rendered independently of target paint code."""
import struct
from native_program import require
from control_panel_oracle import draw
from test_desktop_presentation import rectangle


def paint(bridge,symbols,r,title,bounds):
    left,top,right,bottom=bounds
    if title==b'Counter':
        count=int.from_bytes(bridge.memdump(symbols['GEMCounter']+14,4),'little')
        r.clip=(left+8,top+16,right-9,bottom-9);r.text=4
        r.apply(8,(left+16,top+30),b'GEM counter')
        r.apply(8,(left+16,top+46),('Count: %06d'%count).encode())
        r.clip=(0,0,639,239);return
    require(title==b'GEM Control Panel','Unknown GEM desktop app: '+repr(title))
    base=symbols['GEMPanel'];raw=bridge.memdump(base+178,192)
    objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(8)]
    labels={}
    for i,obj in enumerate(objects):
        if obj[3] in (26,28,32):
            labels[i]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii');obj[6]=i
    objects[0][7]=objects[0][8]=0
    draw(r,objects,labels,(left+8,top+16,right-8,bottom-8))
    focus=int.from_bytes(bridge.memdump(base+392,2),'little');obj=objects[focus]
    rectangle(r,(left+8+obj[7]+3,top+16+obj[8]+13,left+8+obj[7]+77,top+16+obj[8]+14),1)
