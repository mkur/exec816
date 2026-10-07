"""Independent pixel/model oracle for the ordinary GEM input example."""
import struct
from test_desktop_presentation import frame,rectangle

APP_SIZE=212
FIELDS=dict(id=4,window=8,ready=12,activations=14,paints=18,work=38,
            key=46,clicks=56,down=70,armed=72,tick=74)


def address(symbols,instance,field):
    return symbols['GEMInputs']+APP_SIZE*instance+FIELDS[field]


def state(bridge,symbols,instance):
    raw=bridge.memdump(symbols['GEMInputs']+APP_SIZE*instance,APP_SIZE)
    word=lambda n:int.from_bytes(raw[FIELDS[n]:FIELDS[n]+2],'little')
    return dict(instance=instance,**{n:word(n) for n in ('id','window','ready','down','armed','tick')},
                work=list(struct.unpack('<4h',raw[38:46])),key=raw[46:55].decode(),
                clicks=raw[56:69].decode(),activations=int.from_bytes(raw[14:18],'little'),
                paints=int.from_bytes(raw[18:22],'little'))


def paint(r,s,active):
    if not s['ready']:return
    x,y,w,h=s['work'];ink=2 if s['instance'] else 4
    if active is not None:frame(r,(x-8,y-16,x+w+8,y+h+8),b'Input B' if s['instance'] else b'Input A',active,close=True)
    r.clip=(x,y,x+w-1,y+h-1);r.text=ink
    r.apply(8,(x+8,y+14),b'GEM input')
    r.apply(8,(x+8,y+30),s['key'].encode())
    r.apply(8,(x+8,y+46),s['clicks'].encode())
    rectangle(r,(x+8,y+48,x+136,y+72),ink)
    if not s['armed']:rectangle(r,(x+9,y+49,x+135,y+71),0)
    r.text=ink
    r.apply(8,(x+32,y+64),b'Activate')
    r.text=ink;r.apply(8,(x+8,y+88),b'Tick: *' if s['tick'] else b'Tick: .')
    r.clip=(0,0,639,239)
