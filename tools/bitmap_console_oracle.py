"""Retained ASCII terminal and fixed-font pixels, independent of target copies."""
from gem_render_oracle import Raster

class Terminal:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.cells=bytearray(b' '*(width*height));self.row=self.column=0
    def newline(self):
        self.column=0
        if self.row+1<self.height:self.row+=1
        else:
            self.cells[:]=self.cells[self.width:]+b' '*self.width
    def feed(self,values):
        for value in values:
            if value==12:self.cells[:]=b' '*len(self.cells);self.row=self.column=0
            elif value==13:self.column=0
            elif value==10:self.newline()
            elif value==8:self.column=max(0,self.column-1)
            elif value==9:
                self.column=(self.column//8+1)*8
                if self.column>=self.width:self.newline()
            elif value>=32 and value!=127:
                self.cells[self.row*self.width+self.column]=value if value<128 else 63
                self.column+=1
                if self.column==self.width:self.newline()
    def paint(self,raster,left,top,caret=False):
        for index,ch in enumerate(self.cells):
            row,column=divmod(index,self.width)
            for y in range(8):
                for x in range(8):
                    raster.pixel((left+column)*8+x,(top+row)*8+y,
                                 1 if raster.font[y*256+ch]&(128>>x) else 0)
        if caret:
            for x in range(8):raster.pixel((left+self.column)*8+x,(top+self.row)*8+7,1)

def pattern(width,rows,seed):
    return b''.join(bytes(33+(seed+row*7+column)%90 for column in range(width-(row==rows-1))) for row in range(rows))

def scroll_scenes(font):
    base=Terminal(80,30);a=Terminal(17,3);b=Terminal(1,1);scenes=[]
    def snapshot(tiles):
        raster=Raster(font)
        for terminal,x,y,focus in tiles:terminal.paint(raster,x,y,focus)
        scenes.append(raster.packed())
    default=[(base,0,0,True)]
    base.feed(pattern(80,30,0));snapshot(default)
    base.feed(b'Z');snapshot(default)
    base.feed(b'Hi\n');snapshot(default)
    base.feed(pattern(80,4,31));snapshot(default)
    base.feed(b'\x0c');snapshot(default)
    tiles=[(a,5,7,True),(b,30,12,False)]
    a.feed(pattern(17,3,8));snapshot(tiles)
    a.feed(b'W');snapshot(tiles)
    tiles=[(a,5,7,False),(b,30,12,True)]
    b.feed(b'X');snapshot(tiles)
    a.feed(pattern(17,5,47));snapshot([(b,30,12,True)])
    tiles=[(a,5,7,True),(b,30,12,False)];snapshot(tiles)
    a.feed(b'\rA\bB');snapshot(tiles)
    a.feed(b'\x0c');snapshot(tiles)
    base.feed(pattern(80,30,0));snapshot(default)
    return scenes


def batch_scenes(font,accepted=None):
    terminal=Terminal(80,30);scenes=[]
    def snapshot():
        raster=Raster(font);terminal.paint(raster,0,0,True)
        scenes.append(raster.packed())
    terminal.feed(bytes(33+(row*7+col)%90 for row in range(29) for col in range(80)))
    snapshot()
    terminal.feed(b'one\ntwo\nthree\nfour\n'+b'X'*64);snapshot()
    bulk=bytes(10 if i%31==30 else 65+i%26 for i in range(512))
    terminal.feed(bulk*4);snapshot()
    controls=bytearray(65+i%26 for i in range(100))
    for index,value in ((27,13),(55,8),(72,9),(90,10)):controls[index]=value
    terminal.feed(controls);snapshot()
    terminal.feed(bulk);snapshot()
    if accepted is not None:
        terminal.feed(bulk[:accepted]);snapshot()
    return scenes
