/* Bounded retained paint continuation, above the shared drawing owner. */
#include "widgets.h"
#include "gem-drawing.h"
static struct WidgetPacket *paint;
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
static void quantum(void)
{
    struct WidgetContext *c=(struct WidgetContext *)paint->context;
    uint16_t done=0,index;
    GRECT mark;
    while (paint->index<c->count && done<4) {
        index=c->order[paint->index++];
        WidgetDrawObject(c,index,paint->originX,paint->originY);
        if (paint->qualifiers && c->focus==index && WidgetVisible(c,index)) {
            mark=c->bounds[index];
            mark.g_x+=paint->originX+3;mark.g_y+=paint->originY+mark.g_h-3;
            mark.g_w-=6;mark.g_h=1;
            WidgetFill(MD_XOR,FIS_SOLID,IP_SOLID,BLACK,&mark);
        }
        done++;
    }
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
    paint=p;
    status=GemDrawingBatch(p->left,p->top,p->right,p->bottom,quantum);
    p->changed=p->index<c->count;
    paint=0;
    return status;
}
