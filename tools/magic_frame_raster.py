"""Independent pixel oracle for the stored MagiC frame tree and flat palette."""
import json
import struct

from desktop_raster import rectangle, text
from gem_render_oracle import Raster
from generate_desktop import layout as desktop_layout
from generate_gem_objects import layout as gem_layout
from native_program import ROOT


def decode(window):
    raw=bytes.fromhex(window['raw']);frame=bytes.fromhex(window['frame'])
    wf=desktop_layout()['Window']['fields'];ff=gem_layout()['Frame']['fields']
    tree=[struct.unpack_from('<hhhHHHIhhhh',frame,ff['tree']+24*i) for i in range(16)]
    rect=lambda name:struct.unpack_from('<4h',frame,ff[name])
    return dict(tree=tree,current=rect('current'),work=rect('work'),overall=rect('overall'),
        title=raw[wf['title']:wf['title']+65].split(b'\0')[0],
        info=raw[wf['info']:wf['info']+65].split(b'\0')[0],
        id=int.from_bytes(raw[wf['id']:wf['id']+4],'little'),
        kind=int.from_bytes(raw[wf['frameKind']:wf['frameKind']+2],'little'))


def model(font,windows,focus):
    raster=Raster(font)
    assets=json.loads((ROOT/'lib/desktop/frame-gadgets.json').read_text())
    glyphs={1:'close',4:'full',6:'size',7:'up',8:'down',11:'left',12:'right',15:'iconify'}
    def box(bounds,thickness):
        l,t,r,b=bounds
        for inset in range(thickness):
            rectangle(raster,(l+inset,t+inset,r-inset,t+inset+1),1)
            rectangle(raster,(l+inset,b-inset-1,r-inset,b-inset),1)
            rectangle(raster,(l+inset,t+inset,l+inset+1,b-inset),1)
            rectangle(raster,(r-inset-1,t+inset,r-inset,b-inset),1)
    for index,window in enumerate(windows):
        w=decode(window);x,y,width,height=w['current'];right=x+width;bottom=y+height
        if w['kind']==4096:
            rectangle(raster,(x,y,right,bottom),3)
            continue
        left,top,ww,wh=w['work'];wr=left+ww;wb=top+wh
        rectangle(raster,(left,top,wr,wb),6)
        def visit(obj,px,py):
            nxt,head,tail,kind,flags,state,spec,rx,ry,ow,oh=w['tree'][obj]
            ox,oy=px+rx,py+ry
            if flags&128:return
            thickness=(spec>>16)&255
            if thickness>=128:thickness-=256
            if kind==22:thickness=1
            box((ox,oy,ox+ow,oy+oh),thickness)
            if kind!=25:
                # The admitted flat profile renders hollow interiors white.
                # Patterned scroll backgrounds use the existing transparent
                # WHITE disabled stipple over that neutral paper.
                rectangle(raster,(ox+thickness,oy+thickness,
                                  ox+ow-thickness,oy+oh-thickness),0)
            if kind==22:
                value=w['title'] if obj==2 else w['info']
                iw,ih=ow-2,oh-2
                value=value[:min(63,iw//8)] if ih>=8 else b''
                tx=ox+1+((iw-len(value)*8+1)//2 if obj==2 else 0)
                ty=oy+1+max(0,(ih-8+1)//2)
                text(raster,tx,ty,value,12 if obj==2 and w['id']==focus else 1)
            if obj in glyphs and (obj!=6 or spec>>24):
                rows=assets[glyphs[obj]];gw,gh=len(rows[0]),len(rows)
                gx,gy=ox+(ow-gw)//2,oy+(oh-gh)//2
                for row,pixels in enumerate(rows):
                    for col,pixel in enumerate(pixels):
                        raster.pixel(gx+col,gy+row,{'.':0,'#':1,'b':12}[pixel])
            if obj==0 and state&32:
                rectangle(raster,(right,y+2,right+2,bottom+2),1)
                rectangle(raster,(x+2,bottom,right,bottom+2),1)
            child=head
            while child!=-1 and child!=obj:
                visit(child,ox,oy)
                child=w['tree'][child][0]
        # Native full-frame painting partitions around client work. The oracle
        # draws the same objects clipped to those disjoint frame regions.
        for clip in ((x,y,right+2,top),(x,wb,right+2,bottom+2),
                     (x,top,left,wb),(wr,top,right+2,wb)):
            l,t,r,b=clip;raster.clip=(l,t,r-1,b-1)
            rectangle(raster,clip,0)
            visit(0,0,0)
        raster.clip=(0,0,639,239)
    return raster
