/* Private hosted adapter appended to the selected GEM primitives. G2 owns
 * message/session lifetime; G3 owns hardware acquisition and completion.
 * No renderer call is safe until its caller owns the bound device.
 */
#include "hosted-vdi.h"
#include "operation-checks.inc"

uint16_t GemVdiBind(const VDIDEV *device)
{
    if (vdev || !device || (uint32_t)device > 0xffffffUL ||
        device->w != 640 || device->h != 240 || device->stride != 320 ||
        device->font_w != 8 || device->font_h != 8 || device->font_top != 6 ||
        !device->font_face || !device->fill_rect || !device->glyph ||
        !device->font_changed || !device->line_diag || !device->clear_screen ||
        !device->palette_all || !device->flush)
        return 1;
    vdev = device;
    return 0;
}

uint16_t GemVdiDispatch(uint16_t op, uint16_t sub, uint16_t handle,
                       uint16_t pairs, uint16_t words,
                       const int16_t *points, const int16_t *ints)
{
    uint16_t i, result = GemVdiValidate(op, sub, pairs, words, points, ints);
    if (result)
        return result;
    if (!vdev || (op == 1 ? (handle != 0 || vwk.handle != 0) :
                 (handle != VDI_PHYS_HANDLE || vwk.handle != VDI_PHYS_HANDLE)))
        return 3;
    /* Validate first: no globals or callback state change on rejection. */
    for (i = 0; i < pairs * 2; ++i)
        ptsin[i] = points[i];
    for (i = 0; i < words; ++i)
        intin[i] = ints[i];
    contrl[0] = op; contrl[1] = pairs; contrl[2] = 0;
    contrl[3] = words; contrl[4] = 0; contrl[5] = sub; contrl[6] = handle;
    switch (op) {
    case 1: vdi_v_opnwk(); break;
    case 2: vwk.handle = 0; break;
    case 3: vdi_v_clrwk(); break;
    case 4: break; /* The flush below is the device update. */
    case 6: vdi_v_pline(); break;
    case 8: vdi_v_gtext(); break;
    case 11: vdi_vr_recfl(); break;
    case 17: vdi_vsl_color(); break;
    case 22: vdi_vst_color(); break;
    case 23: vdi_vsf_interior(); break;
    case 25: vdi_vsf_color(); break;
    case 32: vdi_vswr_mode(); break;
    case 129: vdi_vs_clip(); break;
    default: return 1;
    }
    /* This private call submits work; successful service replies will fence. */
    dev_flush();
    return 0;
}

/* Service-facing entry points keep GEM typedefs out of the Exec unit. */
uint16_t GemVdiOpen(int16_t *workout)
{
    static const int16_t input[11]={1,1,1,1,1,1,1,1,1,1,2};
    uint16_t i,status=GemVdiBind(&hosted_vbxe_device);
    if (!status) status=GemVdiDispatch(1,0,0,0,11,0,input);
    if (status) return status;
    for (i=0;i<45;i++) workout[i]=intout[i];
    for (i=0;i<12;i++) workout[45+i]=ptsout[i];
    /* Deterministic initial pixels, before enabling the overlay. */
    return GemVdiDispatch(3,0,1,0,0,0,0);
}
uint16_t GemVdiCommand(uint16_t op,uint16_t sub,uint16_t pairs,uint16_t words,
    const int16_t *points,const int16_t *ints,int16_t *reply)
{
    uint16_t status=GemVdiDispatch(op,sub,1,pairs,words,points,ints);
    if (!status && contrl[4]==1) *reply=intout[0];
    return status;
}
void GemVdiReset(void)
{
    vwk.handle=0;
    vdev=0;
}

/* Ordinary drawing clients use the same device/font implementation, without
 * a VDI packet or service request. Validate the complete half-open rectangle
 * before converting to the device's inclusive geometry. */
extern void GemDrawingPrepare(uint16_t,uint16_t,uint16_t,uint16_t);

uint16_t GemBitmapFill(uint16_t x,uint16_t y,uint16_t right,uint16_t bottom,
                        uint16_t pen)
{
    if (!vdev || x>right || right>640 || y>bottom || bottom>240 || pen>15)
        return 1;
    if (x==right || y==bottom) return 0;
    GemDrawingPrepare(x,y,right,bottom);
    dev_fill_rect((WORD)x,(WORD)y,(WORD)(right-1),(WORD)(bottom-1),(WORD)pen);
    return 0;
}

static uint16_t bitmap_text_valid(uint16_t x,uint16_t y,const uint8_t *text,
    uint16_t count,uint16_t foreground,uint16_t background)
{
    uint32_t address=(uint32_t)text;
    if (!vdev || x>640 || y>232 || count>(640-x)/8 || foreground>15 || background>15 ||
        (count && (!text || address>0xffffffUL || count>0x1000000UL-address ||
                   (address<0x9000UL && address+count>0x8000UL))))
        return 0;
    return 1;
}

/* Fill geometry was admitted by the shared drawing entry. Both operations
 * reach the device only after the entire source and text extent are valid. */
uint16_t GemBitmapTextFill(uint16_t x,uint16_t y,const uint8_t *text,uint16_t count,
    uint16_t foreground,uint16_t background,uint16_t fillX,uint16_t fillY,
    uint16_t width,uint16_t height,uint16_t pen)
{
    extern void vbxe_text_run_fill(uint16_t,uint16_t,const uint8_t *,uint16_t,
        uint16_t,uint16_t,uint16_t,uint16_t,uint16_t,uint16_t,uint16_t);
    if (!count || (x&1) || !bitmap_text_valid(x,y,text,count,foreground,background))
        return 1;
    GemDrawingPrepare(x,y,x+count*8,y+8);
    GemDrawingPrepare(fillX,fillY,fillX+width,fillY+height);
    vbxe_text_run_fill(x,y,text,count,foreground,background,fillX,fillY,width,height,pen);
    return 0;
}

uint16_t GemBitmapText(uint16_t x,uint16_t y,const uint8_t *text,uint16_t count,
                        uint16_t foreground,uint16_t background)
{
    WORD color,mode,clip;
    uint16_t i;
    if (!bitmap_text_valid(x,y,text,count,foreground,background)) return 1;
    if (!count) return 0;
    GemDrawingPrepare(x,y,x+count*8,y+8);
    if (!(x&1)) {
        extern void vbxe_text_run(uint16_t,uint16_t,const uint8_t *,uint16_t,uint16_t,uint16_t);
        vbxe_text_run(x,y,text,count,foreground,background);
        return 0;
    }
    color=vwk.text_color; mode=vwk.wrt_mode; clip=vwk.clip;
    vwk.text_color=(WORD)foreground; vwk.wrt_mode=0; vwk.clip=0;
    dev_fill_rect((WORD)x,(WORD)y,(WORD)(x+count*8-1),(WORD)(y+7),(WORD)background);
    for (i=0;i<count;i++,x+=8) dev_glyph((WORD)text[i],(WORD)x,(WORD)y,1);
    vwk.text_color=color; vwk.wrt_mode=mode; vwk.clip=clip;
    return 0;
}

/* Pixel-exact half-open clipping, including an odd edge or a cut glyph.
 * Full cells retain the batched atlas path. The donor raster fallback writes
 * only the clipped ink; the explicit background fill also respects the clip. */
uint16_t GemBitmapTextClip(uint16_t x,uint16_t y,const uint8_t *text,uint16_t count,
    uint16_t foreground,uint16_t background,uint16_t left,uint16_t top,
    uint16_t right,uint16_t bottom)
{
    WORD color,mode,clip,x0,y0,x1,y1;
    uint16_t a,b,c,d,i;
    if (!bitmap_text_valid(x,y,text,count,foreground,background) ||
        left>right || right>640 || top>bottom || bottom>240) return 1;
    if (!count || left==right || top==bottom) return 0;
    a=x>left ? x:left; b=y>top ? y:top;
    c=x+count*8<right ? x+count*8:right; d=y+8<bottom ? y+8:bottom;
    if (a>=c || b>=d) return 0;
    if (a==x && b==y && c==x+count*8 && d==y+8)
        return GemBitmapText(x,y,text,count,foreground,background);
    GemDrawingPrepare(a,b,c,d);
    color=vwk.text_color; mode=vwk.wrt_mode; clip=vwk.clip;
    x0=vwk.xmn_clip; y0=vwk.ymn_clip; x1=vwk.xmx_clip; y1=vwk.ymx_clip;
    dev_fill_rect(a,b,c-1,d-1,background);
    vwk.text_color=foreground; vwk.wrt_mode=1; vwk.clip=1;
    vwk.xmn_clip=a; vwk.ymn_clip=b; vwk.xmx_clip=c-1; vwk.ymx_clip=d-1;
    for (i=0;i<count;i++,x+=8)
        if (x<c && x+8>a) dev_glyph(text[i],x,y,1);
    vwk.text_color=color; vwk.wrt_mode=mode; vwk.clip=clip;
    vwk.xmn_clip=x0; vwk.ymn_clip=y0; vwk.xmx_clip=x1; vwk.ymx_clip=y1;
    return 0;
}

/* Private AES graphics. Geometry has been intersected with the admitted outer
 * clip before these calls. Public VDI operation validation remains unchanged. */
void GemWidgetFill(uint16_t mode,uint16_t style,uint16_t pen,
    uint16_t left,uint16_t top,uint16_t right,uint16_t bottom)
{
    extern void vbxe_xor_rect(WORD,WORD,WORD,WORD);
    extern void GemWidgetStipple(uint16_t,uint16_t,uint16_t,uint16_t);
    if (mode==3) vbxe_xor_rect(left,top,right-1,bottom-1);
    else if (style==2) GemWidgetStipple(left,top,right,bottom);
    else dev_fill_rect(left,top,right-1,bottom-1,style==0 ? 0 : pen);
}
void GemWidgetText(int16_t x,int16_t y,const int16_t *glyphs,uint16_t count,
    uint16_t colour,uint16_t left,uint16_t top,uint16_t right,uint16_t bottom)
{
    extern const uint8_t map_col[16];
    extern void vbxe_widget_text_run(WORD,WORD,const WORD *,UWORD,WORD);
    WORD color=vwk.text_color,mode=vwk.wrt_mode,clip=vwk.clip;
    WORD x0=vwk.xmn_clip,y0=vwk.ymn_clip,x1=vwk.xmx_clip,y1=vwk.ymx_clip;
    UWORD n;
    vwk.text_color=colour;vwk.wrt_mode=1;vwk.clip=1;
    vwk.xmn_clip=left;vwk.ymn_clip=top;vwk.xmx_clip=right-1;vwk.ymx_clip=bottom-1;
    /* Signed cell coordinates; the admitted clip is inside the screen. */
    if (y<(WORD)bottom && y+8>(WORD)top) {
        while (count && x+8<=(WORD)left) { ++glyphs;--count;x+=8; }
        if (count && x<(WORD)left) {
            dev_glyph(*glyphs++,x,y,1);--count;x+=8;
        }
        if (count && y>=(WORD)top && y+8<=(WORD)bottom && map_col[colour&15]) {
            n=x<(WORD)right ? ((UWORD)((WORD)right-x)>>3) : 0;
            if (count<n) n=count;
            if (n) {
                vbxe_widget_text_run(x,y,glyphs,n,colour);
                glyphs+=n;count-=n;x+=(WORD)(n<<3);
            }
        }
        while (count && x<(WORD)right) {
            dev_glyph(*glyphs++,x,y,1);--count;x+=8;
        }
    }
    vwk.text_color=color;vwk.wrt_mode=mode;vwk.clip=clip;
    vwk.xmn_clip=x0;vwk.ymn_clip=y0;vwk.xmx_clip=x1;vwk.ymx_clip=y1;
}
