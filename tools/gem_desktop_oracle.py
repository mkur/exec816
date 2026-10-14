"""Public GEM application models rendered independently of target paint code."""
import struct
from native_program import require
from control_panel_oracle import draw
from test_desktop_presentation import rectangle


def paint(bridge,symbols,r,title,bounds):
    left,top,right,bottom=bounds
    if title in (b'Dialog example',b'Alert',b'File selector'):
        from standard_dialog_oracle import paint as dialog
        dialog(bridge,symbols,r,bounds)
        return
    if symbols.get('GEMDesk'):
        from colour_desktop_model import FIELDS as D,ICONS
        from browser_model import FIELDS as B
        base=symbols['GEMDesk']
        if title==b'':
            raw=bridge.memdump(base+D['tree'],(ICONS+2)*24)
            objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(ICONS+2)]
            icons=[o[:] for o in objects if o[3] in (31,33)]
            labels={}
            for i,o in enumerate(objects):
                if o[3] in (31,33):o[3]=25;o[5]=0;o[6]=0
                elif o[3]==28:
                    labels[i]=bridge.memdump(o[6],65).split(b'\0')[0].decode('ascii');o[6]=i
            objects[0][7]=objects[0][8]=0
            draw(r,objects,labels,bounds)
            for o in icons:icon(bridge,r,o,bounds)
            return
        for slot in range(3):
            folder=int.from_bytes(bridge.memdump(base+D['folders']+slot*4,4),'little')
            if folder and title==bridge.memdump(folder+B['path'],65).split(b'\0')[0][:64]:
                work=struct.unpack('<4h',bridge.memdump(folder+B['work'],8))
                if work[0]==left+8 and work[1]==top+11:
                    return paint(bridge,{**symbols,'GEMBrowser':folder,'GEMDesk':0},r,title,bounds)
        require(False,'No desktop folder model for '+repr(title))
    if 'GEMText' in symbols:
        from text_viewer_oracle import paint as text
        text(bridge,symbols,r,bounds)
        return
    if title==b'Calculator':
        base=symbols['Calculator'];tree=int.from_bytes(bridge.memdump(symbols['tree'],4),'little')
        raw=bridge.memdump(tree,21*24)
        objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(21)]
        labels={}
        for i,obj in enumerate(objects):
            if obj[3] in (26,28):
                labels[i]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii');obj[6]=i
        ted=struct.unpack('<III8h',bridge.memdump(objects[2][6],28))
        text=bridge.memdump(ted[0],12).split(b'\0')[0]
        # The resource's fixed, right-aligned noneditable display is checked
        # independently of the target TED renderer; button drawing reuses AES ref.
        objects[2][3]=25;objects[2][6]=0
        objects[0][7]=objects[0][8]=0
        focus=int.from_bytes(bridge.memdump(base+6,2),'little')
        draw(r,objects,labels,(left+8,top+11,right-8,bottom-2),focus)
        obj=objects[2];x=left+8+obj[7];y=top+11+obj[8];w,h=obj[9:11]
        rectangle(r,(x-1,y-1,x+w+1,y+h+1),1);rectangle(r,(x,y,x+w,y+h),0)
        r.text=1;r.apply(8,(x+w-len(text)*8,y+6),text)
        return
    if title==b'Counter':
        count=int.from_bytes(bridge.memdump(symbols['GEMCounter']+14,4),'little')
        r.clip=(left+8,top+11,right-9,bottom-3);r.text=4
        r.apply(8,(left+16,top+25),('Count: %06d'%count).encode())
        r.clip=(0,0,639,239);return
    if 'GEMBrowser' in symbols and title==bridge.memdump(symbols['GEMBrowser']+178,65).split(b'\0')[0][:64]:
        base=symbols['GEMBrowser'];tree=int.from_bytes(bridge.memdump(base+170,4),'little')
        from browser_model import OBJECTS,FIELDS as F
        dialog=int.from_bytes(bridge.memdump(base+F['dialog'],2),'little')
        if 'objc_edit' in symbols and dialog and dialog!=6:
            raw=bridge.memdump(base+F['dialogTree'],7*24)
            objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(7)]
            labels={}
            for i,obj in enumerate(objects):
                if obj[3] in (26,28):
                    labels[i]=bridge.memdump(obj[6],128).split(b'\0')[0].decode('ascii');obj[6]=i
            if objects[2][3]==28:  # Copy progress uses an ordinary string.
                objects[0][7]=objects[0][8]=0
                draw(r,objects,labels,(left+8,top+11,right-16,bottom-11),clip_strings=True)
                return
            field=objects[2][:];objects[2][3]=25;objects[2][6]=0
            objects[0][7]=objects[0][8]=0
            draw(r,objects,labels,(left+8,top+11,right-16,bottom-11),clip_strings=True)
            x,y=left+8+field[7],top+11+field[8];w,h=field[9:11]
            text=bridge.memdump(base+F['editText'],128).split(b'\0')[0]
            index=int.from_bytes(bridge.memdump(base+F['editIndex'],2),'little')
            from generate_aes_server import expected_layout
            context=dict(expected_layout())
            edit_tree=int.from_bytes(bridge.memdump(symbols['__aes_context']+context['C context editTree'],4),'little')
            active=edit_tree==base+F['dialogTree'] and int.from_bytes(bridge.memdump(base+F['focus'],2),'little')==2
            columns=min(w//8,63);start=0
            if active:
                from generate_aes_server import expected_layout
                offset=dict(expected_layout())['C context editScroll']
                # Backspace retains the viewport while the caret stays visible.
                start=int.from_bytes(bridge.memdump(symbols['__aes_context']+offset,2),'little')
                require(start<=index<start+columns,'Caret outside the editable viewport')
            visible=text[start:start+columns]
            r.clip=(left+8,top+11,right-23,bottom-12)
            rectangle(r,(x-1,y-1,x+w+1,y+h+1),1);rectangle(r,(x,y,x+w,y+h),0)
            r.text=1;r.apply(8,(x,y+(h-8)//2+6),visible)
            if active:rectangle(r,(x+(index-start)*8,y+(h-8)//2,x+(index-start)*8+1,y+(h-8)//2+8),1)
            r.clip=(0,0,639,239)
            return
        raw=bridge.memdump(tree,OBJECTS*24)
        objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(OBJECTS)]
        labels={}
        for i,obj in enumerate(objects):
            if obj[3] in (26,28,32):
                labels[i]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii');obj[6]=i
        icons=[]
        for obj in objects:
            if obj[3] in (31,33):
                if not obj[4]&128:icons.append(obj[:])
                obj[3]=25;obj[5]=0;obj[6]=0
        # The focus decoration follows the icons in the real OBJECT tree.
        # Rasterize it last too, including the edge beside a selected label.
        focus=[obj[:] for obj in (objects[1],*objects[-4:])]
        objects[1][4]|=128
        objects[0][7]=objects[0][8]=0
        draw(r,objects,labels,(left+8,top+11,right-16,bottom-11),clip_strings=True)
        for obj in icons:icon(bridge,r,obj,(left+8,top+11,right-16,bottom-11))
        if not focus[0][4]&128:
            focus[0][0:3]=[-1,1,4]
            for i in range(1,5):focus[i][0]=i+1 if i<4 else 0
            draw(r,focus,{},(left+8,top+11,right-16,bottom-11))
        if dialog==6:
            raw=bridge.memdump(base+F['dialogTree'],7*24)
            objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(7)]
            labels={}
            for i,obj in enumerate(objects):
                if obj[3] in (26,28):
                    labels[i]=bridge.memdump(obj[6],128).split(b'\0')[0].decode('ascii');obj[6]=i
            objects[0][7]-=left+8;objects[0][8]-=top+11
            draw(r,objects,labels,(left+8,top+11,right-16,bottom-11),clip_strings=True)
        return
    require(title==b'Control Panel','Unknown GEM desktop app: '+repr(title))
    base=symbols['GEMPanel'];raw=bridge.memdump(base+178,192)
    objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(8)]
    labels={}
    for i,obj in enumerate(objects):
        if obj[3] in (26,28,32):
            labels[i]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii');obj[6]=i
    objects[0][7]=objects[0][8]=0
    draw(r,objects,labels,(left+8,top+11,right-8,bottom-2))
    focus=int.from_bytes(bridge.memdump(base+392,2),'little');obj=objects[focus]
    rectangle(r,(left+8+obj[7]+3,top+11+obj[8]+13,left+8+obj[7]+77,top+11+obj[8]+14),1)


def icon(bridge,r,obj,bounds):
    """Read native public ICONBLK planes, independent of target blit commands."""
    l,t,right,bottom=bounds;x=l+obj[7];y=t+obj[8]
    fields=struct.unpack('<IIIH10h',bridge.memdump(obj[6],34))
    mask,data,label,char,xc,yc,xi,yi,width,height,xt,yt,wt,ht=fields
    colour=None
    if obj[3]==33:
        address=int.from_bytes(bridge.memdump(obj[6]+34,4),'little')
        while address:
            planes,normal,nmask,selected,smask,address=struct.unpack('<hIIIII',bridge.memdump(address,22))
            if planes==4:
                data,mask=(selected,smask) if obj[5]&1 and selected else (normal,nmask)
                colour=bridge.memdump(data,width//2*height)
                break
    fg,bg=char>>12,(char>>8)&15
    if obj[5]&1:fg,bg=bg,fg
    count=width//16*height
    mask=struct.unpack('<%dH'%count,bridge.memdump(mask,count*2))
    if colour is None:data=struct.unpack('<%dH'%count,bridge.memdump(data,count*2))
    def pixel(px,py,pen):
        if l<=px<right and t<=py<bottom:r.pixel(px,py,pen)
    for yy in range(height):
        for xx in range(width):
            index=yy*(width//16)+xx//16;bit=0x8000>>(xx%16)
            if colour is None:
                if (mask[index]|data[index])&bit:pixel(x+xi+xx,y+yi+yy,fg if data[index]&bit else bg)
            elif mask[index]&bit:
                from gem_render_oracle import PENS
                value=colour[(yy*width+xx)//2]
                pixel(x+xi+xx,y+yi+yy,PENS.index(value&15 if xx&1 else value>>4))
    def glyph(code,gx,gy):
        for yy in range(8):
            for xx in range(8):
                if r.font[yy*256+code]&(128>>xx):pixel(gx+xx,gy+yy,fg)
    if char&255:glyph(char&255,x+xi+xc,y+yi+yc)
    label=bridge.memdump(label,12 if obj[3]==33 else 64).split(b'\0')[0][:wt//8]
    if not label:return
    for yy in range(ht):
        for xx in range(wt):pixel(x+xt+xx,y+yt+yy,bg)
    start=x+xt+(wt-len(label)*8)//2
    for i,code in enumerate(label):glyph(code,start+i*8,y+yt)
