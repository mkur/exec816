/* Bounded retained paint continuation, above the shared drawing owner. */
#include "widgets.h"
#include "gem-drawing.h"
static struct WidgetPacket *paint;
/* Scalar progress only; the scene token owns the context between calls. */
static WORD objectLeft;
/* Rejected objects also consume a step's CPU budget. */
#define PAINT_SCAN_LIMIT 8
#define PAINT_TEXT_WIDTH 96
extern void GemWidgetFill(uint16_t,uint16_t,uint16_t,uint16_t,uint16_t,uint16_t,uint16_t);
extern void GemWidgetText(int16_t,int16_t,const int16_t *,uint16_t,uint16_t,
                          uint16_t,uint16_t,uint16_t,uint16_t);
void WidgetFill(WORD mode,WORD style,WORD pattern,WORD colour,const GRECT *r)
{
    WORD l=r->g_x,t=r->g_y,right=l+r->g_w,bottom=t+r->g_h;
    (void)pattern;
    if (l<gl_clip.g_x) l=gl_clip.g_x;
    if (t<gl_clip.g_y) t=gl_clip.g_y;
    if (right>gl_clip.g_x+gl_clip.g_w) right=gl_clip.g_x+gl_clip.g_w;
    if (bottom>gl_clip.g_y+gl_clip.g_h) bottom=gl_clip.g_y+gl_clip.g_h;
    if (l<right && t<bottom) GemWidgetFill(mode,style,colour,l,t,right,bottom);
}
void WidgetText(WORD x,WORD y,const WORD *glyphs,WORD count,WORD mode,WORD colour)
{
    (void)mode;
    GemWidgetText(x,y,glyphs,count,colour,gl_clip.g_x,gl_clip.g_y,
        gl_clip.g_x+gl_clip.g_w,gl_clip.g_y+gl_clip.g_h);
}
static UWORD quantum(void)
{
    struct WidgetContext *c=(struct WidgetContext *)paint->context;
    uint16_t done=0,examined=0,index;
    WORD border,left,right,textTop;
    GRECT bounds,mark,clip=gl_clip;
    /* The validated root spans the client. A visible solid box supplies its
       own background; transparent or hidden roots need the client's fill.
       Keep that fill in the same drawing batch as the first visible objects. */
    if (!paint->index &&
        (c->objects[0].ob_type!=G_BOX || !WidgetVisible(c,0) ||
         ((c->objects[0].ob_spec>>4)&7)!=IP_SOLID))
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,c->background,&gl_clip);
    while (paint->index<c->count && examined<PAINT_SCAN_LIMIT) {
        index=c->order[paint->index];
        ++examined;
        bounds=c->bounds[index];
        border=c->objects[index].ob_type==G_BUTTON ?
            1+!!(c->objects[index].ob_flags&EXIT)+!!(c->objects[index].ob_flags&DEFAULT) : 0;
        bounds.g_x+=paint->originX-border;bounds.g_y+=paint->originY-border;
        bounds.g_w+=2*border;bounds.g_h+=2*border;
        if (!WidgetVisible(c,index) || bounds.g_x>=gl_clip.g_x+gl_clip.g_w ||
            bounds.g_y>=gl_clip.g_y+gl_clip.g_h ||
            bounds.g_x+bounds.g_w<=gl_clip.g_x || bounds.g_y+bounds.g_h<=gl_clip.g_y) {
            ++paint->index;
            continue;
        }
        /* One visible object, then scan a bounded rejected tail. Leave the
           next intersecting object untouched for the next native step. */
        if (done) break;
        /* Vertically clipped glyphs use the per-glyph path. Bound wide text
         * objects horizontally too, preserving donor drawing order inside
         * disjoint clips. Selected/focus XOR is applied once per pixel. */
        if (bounds.g_w>PAINT_TEXT_WIDTH && (c->objects[index].ob_type==G_STRING ||
            c->objects[index].ob_type==G_BUTTON)) {
            textTop=paint->originY+c->bounds[index].g_y+(c->bounds[index].g_h-8)/2;
            /* Whole glyph rows retain the fast run encoder. Only a partial
             * row needs this fallback continuation. */
            if (textTop<clip.g_y+clip.g_h && textTop+8>clip.g_y &&
                (textTop<clip.g_y || textTop+8>clip.g_y+clip.g_h)) {
                left=objectLeft ? objectLeft : bounds.g_x>clip.g_x ? bounds.g_x : clip.g_x;
                right=bounds.g_x+bounds.g_w;
                if (right>clip.g_x+clip.g_w) right=clip.g_x+clip.g_w;
                objectLeft=right-left>PAINT_TEXT_WIDTH ? left+PAINT_TEXT_WIDTH : 0;
                gl_clip.g_x=left;
                gl_clip.g_w=(objectLeft ? objectLeft : right)-left;
            }
        }
        WidgetDrawObject(c,index,paint->originX,paint->originY);
        if (paint->qualifiers && c->focus==index) {
            mark=c->bounds[index];
            mark.g_x+=paint->originX+3;mark.g_y+=paint->originY+mark.g_h-3;
            mark.g_w-=6;mark.g_h=1;
            WidgetFill(MD_XOR,FIS_SOLID,IP_SOLID,BLACK,&mark);
        }
        gl_clip=clip;
        done++;
        if (objectLeft) break;
        ++paint->index;
    }
    return paint->index==c->count;
}
uint16_t WidgetPaint(struct WidgetPacket *p)
{
    struct WidgetContext *c=(struct WidgetContext *)p->context;
    uint16_t status;
    if (!c || p->originX<0 || p->originY<0 ||
        (int32_t)p->originX+c->width>640 || (int32_t)p->originY+c->height>240 ||
        p->left<p->originX || p->top<p->originY ||
        p->right>p->originX+c->width || p->bottom>p->originY+c->height ||
        p->left>=p->right || p->top>=p->bottom || p->bottom-p->top>16)
        return DISPLAY_BAD_ARGUMENT;
    r_set(&gl_clip,p->left,p->top,p->right-p->left,p->bottom-p->top);
    if (!p->index) objectLeft=0;
    paint=p;
    status=GemDrawingWidgetBatch(p->left,p->top,p->right,p->bottom,p->index==0,quantum);
    p->changed=p->index<c->count;
    paint=0;
    return status;
}
