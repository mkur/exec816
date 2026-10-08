/* Presenter menu binding of the existing extracted object renderer. */
#include "widgets.h"
#include "gem-drawing.h"

static struct WidgetPacket *paint;
static OBJECT object;
static WORD fragment;

static UWORD quantum(void)
{
    OBJECT *tree=(OBJECT *)paint->context;
    /* Admission's parent/x/y arrays are contiguous WORD arrays, 32 each. */
    const WORD *parent=(const WORD *)paint->payload;
    const WORD *x=parent+WIDGET_OBJECTS,*y=x+WIDGET_OBJECTS;
    WORD at,next,l,t,r,b,right;
    UWORD examined=0,drawn=0;
    GRECT bounds,clip=gl_clip;
    if (!paint->index) {
        paint->index=paint->object;
        fragment=0;
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,WHITE,&clip);
    }
    while (examined++<8) {
        at=paint->index;
        l=paint->originX+x[at];t=paint->originY+y[at];
        r=l+tree[at].ob_width;b=t+tree[at].ob_height;
        if (!(tree[at].ob_flags&HIDETREE) && l<clip.g_x+clip.g_w &&
            r>clip.g_x && t<clip.g_y+clip.g_h && b>clip.g_y) {
            if (drawn) return 0;
            object=tree[at];
            if (at==paint->state || at==paint->qualifiers) object.ob_state|=SELECTED;
            if (object.ob_type==G_STRING || object.ob_type==G_TITLE) {
                right=r<clip.g_x+clip.g_w ? r:clip.g_x+clip.g_w;
                gl_clip.g_x=fragment ? fragment:l>clip.g_x ? l:clip.g_x;
                gl_clip.g_w=right-gl_clip.g_x;
                if (gl_clip.g_w>96) gl_clip.g_w=96;
                fragment=gl_clip.g_x+gl_clip.g_w<right ? gl_clip.g_x+gl_clip.g_w:0;
            }
            WidgetCurrent=0; /* Menu specs are full caller addresses. */
            just_draw(&object,0,l,t);
            gl_clip=clip;
            drawn=1;
            if (fragment) return 0;
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
uint16_t MenuPaint(struct WidgetPacket *p)
{
    UWORD status;
    paint=p;
    r_set(&gl_clip,p->left,p->top,p->right-p->left,p->bottom-p->top);
    status=GemDrawingWidgetBatch(p->left,p->top,p->right,p->bottom,!p->index,quantum);
    p->changed=p->index!=0;
    paint=0;
    return status;
}
