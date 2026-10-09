"""Independent donor OBJECT/TED rasterization with Exec's editor viewport."""
import struct,sys
from native_program import ROOT
from generate_aes_server import expected_layout
from gem_render_oracle import PENS

def paint(b,context,r):
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    number=lambda at,size=2:int.from_bytes(b.memdump(at,size),'little')
    layout=dict(expected_layout());session=number(context+layout['C context form'],4)
    tree=number(session,4);focus=number(session+209);objects=[];memory={};caret=None
    for i in range(32):
        o=list(struct.unpack('<hhhHHHIhhhh',b.memdump(tree+i*24,24)))
        if o[3] in (26,28):
            memory[i+1]=a.Text(b.memdump(o[6],128).split(b'\0')[0].decode('ascii'));o[6]=i+1
        elif o[3]==22:
            t=struct.unpack('<III8h',b.memdump(o[6],28));text=b.memdump(t[0],t[-2]).split(b'\0')[0].decode('ascii')
            start=0
            if o[4]&8:
                active=number(context+layout['C context editTree'],4)==tree and number(context+layout['C context editObject'])==i
                if active:
                    start=number(context+layout['C context editScroll'])
                    caret=(i,number(context+layout['C context editIndex'])-start)
                text=text[start:start+min(63,o[9]//8)]
            base=1000+i*4
            memory[base]=a.Text(text);memory[base+1]=a.Text('');memory[base+2]=a.Text('X')
            memory[i+1]=a.Ted(base,base+1,base+2,font=t[3],just=t[5],color=t[6],thickness=t[8],txtlen=t[9],tmplen=t[10]);o[6]=i+1
        objects.append(a.Obj(*o))
        if o[4]&32:break
    root=objects[0];device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
    device.dev.s.mem[:76800]=r.packed()
    aes=a.AES(device,objects,memory);aes.gsx_start()
    aes.gsx_sclip(a.Rect(root.ob_x,root.ob_y,root.ob_width,root.ob_height));aes.ob_draw(0,7)
    if focus!=65535 and not objects[focus].ob_flags&8:
        o=objects[focus]
        for xx in range(root.ob_x+o.ob_x+3,root.ob_x+o.ob_x+o.ob_width-3):
            device.dev.plot_xor(xx,root.ob_y+o.ob_y+o.ob_height-3)
    if caret:
        i,index=caret;o=objects[i];x=root.ob_x+o.ob_x+index*8;y=root.ob_y+o.ob_y+(o.ob_height-8)//2
        for yy in range(y,y+8):device.dev.plot(x,yy,1)
    r.pixels[:]=bytes(n for byte in device.dev.s.mem[:76800] for n in (byte>>4,byte&15))
    return root.ob_x,root.ob_y,root.ob_width,root.ob_height
