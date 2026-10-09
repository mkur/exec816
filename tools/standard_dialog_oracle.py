"""Independent pixels for the packaged standard-dialog example."""
import ast,struct
from native_program import ROOT
from generate_aes_server import expected_layout
from control_panel_oracle import draw
from file_selector_model import FORM_SELECTOR
from test_desktop_presentation import rectangle
from gem_render_oracle import PENS


def paint(b,sy,r,bounds):
    number=lambda at,size=2:int.from_bytes(b.memdump(at,size),'little')
    c=sy['__aes_context'];layout=dict(expected_layout())
    session=number(c+layout['C context form'],4)
    if session and number(session+FORM_SELECTOR,4):
        from file_selector_oracle import paint as selector
        selector(b,c,r)
        return
    tree=number(session,4) if session else sy['GEMDialog']+184
    objects=[]
    for i in range(32):
        objects.append(list(struct.unpack('<hhhHHHIhhhh',b.memdump(tree+24*i,24))))
        if objects[-1][4]&32:break
    labels={};fields=[]
    for i,o in enumerate(objects):
        if o[3] in (26,28):labels[i]=b.memdump(o[6],128).split(b'\0')[0].decode('ascii');o[6]=i
        elif o[3]==22:
            fields.append((i,o[:],struct.unpack('<III8h',b.memdump(o[6],28))))
            o[3]=25;o[6]=0
    x,y,w,h=objects[0][7:11];objects[0][7]=objects[0][8]=0
    if session:rectangle(r,(bounds[0]+8,bounds[1]+16,bounds[2]-8,bounds[3]-8),0)
    focus=number(session+209) if session and not fields else -1
    draw(r,objects,labels,(x,y,x+w,y+h),focus if focus!=65535 else -1)
    for i,o,ted in fields:
        left,top=x+o[7],y+o[8];width,height=o[9:11]
        rectangle(r,(left-1,top-1,left+width+1,top+height+1),1)
        rectangle(r,(left,top,left+width,top+height),0)
        text=b.memdump(ted[0],ted[-2]).split(b'\0')[0]
        start=number(c+layout['C context editScroll'])
        r.text=1;r.apply(8,(left,top+(height-8)//2+6),text[start:start+width//8])
        if number(c+layout['C context editTree'],4)==tree and number(c+layout['C context editObject'])==i:
            cursor=number(c+layout['C context editIndex'])-start
            rectangle(r,(left+cursor*8,top+(height-8)//2,left+cursor*8+1,top+(height-8)//2+8),1)
    if session and len(objects)==10:
        alert=number(session+311,4);icon=number(alert+508)
        if icon:
            source=ast.parse((ROOT/'build/gem-vdi/upstream/tools/gemdata.py').read_text())
            masks=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='ALERT_ICONS' for t in n.targets))
            words=masks[('NOTE','QUEST','STOP')[icon-1]]
            for yy in range(32):
                for xx in range(32):
                    if words[yy*2+xx//16]&(0x8000>>(xx%16)):
                        r.pixels[(y+16+yy)*640+x+16+xx]=PENS[1]
