"""Expected pixels from the donor formulas and independent host AES/VDI."""
from gem_render_oracle import Raster, font_bytes, PALETTE, PENS
from control_panel_oracle import draw
from native_program import require


def check(bridge,output,font,row):
    r=Raster(font_bytes(font));cx,cy,cw,ch=80,56,480,160
    r.clip=(cx,cy,cx+cw-1,cy+ch-1)
    r.apply(25,ints=[0]);r.apply(11,(cx,cy,cx+cw-1,cy+ch-1))
    text=b'The quick brown fox jumps over the lazy'
    for i in range(20 if row==4 else 50):
        pen=1+i%15
        if row==0:
            x,y=cx+(i*7)%(cw-100),cy+(i*5)%(ch-50)
            r.apply(25,ints=[pen]);r.apply(11,(x,y,x+99,y+49))
        elif row<4:
            x,y=cx+2+(row==2),cy+8+8*(i%19)
            if row==3:r.clip=(cx+3,cy+3,cx+2+len(text)*8-2,cy+ch-1)
            r.apply(22,ints=[pen]);r.apply(8,(x,y),text)
        else:
            objects=[[-1,1,4,20,0,0,0x21100,(i*13)%(cw-176),(i*7)%(ch-64),176,64],
                     [2,-1,-1,28,0,0,1,16,8,96,8],
                     [3,-1,-1,20,0,0,0x11172,136,8,24,16],
                     [4,-1,-1,26,7,0,3,16,40,64,16],
                     [0,-1,-1,26,37,0,4,96,40,64,16]]
            draw(r,objects,{1:'A dialog box',3:'OK',4:'Cancel'},(cx,cy,cx+cw,cy+ch))
    path=output/f'pixels-{row}.bgra';frame=bridge.rawscreen(str(path));raw=path.read_bytes()
    bridge.screenshot(str(output/f'pixels-{row}.png'))
    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    for y in range(cy,cy+ch):
        for x in range(cx,cx+cw):
            offset=y*frame.stride+(x+16)*4
            require(raw[offset:offset+3]==colors[r.pixels[y*640+x]],
                    f'G4BENCH row {row} pixel differs at {x},{y}: '
                    f'{raw[offset:offset+3].hex()} != {colors[r.pixels[y*640+x]].hex()}')
