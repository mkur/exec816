/* Presenter menu binding of the existing extracted object renderer. */
#include "aes-hosted.h"
#include <exec816/menu-render.h>
#include "gem-drawing.h"
#include <exec816/aes-wire.h>

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

const char *WidgetSpec(uint32_t address)
{
    return (const char *)address;
}

static struct MenuRenderPacket *paint;
static OBJECT object;

static void checkmark(WORD x,WORD y,UWORD pen)
{
    WORD i;GRECT dot;
    for (i=0;i<6;++i) {
        r_set(&dot,x+2+i,y+6+(i<2 ? i:4-i),1,2);
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,pen,&dot);
    }
}

static UWORD quantum(void)
{
    OBJECT *tree=(OBJECT *)paint->context;
    /* Match the presenter's menu arrays, independent of widget-tree limits. */
    const WORD *parent=(const WORD *)paint->payload;
    const WORD *x=parent+AES_MENU_OBJECTS,*y=x+AES_MENU_OBJECTS;
    WORD at,next,l,t,r,b,left,right;
    UWORD examined=0,drawn=0,cells=0,cost;
    GRECT clip=gl_clip;
    if (!paint->index) {
        paint->index=paint->object;
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,WHITE,&clip);
    }
    while (examined++<AES_MENU_OBJECTS) {
        at=paint->index;
        l=paint->originX+x[at];t=paint->originY+y[at];
        r=l+tree[at].ob_width;b=t+tree[at].ob_height;
        if (!(tree[at].ob_flags&HIDETREE) && l<clip.g_x+clip.g_w &&
            r>clip.g_x && t<clip.g_y+clip.g_h && b>clip.g_y) {
            if (drawn==4) return 0;
            object=tree[at];
            if (at==paint->state || at==paint->qualifiers) object.ob_state|=SELECTED;
            if (object.ob_type==G_STRING || object.ob_type==G_TITLE) {
                left=l>clip.g_x ? l:clip.g_x;
                right=r<clip.g_x+clip.g_w ? r:clip.g_x+clip.g_w;
                /* Admission bounds a label and its width. Budget complete
                 * objects without rescanning strings or splitting glyph runs. */
                /* Both clip edges may cut cells; admission caps text at 63.
                 * This positive pixel span uses unsigned size arithmetic. */
                cost=((UWORD)(right-left)+14U)>>3;
                if (cost>63) cost=63;
                if (cells+cost>80) return 0;
                cells+=cost;
                gl_clip.g_x=left;
                gl_clip.g_w=right-left;
            }
            just_draw(&object,0,l,t);
            if (object.ob_type==G_STRING && (object.ob_state&CHECKED))
                checkmark(l,t,(object.ob_state&SELECTED) ? WHITE:BLACK);
            gl_clip=clip;
            ++drawn;
        }
        if (!(tree[at].ob_flags&HIDETREE) && tree[at].ob_head!=NIL) {
            paint->index=tree[at].ob_head;
            continue;
        }
        while (at!=paint->object) {
            next=tree[at].ob_next;
            if (next!=parent[at]) break;
            at=parent[at];
        }
        if (at==paint->object) { paint->index=0;return 1; }
        paint->index=tree[at].ob_next;
    }
    return 0;
}
uint16_t MenuPaint(struct MenuRenderPacket *p)
{
    UWORD status;
    paint=p;
    r_set(&gl_clip,p->left,p->top,p->right-p->left,p->bottom-p->top);
    status=GemDrawingWidgetBatch(p->left,p->top,p->right,p->bottom,!p->index,quantum);
    p->changed=p->index!=0;
    paint=0;
    return status;
}

/* Only presenter-owned GEM menu rendering crosses this private bridge. */
struct MenuRenderPacket MenuRenderPacket __attribute__((aligned(2)));
void MenuRenderEntry(void)
{
    struct MenuRenderPacket *p=&MenuRenderPacket;
    p->status=MENU_RENDER_BAD_ARGUMENT;p->changed=0;
    if (!p->context) return;
    if (p->operation==MENU_RENDER_OP_DRAW) p->status=MenuPaint(p);
    else if (p->operation==MENU_RENDER_OP_INVERT)
        p->status=GemDrawingInvertRows((const WORD *)&p->damage[0],p->index);
}
