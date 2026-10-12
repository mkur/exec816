"""Independent classic ICONBLK file and emitted-pixel checks."""
import struct
from native_program import require


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
    return result


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
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
    b.bp_clear_all()
