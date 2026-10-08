/* Presenter-owned frame fragments. Compose in the existing widget strip, then
 * publish only complete pixels. Work rectangles are never part of a fragment.
 * The packet/title borrow ends at return; only a scalar glyph offset survives. */
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include "gem-drawing.h"

extern void GemWidgetFill(UWORD,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
extern void GemWidgetText(WORD,WORD,const WORD *,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
static struct ConsoleBitmapPacket *paint;
static WORD glyphs[16];

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

static void text(WORD x,WORD y,UWORD count)
{
    GemWidgetText(x,y,glyphs,count,1,paint->clipLeft,paint->clipTop,
                  paint->clipRight,paint->clipBottom);
}

static UWORD fragment(void)
{
    struct ConsoleBitmapPacket *p=paint;
    const UBYTE *title=(const UBYTE *)p->text;
    WORD l=p->x,t=p->y,r=l+p->width,b=t+p->height;
    WORD nameLeft=l+(p->background ? DESKTOP_TITLE_HEIGHT:DESKTOP_FRAME_EDGE);
    WORD nameRight=r-DESKTOP_FRAME_EDGE,x,y=t+DESKTOP_TITLE_TEXT_Y;
    WORD pl,pt,pr,pb;
    UWORD span=nameRight-nameLeft;
    UWORD length=0,limit=(span-2*DESKTOP_TITLE_PAD)>>3;
    UWORD first,n;
    /* Side/bottom fragments are admitted inside the outer bounds. They need
     * only paper and the intersecting outline, never a title scan or glyphs. */
    if (p->clipTop>=t+DESKTOP_TITLE_HEIGHT) {
        GemWidgetFill(1,1,0,p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
        if (p->clipLeft==l)
            GemWidgetFill(1,1,1,l,p->clipTop,l+1,p->clipBottom);
        if (p->clipRight==r)
            GemWidgetFill(1,1,1,r-1,p->clipTop,r,p->clipBottom);
        if (p->clipBottom==b)
            GemWidgetFill(1,1,1,p->clipLeft,b-1,p->clipRight,b);
        return 1;
    }
    while (length<DESKTOP_TITLE_BYTES-1 && length<limit && title[length]) ++length;
    x=nameLeft+((nameRight-nameLeft-(length<<3))>>1);
    if (!p->fillX) {
        fill(l,t,r,b,0);
        box(l,t,r,b);
        fill(l,t+DESKTOP_TITLE_HEIGHT-1,r,t+DESKTOP_TITLE_HEIGHT,1);
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
        if (p->background) {
            box(l+DESKTOP_CLOSE_LEFT,t+DESKTOP_CLOSE_TOP,
                l+DESKTOP_CLOSE_RIGHT,t+DESKTOP_CLOSE_BOTTOM);
            glyphs[0]=DESKTOP_CLOSE_GLYPH;
            text(l+DESKTOP_CLOSE_TEXT_X,y,1);
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
        text(x+(first<<3),y,n);
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
        fill(l,row,r,row+16,0);
        fill(l+1,row>t ? row:t+1,r-1,row+16<b ? row+16:b-1,selected);
        box(l,t,r,b);
    }
    while (n<16 && first+n<24 && label[first+n]) {
        glyphs[n]=label[first+n];++n;
    }
    if (n) GemWidgetText(l+8+(first<<3),row+4,glyphs,n,!selected,
                         p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
    first+=n;
    p->fillX=first<24 && label[first] ? first:0;
    if (!p->fillX && !p->foreground) {
        WORD pl=l+1>p->clipLeft ? l+1:p->clipLeft;
        WORD pt=row>t ? row:t+1,pr=r-1<p->clipRight ? r-1:p->clipRight;
        WORD pb=row+16<b ? row+16:b-1;
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

/* The fixed desktop pattern is screen-anchored, unlike the active title.
 * Fill/stipple stay offscreen until this complete <=16-row fragment is ready. */
static UWORD background(void)
{
    struct ConsoleBitmapPacket *p=paint;
    GemWidgetFill(1,1,8,p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
    GemWidgetStipple(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
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
