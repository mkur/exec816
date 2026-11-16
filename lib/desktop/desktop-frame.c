/* Stored frame objects, composed through the existing scratch and grant.
 * UPDATE retains the tree/text; frame clips exclude client work. Native popup
 * rows below retain their independent scalar glyph continuation. */
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include "gem-drawing.h"
#include "application-hosted.h"

extern void GemWidgetFill(UWORD,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
extern void GemWidgetText(WORD,WORD,const WORD *,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
/* Shared scratch is bound only inside a physical-access callback. */
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

/* The current physical borrower owns GSX scratch and this prepared object.
 * UPDATE pins the tree and strings through every callback and fence. */
static GEMFRAMEDRAW *framePaint;
static struct ObjectPrepared frameObject;

static void frame_object(OBJECT *tree,WORD object,WORD x,WORD y)
{
    WORD image=-1;
    WORD right=x+tree[object].ob_width,bottom=y+tree[object].ob_height;
    if (tree[object].ob_flags&HIDETREE) return;
    if (object==GEM_O_FRAME) { right+=GEM_SHADOW;bottom+=GEM_SHADOW; }
    if (x>=paint->clipRight || y>=paint->clipBottom ||
        right<=paint->clipLeft || bottom<=paint->clipTop) return;
    prepare_draw(&frameObject,tree,object,x,y);
    if (object==GEM_O_NAME)
        frameObject.ink=framePaint->flags&1 ? 12:1;
    draw_prepared(&frameObject);
    /* Fixed platform artwork replaces the donor BOXCHAR character glyph;
     * its enclosing OBJECT still supplies position, size, colour and border. */
    switch (object) {
    case GEM_O_CLOSER:image=GEM_GADGET_CLOSE;break;
    case GEM_O_FULLER:image=GEM_GADGET_FULL;break;
    case GEM_O_ICONIFIER:image=GEM_GADGET_ICONIFY;break;
    case GEM_O_SIZER:
        if (tree[object].ob_spec>>24) image=GEM_GADGET_SIZE;
        break;
    case GEM_O_UP:image=GEM_GADGET_UP;break;
    case GEM_O_DOWN:image=GEM_GADGET_DOWN;break;
    case GEM_O_LEFT:image=GEM_GADGET_LEFT;break;
    case GEM_O_RIGHT:image=GEM_GADGET_RIGHT;break;
    }
    if (image>=0) GemFrameGadgetCentered(image,x,y,tree[object].ob_width,
        tree[object].ob_height,paint->clipLeft,paint->clipTop,
        paint->clipRight,paint->clipBottom);
    if (object==GEM_O_FRAME && (tree[object].ob_state&32)) {
        right=x+tree[object].ob_width;bottom=y+tree[object].ob_height;
        fill(right,y+GEM_SHADOW,right+GEM_SHADOW,bottom+GEM_SHADOW,1);
        fill(x+GEM_SHADOW,bottom,right,bottom+GEM_SHADOW,1);
    }
}

static UWORD fragment(void *context)
{
    struct ConsoleBitmapPacket *p=context;
    OBJECT *tree;
    WORD x,y,start;
    paint=p;
    framePaint=(GEMFRAMEDRAW *)p->text;
    gl_clip=framePaint->clip;
    p->clipLeft=gl_clip.g_x;p->clipTop=gl_clip.g_y;
    p->clipRight=gl_clip.g_x+gl_clip.g_w;
    p->clipBottom=gl_clip.g_y+gl_clip.g_h;
    /* The native producer clips full frames to disjoint frame-only pieces;
     * selected scrollbar subtrees are opaque and wholly outside client work. */
    fill(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,0);
    tree=(OBJECT *)framePaint->tree;start=framePaint->start;
    ob_offset(tree,start,&x,&y);
    x-=tree[start].ob_x;y-=tree[start].ob_y;
    everyobj(tree,start,tree[start].ob_next,frame_object,x,y,framePaint->depth);
    framePaint=0;paint=0;
    p->fillX=0;
    return 1;
}

UWORD DesktopFrame(struct ConsoleBitmapPacket *p)
{
    GEMFRAMEDRAW *frame=(GEMFRAMEDRAW *)p->text;
    WORD l=frame->clip.g_x,t=frame->clip.g_y;
    WORD r=l+frame->clip.g_w,b=t+frame->clip.g_h;
    if (b-t>16) return GemDrawingFrameBatch(l,t,r,b,fragment,p);
    return GemDrawingWidgetBatch(l,t,r,b,1,fragment,p);
}

UWORD DesktopFrameBorrow(struct DisplayGrant *grant,struct ConsoleBitmapPacket *p)
{
    GEMFRAMEDRAW *frame=(GEMFRAMEDRAW *)p->text;
    WORD l=frame->clip.g_x,t=frame->clip.g_y;
    return GemDrawingFrameBorrow(grant,l,t,l+frame->clip.g_w,
                                 t+frame->clip.g_h,fragment,p);
}

/* Native popup rows use the same strip, font and disabled stipple as GEM
 * objects. The allocated popup owns its one-pixel outline. */
extern void GemWidgetStipple(UWORD,UWORD,UWORD,UWORD);
static UWORD menu_row_draw(void *context)
{
    struct ConsoleBitmapPacket *p=context;
    paint=p;
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

static UWORD menu_row(void *context)
{
    UWORD done=menu_row_draw(context);
    paint=0;
    return done;
}

UWORD DesktopMenuRow(struct ConsoleBitmapPacket *p)
{
    UWORD status;
    status=GemDrawingWidgetBatch(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,
                                !p->fillX,menu_row,p);
    return status;
}

/* Neutral desktop paper; publish each complete bounded fragment once. */
static UWORD background(void *context)
{
    struct ConsoleBitmapPacket *p=context;
    GemWidgetFill(1,1,8,p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
    return 1;
}

UWORD DesktopBackground(struct ConsoleBitmapPacket *p)
{
    UWORD status;
    status=GemDrawingWidgetBatch(p->clipLeft,p->clipTop,p->clipRight,p->clipBottom,
                                1,background,p);
    return status;
}

UWORD DesktopMenuRowBorrow(struct DisplayGrant *grant,struct ConsoleBitmapPacket *p)
{
    return GemDrawingFrameBorrow(grant,p->clipLeft,p->clipTop,p->clipRight,
                                 p->clipBottom,menu_row,p);
}

UWORD DesktopBackgroundBorrow(struct DisplayGrant *grant,struct ConsoleBitmapPacket *p)
{
    return GemDrawingFrameBorrow(grant,p->clipLeft,p->clipTop,p->clipRight,
                                 p->clipBottom,background,p);
}
