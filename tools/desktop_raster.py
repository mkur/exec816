"""Independent GEM frame, title, desktop and menu raster helpers."""
from gem_render_oracle import PENS

def rectangle(raster, bounds, pen):
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        for x in range(left, right):
            raster.pixel(x, y, pen)


def text(raster, x, y, value, fg=1, bg=0):
    for index, char in enumerate(value):
        for row in range(8):
            for col in range(8):
                raster.pixel(x + index*8 + col, y + row,
                             fg if raster.font[row*256+char] & (128 >> col) else bg)


def desktop(raster):
    # The desktop is a flat neutral field; titles retain their own pattern.
    for y in range(240):
        for x in range(640):
            raster.pixels[y*640+x]=PENS[8]


def frame(raster, bounds, title, focused, background=0, close=False, kind=0, slider=(0,0), info=b''):
    x, y, right, bottom = bounds
    rectangle(raster, bounds, 0)
    def box(l,t,r,b):
        rectangle(raster,(l,t,r,t+1),1)
        rectangle(raster,(l,b-1,r,b),1)
        rectangle(raster,(l,t+1,l+1,b-1),1)
        rectangle(raster,(r-1,t+1,r,b-1),1)
    def mark(l,t,full):
        widths=(4,3,1,0,1,3,4) if full else (0,1,3,4,3,1,0)
        for row,offset in enumerate(widths):
            rectangle(raster,(l+offset,t+row,l+offset+2,t+row+1),1)
            rectangle(raster,(l+8-offset,t+row,l+10-offset,t+row+1),1)
    box(x,y,right,bottom)
    rectangle(raster,(x+1,y+10,right-1,y+11),12 if focused else 1)
    name_left=x+(16 if close else 1)
    icon_right=right-(16 if kind&4 else 0)
    has_icon=icon_right-name_left>=28
    name_right=icon_right-(16 if has_icon else 1)
    title=title[:max(0,min(64,(name_right-name_left-4)//8))]
    tx=name_left+(name_right-name_left-len(title)*8)//2
    if focused:
        for py in range(y+1,y+10):
            for px in range(name_left,name_right):
                if (px-x)&1 and (py-y)&1: raster.pixel(px,py,1)
    if title:
        rectangle(raster,(tx-2,y+1,tx+len(title)*8+2,y+10),0)
        text(raster,tx,y+2,title,fg=12 if focused else 1)
    if close:
        if name_left<icon_right:
            rectangle(raster,(x+15,y+1,x+16,y+10),1)
        mark(x+3,y+2,False)
    if has_icon:
        rectangle(raster,(icon_right-16,y+1,icon_right-15,y+10),1)
        box(icon_right-13,y+2,icon_right-3,y+9)
        rectangle(raster,(icon_right-7,y+6,icon_right-4,y+8),1)
    if kind&4:
        rectangle(raster,(right-16,y+1,right-15,y+10),1)
        mark(right-13,y+2,True)
    wt=21 if kind&16 else 11
    if kind&16:
        rectangle(raster,(x,y+20,right,y+21),1)
        text(raster,x+8,y+12,info[:min(64,(right-x-16)//8)])
    wr=16 if kind&448 else 8
    wb=11 if kind&32 else 2
    rectangle(raster,(x+8,y+wt,right-wr,bottom-wb),background)
    if kind&448:
        l,t,b=right-16,y+wt,bottom-wb
        rectangle(raster,(l+1,t,right-1,b),8)
        rectangle(raster,(l,t,l+1,b),1)
        if kind&64:
            rectangle(raster,(l+1,t,right-1,t+11),0)
            for dy in range(5):rectangle(raster,(l+7-dy,t+3+dy,l+9+dy,t+4+dy),1)
            t+=11
        if kind&128:
            rectangle(raster,(l+1,b-11,right-1,b),0)
            for dy in range(5):rectangle(raster,(l+7-dy,b-4-dy,l+9+dy,b-3-dy),1)
            b-=11
        box(l,t,right,b)
        if kind&256:
            t=y+slider[0];b=t+slider[1]
            rectangle(raster,(l+1,t,right-1,b),0);box(l,t,right,b)
    if kind&32:
        box(right-16,bottom-11,right,bottom)
        for distance in (2,4,6):
            for step in range(distance):
                rectangle(raster,(right-4-2*step,bottom-2-distance+step,
                    right-2-2*step,bottom-1-distance+step),1)


def tile(raster, bounds, title):
    x,y,right,bottom=bounds
    rectangle(raster,bounds,0)
    for l,t,r,b in [(x,y,right,y+1),(x,bottom-1,right,bottom),
                    (x,y+1,x+1,bottom-1),(right-1,y+1,right,bottom-1),
                    (x+3,y+2,x+17,y+3),(x+3,y+8,x+17,y+9),
                    (x+3,y+3,x+4,y+8),(x+16,y+3,x+17,y+8)]:
        rectangle(raster,(l,t,r,b),1)
    rectangle(raster,(x+4,y+3,x+16,y+4),12)
    text(raster,x+20,y+2,title[:8])


def menu_bar(raster, title=b'Shell'):
    rectangle(raster,(0,0,640,11),0)
    text(raster,8,1,title[:14])
    text(raster,568,1,b'Windows')
    rectangle(raster,(0,10,640,11),1)


