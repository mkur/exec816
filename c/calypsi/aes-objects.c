/* Application binding of the extracted GEM4XE object algorithms. */
#include "aes-private.h"
#include "vdi-private.h"
#include "application-hosted.h"
#include "gem-drawing.h"

extern void GemWidgetFill(UWORD,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);
extern void GemWidgetText(WORD,WORD,const WORD *,UWORD,UWORD,UWORD,UWORD,UWORD,UWORD);

void WidgetFill(WORD mode,WORD style,WORD pattern,WORD colour,const GRECT *r)
{
    WORD l=r->g_x,t=r->g_y,b=t+r->g_h,right=l+r->g_w;
    (void)pattern;
    if (l<gl_clip.g_x) l=gl_clip.g_x;
    if (t<gl_clip.g_y) t=gl_clip.g_y;
    if (right>gl_clip.g_x+gl_clip.g_w) right=gl_clip.g_x+gl_clip.g_w;
    if (b>gl_clip.g_y+gl_clip.g_h) b=gl_clip.g_y+gl_clip.g_h;
    if (l<right && t<b) GemWidgetFill(mode,style,colour,l,t,right,b);
}
void WidgetText(WORD x,WORD y,const WORD *glyphs,WORD count,WORD mode,WORD colour)
{
    (void)mode;
    GemWidgetText(x,y,glyphs,count,colour,gl_clip.g_x,gl_clip.g_y,
                  gl_clip.g_x+gl_clip.g_w,gl_clip.g_y+gl_clip.g_h);
}

struct ObjectPaint { struct ExecAESContext *context; OBJECT *tree; WORD object,x,y; GRECT clip; };
static void draw(void *data)
{
    struct ObjectPaint *p=data;
    gl_clip=p->clip;
    if ((p->tree[p->object].ob_flags&EDITABLE) ||
        p->tree[p->object].ob_type==G_FTEXT || p->tree[p->object].ob_type==G_FBOXTEXT)
        ExecAESDrawEdit(p->context,p->tree,p->object,p->x,p->y);
    else just_draw(p->tree,p->object,p->x,p->y);
}

/* The caller owns its tree and UPDATE snapshot. Only the linked draw callback
 * touches shared GSX scratch, after DisplayEnter and before DisplayLeave. */
WORD objc_draw(OBJECT *tree,WORD start,WORD depth,WORD x,WORD y,WORD w,WORD h)
{
    struct ExecAESContext *c=ExecAESContext();
    struct ObjectPaint p;
    struct AESWindowView *v;
    WORD obj=start,level=0,next,border,l,t,r,b,row,vl,vt,vr,vb;
    UWORD i;
    if (!c || !ExecAESEnter(c)) return 0;
    if (!c->workstation || !c->view || !c->view->shown || !c->view->updates) {
        c->diagnostic=AES_BUSY; c->busy=0; return 0;
    }
    v=c->view; p.tree=tree; p.context=c;
    if (depth>MAX_DEPTH) depth=MAX_DEPTH;
    if (w<=0 || h<=0) { c->busy=0; return 1; }
    for (;;) {
        if (!(tree[obj].ob_flags&HIDETREE)) {
            p.object=obj; ob_offset(tree,obj,&p.x,&p.y);
            border=tree[obj].ob_type==G_BUTTON ?
                1+!!(tree[obj].ob_flags&EXIT)+!!(tree[obj].ob_flags&DEFAULT):0;
            if (tree[obj].ob_type==G_BOXTEXT || tree[obj].ob_type==G_TEXT ||
                tree[obj].ob_type==G_FTEXT || tree[obj].ob_type==G_FBOXTEXT) {
                border=((const TEDINFO *)(ULONG)tree[obj].ob_spec)->te_thickness;
                border=border<0 ? -border:0;
            }
            l=p.x-border; t=p.y-border;
            r=p.x+tree[obj].ob_width+border; b=p.y+tree[obj].ob_height+border;
            if (l<x) l=x;
            if (t<y) t=y;
            if (r>x+w) r=x+w;
            if (b>y+h) b=y+h;
            for (i=0;i<v->visibleCount;++i) {
                vl=l>v->visible[i].left ? l:v->visible[i].left;
                vt=t>v->visible[i].top ? t:v->visible[i].top;
                vr=r<v->visible[i].right ? r:v->visible[i].right;
                vb=b<v->visible[i].bottom ? b:v->visible[i].bottom;
                if (vl>=vr || vt>=vb) continue;
                for (row=vt;row<vb;row+=16) {
                    r_set(&p.clip,vl,row,vr-vl,vb-row>16 ? 16:vb-row);
                    if (GemDrawingBorrow(&c->workstation->grant,vl,row,vr,row+p.clip.g_h,draw,&p)!=DISPLAY_OK) {
                        c->diagnostic=AES_DISPLAY_ERROR; c->busy=0; return 0;
                    }
                }
            }
            if (level<depth && tree[obj].ob_head!=NIL) {
                obj=tree[obj].ob_head; ++level; continue;
            }
        }
        while (obj!=start) {
            next=tree[obj].ob_next;
            if (tree[next].ob_tail!=obj) break;
            obj=next; --level;
        }
        if (obj==start) break;
        obj=tree[obj].ob_next;
    }
    c->busy=0; return 1;
}
WORD objc_find(OBJECT *tree,WORD start,WORD depth,WORD x,WORD y)
{
    return ob_find(tree,start,depth>MAX_DEPTH ? MAX_DEPTH:depth,x,y);
}
WORD objc_offset(OBJECT *tree,WORD obj,WORD *x,WORD *y)
{
    ob_offset(tree,obj,x,y); return 1;
}
WORD objc_change(OBJECT *tree,WORD obj,WORD reserved,WORD x,WORD y,WORD w,WORD h,WORD state,WORD redraw)
{
    (void)reserved;
    tree[obj].ob_state=state;
    return redraw ? objc_draw(tree,obj,0,x,y,w,h):1;
}
WORD form_center(OBJECT *tree,WORD *x,WORD *y,WORD *w,WORD *h)
{
    struct ExecAESContext *c=ExecAESContext();
    if (!c || !c->view || !c->view->shown) return 0;
    *w=tree[0].ob_width; *h=tree[0].ob_height;
    /* Keep the form in the caller's work area, the hosted drawing domain. */
    *x=c->view->work.left+(c->view->work.right-c->view->work.left-*w)/2;
    *y=c->view->work.top+(c->view->work.bottom-c->view->work.top-*h)/2;
    tree[0].ob_x=*x; tree[0].ob_y=*y;
    return 1;
}
static WORD eligible(OBJECT *tree,WORD obj)
{
    WORD at=obj;
    if (!(tree[obj].ob_flags&(SELECTABLE|EDITABLE)) || (tree[obj].ob_state&DISABLED)) return 0;
    while (at!=NIL) {
        if (tree[at].ob_flags&HIDETREE) return 0;
        at=ob_get_par(tree,at);
    }
    return 1;
}
WORD form_button(OBJECT *tree,WORD obj,WORD clicks,WORD *next)
{
    WORD result;
    *next=obj;
    if (!eligible(tree,obj) || (tree[obj].ob_flags&EDITABLE)) return 1;
    result=fm_button(tree,obj,clicks,next);
    *next=obj;
    return result;
}
WORD form_keybd(OBJECT *tree,WORD obj,WORD next,WORD key,WORD *out,WORD *unused)
{
    WORD i,count=1,target=NIL;
    *out=next; *unused=key;
    while (!(tree[count-1].ob_flags&LASTOB)) ++count;
    if ((key&255)==9 || key==0x0f00) {
        i=obj;
        do {
            if (key==0x0f00) i=i ? i-1:count-1;
            else i=i+1==count ? 0:i+1;
            if (eligible(tree,i)) { *out=i; break; }
        } while (i!=obj);
        *unused=0; return 1;
    }
    if ((key&255)==13) {
        for (i=0;i<count;++i) if ((tree[i].ob_flags&DEFAULT) && eligible(tree,i)) { target=i; break; }
    } else if ((key&255)==32 && !(tree[obj].ob_flags&EDITABLE) && eligible(tree,obj)) target=obj;
    if (target!=NIL) {
        *out=target; *unused=0;
        return form_button(tree,target,1,out);
    }
    return 1;
}

BOOL ExecAESObjects(struct ExecAESContext *c,AESPB *pb)
{
    WORD op=pb->control[0],ins,outs=1,*a=pb->int_in,*b=pb->int_out;
    OBJECT *tree;
    switch (op) {
    case 42: ins=6; break;
    case 43: ins=4; break;
    case 44: ins=1; outs=3; break;
    case 46: ins=4; outs=2; break;
    case 47: ins=8; break;
    case 54: ins=0; outs=5; break;
    case 55: ins=3; outs=3; break;
    case 56: ins=2; outs=2; break;
    default: return FALSE;
    }
    b[0]=0;
    if (pb->control[1]!=ins || pb->control[2]!=outs ||
        pb->control[3]!=1 || pb->control[4]!=0) {
        c->diagnostic=AES_MALFORMED; return TRUE;
    }
    tree=(OBJECT *)(ULONG)pb->addr_in[0]; c->diagnostic=AES_OK;
    switch (op) {
    case 42: b[0]=objc_draw(tree,a[0],a[1],a[2],a[3],a[4],a[5]); break;
    case 43: b[0]=objc_find(tree,a[0],a[1],a[2],a[3]); break;
    case 44: b[0]=objc_offset(tree,a[0],&b[1],&b[2]); break;
    case 46: b[1]=a[2]; b[0]=objc_edit(tree,a[0],a[1],&b[1],a[3]); break;
    case 47: b[0]=objc_change(tree,a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7]); break;
    case 54: b[0]=form_center(tree,&b[1],&b[2],&b[3],&b[4]); break;
    case 55: b[0]=form_keybd(tree,a[0],a[2],a[1],&b[1],&b[2]); break;
    case 56: b[0]=form_button(tree,a[0],a[1],&b[1]); break;
    }
    return TRUE;
}
