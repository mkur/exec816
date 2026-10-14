/* Presenter-owned frame fragments. Compose in the existing widget strip, then
 * publish only complete pixels. Work rectangles are never part of a fragment.
 * The packet/title borrow ends at return; only a scalar glyph offset survives. */
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include "gem-drawing.h"

extern void GemWidgetFill(UWORD,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
extern void GemWidgetText(WORD,WORD,const WORD *,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
static struct ConsoleBitmapPacket *paint;
static WORD glyphs[24];

static void fill(WORD l,WORD t,WORD r,WORD b,UWORD pen)
{
    if (l<paint->clipLeft) l=paint->clipLeft;
    if (t<paint->clipTop) t=paint->clipTop;
    if (r>paint->clipRight) r=paint->clipRight;
    if (b>paint->clipBottom) b=paint->clipBottom;
    if (l<r && t<b) GemWidgetFill(1,1,pen,l,t,r,b);
}

static void box(WORD l,WORD t,WORD r,WORD b)
{
    fill(l,t,r,t+1,1); fill(l,b-1,r,b,1);
    fill(l,t+1,l+1,b-1,1); fill(r-1,t+1,r,b-1,1);
}

static void text(WORD x,WORD y,UWORD count,UWORD pen)
{
    GemWidgetText(x,y,glyphs,count,pen,paint->clipLeft,paint->clipTop,
                  paint->clipRight,paint->clipBottom);
}

/* Short, wide GEM-style marks match the displayed pixel proportions. */
static void title_mark(WORD x,WORD y,UWORD full)
{
    WORD row,offset;
    for (row=0;row<7;++row) {
        offset=2*(row<4 ? row:6-row);
        if (full) offset=6-offset;
        fill(x+offset,y+row,x+offset+2,y+row+1,1);
        fill(x+12-offset,y+row,x+14-offset,y+row+1,1);
    }
}

/* Cached thumb coordinates come from the admitted window mutation. Each
 * strip draws only its intersection; no divide or tree traversal is needed. */
static void gadgets(WORD l,WORD t,WORD r,WORD b)
{
    struct ConsoleBitmapPacket *p=paint;
    WORD k=p->fillY,gw=DESKTOP_FRAME_GADGET_WIDTH,gh=DESKTOP_FRAME_GADGET_HEIGHT,left=r-gw;
    WORD top=t+DESKTOP_TITLE_HEIGHT+(k&DESKTOP_FRAME_INFO ? DESKTOP_FRAME_INFO_HEIGHT:0),bottom=b-(k&DESKTOP_FRAME_SIZER ? gh:DESKTOP_WORK_BOTTOM);
    WORD i,mid=left+gw/2,center;
    if (k&DESKTOP_FRAME_VERTICAL) {
        fill(left,top,r,bottom,8);
        if (k&DESKTOP_FRAME_UPARROW) {
            fill(left,top,r,top+gh,0);box(left,top,r,top+gh);
            center=top+(gh-5)/2;
            for (i=0;i<5;++i) fill(mid-i,center+i,mid+i+1,center+i+1,1);
            top+=gh;
        }
        if (k&DESKTOP_FRAME_DNARROW) {
            fill(left,bottom-gh,r,bottom,0);box(left,bottom-gh,r,bottom);
            center=bottom-1-(gh-5)/2;
            for (i=0;i<5;++i) fill(mid-i,center-i,mid+i+1,center-i+1,1);
            bottom-=gh;
        }
        box(left,top,r,bottom);
        if (k&DESKTOP_FRAME_VSLIDE) {
            top=t+p->fillWidth;bottom=top+p->fillHeight;
            fill(left+1,top,r-1,bottom,0);box(left,top,r,bottom);
        }
    }
    if (k&DESKTOP_FRAME_SIZER) {
        box(left,b-gh,r,b);
        for (i=2;i<=6;i+=2) {
            WORD j;
            for (j=0;j<i;++j) fill(r-4-2*j,b-2-i+j,r-2-2*j,b-1-i+j,1);
        }
    }
    (void)l;
}

static UWORD fragment(void)
{
    struct ConsoleBitmapPacket *p=paint;
    const UBYTE *title=(const UBYTE *)p->text;
    WORD l=p->x,t=p->y,r=l+p->width,b=t+p->height;
    WORD nameLeft=l+(p->background ? DESKTOP_FRAME_GADGET_WIDTH:DESKTOP_FRAME_EDGE);
    WORD iconRight=r-(p->fillY&DESKTOP_FRAME_FULLER ? DESKTOP_FRAME_GADGET_WIDTH:0);
    WORD hasIcon=iconRight-nameLeft>=DESKTOP_FRAME_GADGET_WIDTH+8+2*DESKTOP_TITLE_PAD;
    WORD nameRight=iconRight-(hasIcon ? DESKTOP_FRAME_GADGET_WIDTH:DESKTOP_FRAME_EDGE);
    WORD x,y=t+DESKTOP_TITLE_TEXT_Y;
    WORD pl,pt,pr,pb;
    UWORD span=nameRight-nameLeft;
    UWORD length=0,limit=nameRight>nameLeft+2*DESKTOP_TITLE_PAD ? (span-2*DESKTOP_TITLE_PAD)>>3:0;
    UWORD first,n;
    if (p->fillY&DESKTOP_FRAME_ICONIFIED) {
        fill(l,t,r,b,0);box(l,t,r,b);
        box(l+3,t+2,l+17,t+9);
        fill(l+4,t+3,l+16,t+4,12);
        for (n=0;n<8 && title[n];++n) glyphs[n]=title[n];
        text(l+20,t+1,n,1);
        p->fillX=0;
        return 1;
    }
    /* Side/bottom fragments are admitted inside the outer bounds. They need
     * only paper and the intersecting outline, never a title scan or glyphs. */
    if (p->clipTop>=t+DESKTOP_TITLE_HEIGHT) {
        if (!p->fillX) {
            fill(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,0);
            box(l,t,r,b);
            if (p->fillY&(DESKTOP_FRAME_SIZER|DESKTOP_FRAME_VERTICAL)) gadgets(l,t,r,b);
            if (p->fillY&DESKTOP_FRAME_INFO)
                fill(l,t+DESKTOP_TITLE_HEIGHT+DESKTOP_FRAME_INFO_HEIGHT-1,
                     r,t+DESKTOP_TITLE_HEIGHT+DESKTOP_FRAME_INFO_HEIGHT,1);
        }
        if (!(p->fillY&DESKTOP_FRAME_INFO) ||
            p->clipTop>=t+DESKTOP_TITLE_HEIGHT+DESKTOP_FRAME_INFO_HEIGHT) return 1;
        title+=DESKTOP_TITLE_BYTES;
        x=l+8;y=t+DESKTOP_TITLE_HEIGHT+1;
        span=r-x-8;
        limit=span>>3;
        while (length<DESKTOP_TITLE_BYTES-1 && length<limit && title[length]) ++length;
    } else {
        while (length<DESKTOP_TITLE_BYTES-1 && length<limit && title[length]) ++length;
    x=nameLeft+((nameRight-nameLeft-(length<<3))>>1);
    if (!p->fillX) {
        fill(l,t,r,b,0);
        box(l,t,r,b);
        fill(l,t+DESKTOP_TITLE_HEIGHT-1,r,t+DESKTOP_TITLE_HEIGHT,p->foreground ? 12:1);
        if (p->foreground) {
            pl=nameLeft>p->clipLeft ? nameLeft:p->clipLeft;
            pt=t+1>p->clipTop ? t+1:p->clipTop;
            pr=nameRight<p->clipRight ? nameRight:p->clipRight;
            pb=t+DESKTOP_TITLE_HEIGHT-1<p->clipBottom ?
               t+DESKTOP_TITLE_HEIGHT-1:p->clipBottom;
            if (pl<pr && pt<pb) GemFramePattern(pl,pt,pr,pb,l,t);
        }
        if (length) fill(x-DESKTOP_TITLE_PAD,t+1,x+(length<<3)+DESKTOP_TITLE_PAD,
                         t+DESKTOP_TITLE_HEIGHT-1,0);
        if (hasIcon) {
            box(iconRight-DESKTOP_FRAME_GADGET_WIDTH,t+1,iconRight-1,t+DESKTOP_TITLE_HEIGHT-1);
            box(iconRight-18,t+2,iconRight-4,t+9);
            fill(iconRight-10,t+5,iconRight-5,t+8,1);
        }
        if (p->fillY&DESKTOP_FRAME_FULLER) {
            box(r-DESKTOP_FRAME_GADGET_WIDTH,t+1,r-1,t+DESKTOP_TITLE_HEIGHT-1);
            title_mark(r-18,t+2,1);
        }
        if (p->background) {
            box(l+DESKTOP_CLOSE_LEFT,t+DESKTOP_CLOSE_TOP,
                l+DESKTOP_CLOSE_RIGHT,t+DESKTOP_CLOSE_BOTTOM);
            title_mark(l+4,t+2,0);
        }
    }
    }
    first=p->fillX;
    if (p->clipLeft>x && first<((p->clipLeft-x)>>3)) first=(p->clipLeft-x)>>3;
    if (y>=p->clipBottom || y+8<=p->clipTop || x+(first<<3)>=p->clipRight)
        first=length;
    n=length>first ? length-first:0;
    if (n>16) n=16;
    if (n) {
        UWORD i;
        for (i=0;i<n;++i) glyphs[i]=title[first+i];
        text(x+(first<<3),y,n,p->foreground && y==t+DESKTOP_TITLE_TEXT_Y ? 12:1);
    }
    first+=n;
    p->fillX=first<length && x+(first<<3)<p->clipRight ? first:0;
    return !p->fillX;
}

UWORD DesktopFrame(struct ConsoleBitmapPacket *p)
{
    UWORD status;
    paint=p;
    status=GemDrawingWidgetBatch(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,
                                !p->fillX,fragment);
    paint=0;
    return status;
}

/* Native popup rows use the same strip, font and disabled stipple as GEM
 * objects. The allocated popup owns its one-pixel outline. */
extern void GemWidgetStipple(UWORD,UWORD,UWORD,UWORD);
static UWORD menu_row(void)
{
    struct ConsoleBitmapPacket *p=paint;
    const UBYTE *label=(const UBYTE *)p->text;
    WORD l=p->x,t=p->y,r=l+p->width,b=t+p->height,row=p->fillY;
    UWORD first=p->fillX,n=0,selected=p->foreground && p->background;
    if (!first) {
        fill(l,row,r,row+DESKTOP_MENU_ROW_HEIGHT,0);
        fill(l+1,row>t ? row:t+1,r-1,row+DESKTOP_MENU_ROW_HEIGHT<b ? row+DESKTOP_MENU_ROW_HEIGHT:b-1,selected);
        box(l,t,r,b);
    }
    while (first+n<24 && label[first+n]) {
        glyphs[n]=label[first+n];++n;
    }
    if (n) GemWidgetText(l+8+(first<<3),row+DESKTOP_MENU_TEXT_Y,glyphs,n,!selected,
                         p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
    first+=n;
    p->fillX=first<24 && label[first] ? first:0;
    if (!p->fillX && !p->foreground) {
        WORD pl=l+1>p->clipLeft ? l+1:p->clipLeft;
        WORD pt=row>t ? row:t+1,pr=r-1<p->clipRight ? r-1:p->clipRight;
        WORD pb=row+DESKTOP_MENU_ROW_HEIGHT<b ? row+DESKTOP_MENU_ROW_HEIGHT:b-1;
        if (pt<p->clipTop) pt=p->clipTop;
        if (pb>p->clipBottom) pb=p->clipBottom;
        if (pl<pr && pt<pb) GemWidgetStipple(pl,pt,pr,pb);
    }
    return !p->fillX;
}

UWORD DesktopMenuRow(struct ConsoleBitmapPacket *p)
{
    UWORD status;
    paint=p;
    status=GemDrawingWidgetBatch(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,
                                !p->fillX,menu_row);
    paint=0;
    return status;
}

/* Neutral desktop paper; publish each complete bounded fragment once. */
static UWORD background(void)
{
    struct ConsoleBitmapPacket *p=paint;
    GemWidgetFill(1,1,8,p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
    return 1;
}

UWORD DesktopBackground(struct ConsoleBitmapPacket *p)
{
    UWORD status;
    paint=p;
    status=GemDrawingWidgetBatch(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,
                                1,background);
    paint=0;
    return status;
}
