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
/* ICONBLK storage and dimensions belong to the caller. Shared GSX text scratch
 * and the renderer's bitmap page are protected by this callback's grant. */
static void draw_icon(struct ObjectPaint *p)
{
    const ICONBLK *ib=(const ICONBLK *)(ULONG)p->tree[p->object].ob_spec;
    const char *label=(const char *)(ULONG)ib->ib_ptext;
    WORD fg=(ib->ib_char>>12)&15,bg=(ib->ib_char>>8)&15,swap;
    WORD x=p->x+ib->ib_xicon,y=p->y+ib->ib_yicon;
    WORD l=x,t=y,r=x+ib->ib_wicon,b=y+ib->ib_hicon,n,tx;
    GRECT paper;
    const CICON *colour=NULL;
    if (p->tree[p->object].ob_type==G_CICON)
        colour=(const CICON *)(ULONG)((const CICONBLK *)ib)->mainlist;
    while (colour && colour->num_planes!=4) colour=(const CICON *)(ULONG)colour->next_res;
    if (p->tree[p->object].ob_state&SELECTED) { swap=fg;fg=bg;bg=swap; }
    if (l<gl_clip.g_x) l=gl_clip.g_x;
    if (t<gl_clip.g_y) t=gl_clip.g_y;
    if (r>gl_clip.g_x+gl_clip.g_w) r=gl_clip.g_x+gl_clip.g_w;
    if (b>gl_clip.g_y+gl_clip.g_h) b=gl_clip.g_y+gl_clip.g_h;
    if (l<r && t<b) {
        if (colour) {
            WORD selected=(p->tree[p->object].ob_state&SELECTED) && colour->sel_data;
            GemColourIconBitmap((const UWORD *)(ULONG)(selected ? colour->sel_mask:colour->col_mask),
                (const UBYTE *)(ULONG)(selected ? colour->sel_data:colour->col_data),
                ib->ib_wicon,x,y,l,t,r,b);
        } else GemIconBitmap((const UWORD *)(ULONG)ib->ib_pmask,
            (const UWORD *)(ULONG)ib->ib_pdata,ib->ib_wicon,x,y,l,t,r,b,fg,bg);
    }
    if (ib->ib_char&255) {
        intin[0]=ib->ib_char&255;
        WidgetText(x+ib->ib_xchar,y+ib->ib_ychar,intin,1,MD_TRANS,fg);
    }
    if (label && *label) {
        if (p->tree[p->object].ob_type==G_CICON) {
            /* The standard extension stores exactly twelve label bytes. */
            for (n=0;n<12 && label[n];++n) intin[n]=(UBYTE)label[n];
        } else n=expand_string(intin,label);
        if (n>ib->ib_wtext/8) n=ib->ib_wtext/8;
        r_set(&paper,p->x+ib->ib_xtext,p->y+ib->ib_ytext,ib->ib_wtext,ib->ib_htext);
        WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,bg,&paper);
        tx=paper.g_x+(paper.g_w-n*8)/2;
        WidgetText(tx,paper.g_y,intin,n,MD_TRANS,fg);
    }
}
static void draw(void *data)
{
    struct ObjectPaint *p=data;
    gl_clip=p->clip;
    if (p->tree[p->object].ob_type==G_ICON || p->tree[p->object].ob_type==G_CICON) draw_icon(p);
    else if ((p->tree[p->object].ob_flags&EDITABLE) ||
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
    WORD obj=start,level=0,next,border,l,t,r,b,row,rows,vl,vt,vr,vb;
    WORD changed=0,left=0,top=0,right=0,bottom=0,okay=1;
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
            if (tree[obj].ob_type==G_BOX || tree[obj].ob_type==G_IBOX) {
                WORD high=(WORD)(tree[obj].ob_spec>>16);
                BYTE thickness=(BYTE)high;
                border=thickness;
                border=border<0 ? -border:0;
            }
            l=p.x-border; t=p.y-border;
            r=p.x+tree[obj].ob_width+border; b=p.y+tree[obj].ob_height+border;
            /* Choose from the full extent, before damage/visibility clipping.
             * Large objects retain bounded strips even for a short exposure. */
            rows=b-t<=32 ? 32:16;
            if (l<x) l=x;
            if (t<y) t=y;
            if (r>x+w) r=x+w;
            if (b>y+h) b=y+h;
            if (l<r && t<b) {
                if (!changed) { left=l;top=t;right=r;bottom=b;changed=1; }
                else {
                    if (l<left) left=l;
                    if (t<top) top=t;
                    if (r>right) right=r;
                    if (b>bottom) bottom=b;
                }
            }
            for (i=0;i<v->visibleCount;++i) {
                vl=l>v->visible[i].left ? l:v->visible[i].left;
                vt=t>v->visible[i].top ? t:v->visible[i].top;
                vr=r<v->visible[i].right ? r:v->visible[i].right;
                vb=b<v->visible[i].bottom ? b:v->visible[i].bottom;
                if (vl>=vr || vt>=vb) continue;
                for (row=vt;row<vb;row+=rows) {
                    r_set(&p.clip,vl,row,vr-vl,vb-row>rows ? rows:vb-row);
                    if (GemDrawingBorrow(&c->workstation->grant,vl,row,vr,row+p.clip.g_h,draw,&p)!=DISPLAY_OK) {
                        c->request.paintFailed=1;
                        c->diagnostic=AES_DISPLAY_ERROR;okay=0;goto finished;
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
finished:
    if (changed) ExecAESChanged(c,left,top,right,bottom);
    c->busy=0; return okay;
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
