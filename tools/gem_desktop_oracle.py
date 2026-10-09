"""Public GEM application models rendered independently of target paint code."""
import struct
from native_program import require
from control_panel_oracle import draw
from test_desktop_presentation import rectangle


def paint(bridge,symbols,r,title,bounds):
    left,top,right,bottom=bounds
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
        draw(r,objects,labels,(left+8,top+16,right-8,bottom-8),focus)
        obj=objects[2];x=left+8+obj[7];y=top+16+obj[8];w,h=obj[9:11]
        rectangle(r,(x-1,y-1,x+w+1,y+h+1),1);rectangle(r,(x,y,x+w,y+h),0)
        r.text=1;r.apply(8,(x+w-len(text)*8,y+6),text)
        return
    if title==b'Counter':
        count=int.from_bytes(bridge.memdump(symbols['GEMCounter']+14,4),'little')
        r.clip=(left+8,top+16,right-9,bottom-9);r.text=4
        r.apply(8,(left+16,top+30),b'GEM counter')
        r.apply(8,(left+16,top+46),('Count: %06d'%count).encode())
        r.clip=(0,0,639,239);return
    if title==b'Files':
        base=symbols['GEMBrowser'];tree=int.from_bytes(bridge.memdump(base+170,4),'little')
        from browser_model import OBJECTS,FIELDS as F
        if 'objc_edit' in symbols and int.from_bytes(bridge.memdump(base+F['dialog'],2),'little'):
            raw=bridge.memdump(base+F['dialogTree'],6*24)
            objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(6)]
            labels={}
            for i,obj in enumerate(objects):
                if obj[3] in (26,28):
                    labels[i]=bridge.memdump(obj[6],128).split(b'\0')[0].decode('ascii');obj[6]=i
            field=objects[2][:];objects[2][3]=25;objects[2][6]=0
            objects[0][7]=objects[0][8]=0
            draw(r,objects,labels,(left+8,top+16,right-16,bottom-16))
            x,y=left+8+field[7],top+16+field[8];w,h=field[9:11]
            text=bridge.memdump(base+F['editText'],128).split(b'\0')[0]
            index=int.from_bytes(bridge.memdump(base+F['editIndex'],2),'little')
            active=int.from_bytes(bridge.memdump(base+F['focus'],2),'little')==2
            columns=min(w//8,63);start=0
            if active:
                from generate_aes_server import expected_layout
                offset=dict(expected_layout())['C context editScroll']
                # Backspace retains the viewport while the caret stays visible.
                start=int.from_bytes(bridge.memdump(symbols['__aes_context']+offset,2),'little')
                require(start<=index<start+columns,'Caret outside the editable viewport')
            visible=text[start:start+columns]
            r.clip=(left+8,top+16,right-17,bottom-17)
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
        objects[0][7]=objects[0][8]=0
        draw(r,objects,labels,(left+8,top+16,right-16,bottom-16))
        return
    require(title==b'GEM Control Panel','Unknown GEM desktop app: '+repr(title))
    base=symbols['GEMPanel'];raw=bridge.memdump(base+178,192)
    objects=[list(struct.unpack_from('<hhhHHHIhhhh',raw,i*24)) for i in range(8)]
    labels={}
    for i,obj in enumerate(objects):
        if obj[3] in (26,28,32):
            labels[i]=bridge.memdump(obj[6],64).split(b'\0')[0].decode('ascii');obj[6]=i
    objects[0][7]=objects[0][8]=0
    draw(r,objects,labels,(left+8,top+16,right-8,bottom-8))
    focus=int.from_bytes(bridge.memdump(base+392,2),'little');obj=objects[focus]
    rectangle(r,(left+8+obj[7]+3,top+16+obj[8]+13,left+8+obj[7]+77,top+16+obj[8]+14),1)
