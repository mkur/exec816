"""Viewer pixels from raw document bytes, independently of its line index."""
import re
from text_model import FIELDS as F
from generate_aes_server import expected_layout
from file_selector_model import FORM_SELECTOR
from test_desktop_presentation import rectangle

def paint(b,sy,r,bounds):
    number=lambda at,size=2:int.from_bytes(b.memdump(at,size),'little')
    context=sy['__aes_context'];session=number(context+dict(expected_layout())['C context form'],4)
    if session and number(session+FORM_SELECTOR,4):
        from file_selector_oracle import paint as selector
        selector(b,context,r);return
    a=sy['GEMText'];doc=a+F['document'];data=number(doc,4);size=number(doc+8,4)
    payload=b.memdump(data,size) if size else b''
    lines=re.split(b'\r\n|[\r\n\x9b]',payload) if payload else []
    if payload.endswith((b'\r',b'\n',b'\x9b')):lines.pop()
    x,y,endx,endy=bounds[0]+8,bounds[1]+16,bounds[2]-16,bounds[3]-16
    rows=(endy-y-20)//8;columns=(endx-x-8)//8;first=number(a+F['first'])
    rectangle(r,(x,y,endx,endy),0);r.clip=(x,y,endx-1,endy-1);r.text=1
    for row in range(rows):
        raw=lines[first+row] if first+row<len(lines) else b''
        text=bytearray()
        for ch in raw:
            if ch==9:text.extend(b' '*(8-len(text)%8))
            else:text.append(ch if 32<=ch<=126 else 46)
            if len(text)>=columns:break
        r.apply(8,(x+4,y+4+row*8+6),bytes(text[:columns]).ljust(columns,b' '))
    status=b.memdump(a+F['status'],81).split(b'\0')[0]
    r.apply(8,(x+4,endy-12+6),status[:columns].ljust(columns,b' '))
    r.clip=(0,0,639,239)
