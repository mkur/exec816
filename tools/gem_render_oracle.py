"""Independent pixel model and focused corpus; no target blitter algorithms."""
import re
from pathlib import Path

PENS=(0,15,1,2,4,6,3,5,7,8,9,10,12,14,11,13)
PALETTE=bytes.fromhex('ffffff 000000 ff0000 00ff00 0000ff 00ffff ffff00 ff00ff bbbbbb 777777 bb0000 00bb00 0000bb 00bbbb bbbb00 bb00bb')

class Raster:
    def __init__(self,font):
        self.font=font
        self.pixels=bytearray(640*240)
        self.clip=(0,0,639,239)
        self.line=self.text=self.fill=1

    def pixel(self,x,y,pen):
        a,b,c,d=self.clip
        if 0<=x<640 and 0<=y<240 and a<=x<=c and b<=y<=d:
            self.pixels[y*640+x]=PENS[pen]

    def apply(self,op,points=(),ints=()):
        if op==1: self.__init__(self.font)
        elif op==3: self.pixels[:]=bytes(len(self.pixels))
        elif op==129:
            self.clip=(min(points[0],points[2]),min(points[1],points[3]),max(points[0],points[2]),max(points[1],points[3])) if ints[0] else (0,0,639,239)
        elif op in (17,22,25): setattr(self,{17:'line',22:'text',25:'fill'}[op],ints[0])
        elif op==11:
            for y in range(max(0,min(points[1],points[3])),min(239,max(points[1],points[3]))+1):
                for x in range(max(0,min(points[0],points[2])),min(639,max(points[0],points[2]))+1): self.pixel(x,y,self.fill)
        elif op==8:
            for i,ch in enumerate(ints):
                for row in range(8):
                    for col in range(8):
                        self.pixel(points[0]+i*8+col,points[1]-6+row,self.text if self.font[row*256+ch]&(128>>col) else 0)
        elif op==6:
            # Closed-form nearest minor coordinate, ties toward the start.
            # This is independent of the target's incremental error accumulator.
            for n in range(0,len(points)-2,2):
                x,y,xx,yy=points[n:n+4]; dx,dy=abs(xx-x),abs(yy-y)
                sx,sy=(1 if xx>x else -1),(1 if yy>y else -1)
                major=max(dx,dy)
                for i in range(major+1):
                    minor=(2*i*min(dx,dy)+major-1)//(2*major) if major else 0
                    self.pixel(x+sx*(i if dx>=dy else minor),y+sy*(minor if dx>=dy else i),self.line)

    def packed(self):
        return bytes((a<<4)|b for a,b in zip(self.pixels[::2],self.pixels[1::2]))


def font_bytes(path):
    body=Path(path).read_text().split('{',1)[1]
    return bytes(int(x,16) for x in re.findall(r'0x([a-fA-F0-9]{2})',body))


def corpus():
    result=[]
    def add(name,op,p=(),v=(),**extra): result.append(dict(name=name,op=op,points=list(p),ints=list(v),**extra))
    add('open',1)
    for op in (17,22,23,25,32): add('attribute-'+str(op),op,v=[1])
    add('clear',3)
    for pen in range(16):
        add('pen-'+str(pen),25,v=[pen]);add('swatch-'+str(pen),11,[pen*40,0,pen*40+39,25])
    add('red-fill',25,v=[2]);add('reversed-corners',11,[98,61,33,30])
    add('clip-reversed',129,[91,57,41,35],[1]);add('clipped-bar',11,[-32768,-32768,32767,32767])
    add('clip-off',129,[0,0,0,0],[0])
    add('line-blue',17,v=[4])
    add('horizontal',6,[-32768,63,32767,63]);add('vertical',6,[29,-32768,29,32767])
    add('diagonals',6,[-20,60,660,135,0,135,639,60,0,95,639,95,0,60])
    add('extreme-diagonal',6,[-32768,-32768,32767,32767])
    add('extreme-reverse',6,[32767,-32768,-32768,32767])
    add('green-text',22,v=[3])
    for i in range(4): add('glyphs-'+str(i),8,[60+(i&1),150+i*9],list(range(i*64,(i+1)*64)))
    for name,point in [('left',[-3,189]),('right',[635,198]),('top',[301,3]),('bottom',[310,243])]: add('text-'+name,8,point,[65,66,67])
    add('empty-text',8,[40,200]);add('text-max-coordinates',8,[32767,32767],[65]*64)
    add('text-min-coordinates',8,[-32768,-32768],[65]*64)
    add('tiny-clip',129,[401,184,404,186],[1]);add('cut-glyph',8,[400,189],[65])
    add('empty-intersection',129,[-20,-20,-1,-1],[1]);add('invisible-bar',11,[0,0,639,239])
    add('invisible-text',8,[0,10],[65]*64);add('clip-off-again',129,[0,0,0,0],[0])
    add('window-crossing-bar',11,[507,216,530,222])
    add('title-black',22,v=[1]);add('title',8,[190,222],list(b'GEM / VDI on Exec816'))
    add('update',4,screenshot=True)
    add('end-of-bank-packet',11,[90,194,106,202],boundary=1)
    add('cross-bank-packet',11,[0,0,639,239],boundary=2,status=2)
    add('boundary-readback',4)
    add('bad-mode',32,v=[2],status=1);add('bad-pen',25,v=[16],status=1)
    add('bad-glyph',8,[0,6],[256],status=1);add('virtual-workstation',100,status=1)
    add('invalid-batch',11,[0,0,639,239],batch=1,status=1)
    add('after-rejections',4)
    add('fault',11,[5,5,15,15],fault=True,batch=2,status=6)
    add('invalidated',4,status=3)
    add('reopen',1)
    add('reset-line-attribute',6,[0,0,639,239])
    add('reset-text-attribute',8,[40,40],list(b'Clean reopen'))
    add('close',2)
    return result


def text_corpus():
    """All pens/parities and nibble cuts, plus the ordinary shared drawing API."""
    result=[dict(name='open',op=1,points=[],ints=[])]
    def add(name,op,p=(),v=(),**extra):
        result.append(dict(name=name,op=op,points=list(p),ints=list(v),**extra))
    for pen in range(16):
        add('text-pen-'+str(pen),22,v=[pen])
        for parity in (0,1):
            add(f'text-{pen}-{parity}',8,[32+parity,16+pen*9],list(b'AB W 09'))
    for cut in range(8):
        add('clip-'+str(cut),129,[401+cut,180,415-cut,187],[1])
        add('cut-'+str(cut),8,[400,186],list(b'WW'))
    add('clip-off',129,[0,0,0,0],[0])
    add('common-fill',4,common=1)
    add('common-text',4,common=2)
    add('common-invalid-empty-busy',4,common=3)
    add('preserved-vdi-attributes',8,[110,190],list(b'AB C'))
    add('empty-text',8,[0,0])
    add('update',4,screenshot=True)
    add('close',2)
    return result
