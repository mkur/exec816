"""Independent classic ICONBLK file and emitted-pixel checks."""
import struct
from native_program import require

LAYOUT=[('ICONBLK '+n,v) for n,v in zip(
    ('size','mask','data','text','char','width','height','text height'),(34,0,4,8,12,22,24,32))]
LAYOUT += [('CICON '+n,v) for n,v in zip(
    ('size','planes','data','mask','selected data','selected mask','next'),(22,0,2,6,10,14,18))]
LAYOUT += [('CICONBLK '+n,v) for n,v in zip(('size','mono','mainlist'),(38,0,34))]


def cases():
    # Two icons share the mask and data. Relocation must not swap either twice.
    object_at,icon_at,tree_at,bits_at=36,108,176,180
    mask=[0xF3C0 if i%2 else 0x83FE for i in range(32)]
    data=[0xA140 if i%2 else 0x4202 for i in range(32)]
    text_at=bits_at+128;size=text_at+2
    header=[0,object_at,0,icon_at,0,0,text_at,0,0,tree_at,3,1,0,2,0,0,0,size]
    objects=struct.pack('>hhhHHHI4H',-1,1,2,20,0,0,0x1175,0,0,20,10)
    for i in range(2):objects+=struct.pack('>hhhHHHI4H',2 if not i else 0,-1,-1,31,32 if i else 0,0,icon_at+34*i,1+8*i,1,8,4)
    icon=struct.pack('>III11h',bits_at,bits_at+64,text_at,0x2341,2,3,8,0,32,16,0,18,64,8)
    payload=struct.pack('>18H',*header)+objects+icon*2+struct.pack('>I',object_at)+struct.pack('>64H',*(mask+data))+b'I\0'
    result={'ICON.RSC':payload}
    for name,offset,value in [('ICWIDTH.RSC',icon_at+22,17),('ICHEIGHT.RSC',icon_at+24,65)]:
        bad=bytearray(payload);struct.pack_into('>H',bad,offset,value);result[name]=bytes(bad)
    bad=bytearray(payload);struct.pack_into('>I',bad,icon_at,size-2);result['ICEXT.RSC']=bytes(bad)
    result.update(colour_cases())
    return result


def colour_cases():
    # Hand-built standard RSC, independent of the production JSON writer.
    nodes=6;classic=36+24*nodes+4;table=classic+12
    blocks=[]
    for kind in range(4):
        width,height=(64,64) if kind==3 else (32,16)
        words=width//16*height
        mono=struct.pack('>%dH'%words,*[0xa140 if i&1 else 0x4202 for i in range(words)])
        mask=struct.pack('>%dH'%words,*[0xf3c0 if i&1 else 0x83fe for i in range(words)])
        planes=2 if kind==2 else 4
        def data(selected=False):
            pixels=[(15-((x+y)&15) if selected else (x+y)&15) for y in range(height) for x in range(width)]
            return b''.join(bytes(sum(128>>bit for bit,v in enumerate(pixels[i:i+8]) if v&(1<<p))
                                 for i in range(0,len(pixels),8)) for p in range(planes))
        selected=kind==0
        blocks.append(struct.pack('>IIIH10hI',0,0,0,0x1041,2,3,8,0,width,height,0,height+2,96,8,1)+
            mono+mask+b'COLOURICON12'+struct.pack('>hIIIII',planes,0,0,int(selected),0,0)+data()+mask+
            (data(True)+b'\x5a\xa5'*words if selected else b''))
    objects=struct.pack('>hhhHHHI4H',-1,1,5,25,0,0,0,0,0,20,12)
    for i in range(5):
        objects+=struct.pack('>hhhHHHI4H',0 if i==4 else i+2,-1,-1,33,32 if i==4 else 0,0,
                             i if i<4 else 0,0,0,12,10)
    extension=bytes(16)+b'\xff'*4+b''.join(blocks)
    total=classic+12+len(extension)
    payload=(struct.pack('>18H',4,36,0,0,0,0,0,0,0,36+24*nodes,nodes,1,0,0,0,0,0,classic)+
             objects+struct.pack('>I',36)+struct.pack('>III',total,table,0)+extension)
    result={'CICONS.RSC':payload};block=table+20;form=block+38+128+12
    for name,at,fmt,value in [('CILEN.RSC',classic,'I',total-1),('CITAB.RSC',classic+4,'I',total),
                              ('CIINDEX.RSC',36+24+12,'I',4),('CIWIDTH.RSC',block+22,'H',17),
                              ('CIPLANE.RSC',form,'H',0),('CICOUNT.RSC',block+34,'I',257)]:
        bad=bytearray(payload);struct.pack_into('>'+fmt,bad,at,value);result[name]=bytes(bad)
    bad=bytearray(payload[:-2]);struct.pack_into('>I',bad,classic,len(bad));result['CICUT.RSC']=bytes(bad)
    return result


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from gem_render_oracle import Raster,font_bytes,DESKTOP_PALETTE as PALETTE,PENS
    sy=foreign['symbols'];out=p['output'].parent
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=condition)
        run_to(b,p['labels']['native_nmi'],condition=condition,frame_limit=6000,timeout=120)
    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    font=font_bytes(out/'selected/src/vdi/font8x8.c');report['icons']=[]
    for case in range(8):
        reach('dw($%x)=%d'%(sy['IconPhase'],case+1))
        reach('@frame>=%d'%(b.eval_expr('@frame')+3))
        require(b.peek16(sy['AESFailures'])==0,'Icon target checks: '+str(b.peek16(sy['AESFirstFailure'])))
        raster=Raster(font);raster.apply(25,ints=[5]);raster.apply(11,[8,40,631,223])
        x=57+(case&1);y=81;fg,bg=(3,2) if case&2 else (2,3)
        l,t,r,bottom=(x+11,y+2,x+35,y+23) if case>=4 else (8,40,632,224)
        def pixel(px,py,pen):
            if l<=px<r and t<=py<bottom:raster.pixel(px,py,pen)
        for row in range(16):
            for col in range(32):
                index=row*2+col//16;bit=0x8000>>(col%16)
                m=0xF3C0 if index%2 else 0x83FE;d=0xA140 if index%2 else 0x4202
                if (m|d)&bit:pixel(x+8+col,y+row,fg if d&bit else bg)
        def glyph(ch,gx,gy):
            for row in range(8):
                for col in range(8):
                    if font[row*256+ord(ch)]&(128>>col):pixel(gx+col,gy+row,fg)
        glyph('A',x+10,y+3)
        for yy in range(y+18,y+26):
            for xx in range(x,x+64):pixel(xx,yy,bg)
        glyph('I',x+28,y+18)
        path=out/f'icon-{case}.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
        # Includes untouched neighbouring bytes and transparent holes.
        for yy in range(72,114):
            for xx in range(48,136):
                at=yy*frame.stride+(xx+16)*4
                require(raw[at:at+3]==colors[raster.pixels[yy*640+xx]],f'Icon {case} pixel {xx},{yy}')
        report['icons'].append(dict(case=case,source='compiled' if case<4 else 'RSC',pixels=88*42))
        b.poke16(sy['IconGo'],case+1)
    colour_physical(b,p,sy,report,reach,font,colors)
    b.bp_clear_all()


def colour_physical(b,p,sy,report,reach,font,colors):
    from gem_render_oracle import Raster,PENS
    out=p['output'].parent;report['colour_icons']=[]
    for case in range(18):
        reach('dw($%x)=%d'%(sy['IconPhase'],case+9))
        reach('@frame>=%d'%(b.eval_expr('@frame')+3))
        require(b.peek16(sy['AESFailures'])==0,'Colour icon target check: '+str(b.peek16(sy['AESFirstFailure'])))
        raster=Raster(font);raster.apply(25,ints=[5]);raster.apply(11,[8,40,631,223])
        x,y=57+(case&1),81;selected=bool(case&2);fg,bg=(0,1) if selected else (1,0)
        width,height=(64,64) if case>=16 else (32,16)
        l,t,r,bottom=(x+11,y+2,x+35,y+23) if 4<=case<8 else (8,40,632,224)
        def pixel(px,py,pen):
            if l<=px<r and t<=py<bottom:raster.pixel(px,py,pen)
        for yy in range(height):
            for xx in range(width):
                index=yy*(width//16)+xx//16;bit=0x8000>>(xx%16)
                mask=0xf3c0 if index&1 else 0x83fe
                if 12<=case<16:
                    data=0xa140 if index&1 else 0x4202
                    if (mask|data)&bit:pixel(x+8+xx,y+yy,fg if data&bit else bg)
                else:
                    variant=selected and case<8
                    if variant:mask=0x5aa5
                    if mask&bit:
                        value=(xx+yy)&15
                        pixel(x+8+xx,y+yy,PENS.index(15-value if variant else value))
        def glyph(code,gx,gy):
            for yy in range(8):
                for xx in range(8):
                    if font[yy*256+code]&(128>>xx):pixel(gx+xx,gy+yy,fg)
        glyph(ord('A'),x+10,y+3)
        for yy in range(height+2,height+10):
            for xx in range(96):pixel(x+xx,y+yy,bg)
        label=b'COLOURICON12'
        for i,code in enumerate(label):glyph(code,x+(96-len(label)*8)//2+i*8,y+height+2)
        path=out/f'colour-icon-{case}.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
        for yy in range(72,158):
            for xx in range(48,162):
                at=yy*frame.stride+(xx+16)*4
                require(raw[at:at+3]==colors[raster.pixels[yy*640+xx]],f'Colour icon {case} pixel {xx},{yy}')
        report['colour_icons'].append(dict(case=case,pixels=114*86))
        b.poke16(sy['IconGo'],case+9)
