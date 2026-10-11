/* Synchronous forms run in their caller, using ordinary window ownership. */
#include "aes-form-private.h"
#include "aes-alert-private.h"
#include "aes-fsel-private.h"
#include "vdi-private.h"
#include <proto/exec.h>
extern WORD App_ob_get_par(OBJECT *,WORD);

void ExecAESFormExtent(OBJECT *tree,GRECT *r)
{
    WORD border=0;
    if (tree[0].ob_type==G_BOX || tree[0].ob_type==G_IBOX) {
        WORD high=(WORD)(tree[0].ob_spec>>16);
        BYTE thickness=(BYTE)high;
        border=thickness;
    }
    if (border>0) border=0;
    r->g_x=tree[0].ob_x+border; r->g_y=tree[0].ob_y+border;
    r->g_w=tree[0].ob_width-2*border; r->g_h=tree[0].ob_height-2*border;
}

WORD form_center(OBJECT *tree,WORD *x,WORD *y,WORD *w,WORD *h)
{
    struct ExecAESContext *c=ExecAESContext();
    GRECT extent;
    WORD left=8,top=32,width=624,height=200,dx,dy;
    if (!c || !c->identity) return 0;
    c->diagnostic=AES_OK;
    if (c->view && c->view->handle) {
        if (!c->view->shown) { c->diagnostic=AES_BUSY; return 0; }
        left=c->view->work.left; top=c->view->work.top;
        width=c->view->work.right-left; height=c->view->work.bottom-top;
    }
    ExecAESFormExtent(tree,&extent);
    if (extent.g_w>width || extent.g_h>height || extent.g_w<=0 || extent.g_h<=0) {
        c->diagnostic=AES_RESOURCE; return 0;
    }
    *x=left+(width-extent.g_w)/2; *y=top+(height-extent.g_h)/2;
    *w=extent.g_w; *h=extent.g_h;
    dx=tree[0].ob_x-extent.g_x; dy=tree[0].ob_y-extent.g_y;
    tree[0].ob_x=*x+dx; tree[0].ob_y=*y+dy;
    return 1;
}

/* No borrowed window or workstation is retired here. Keep the session if an
 * owned resource cannot retire; appl_exit can retry the same cleanup. */
BOOL ExecAESFormFinish(struct ExecAESContext *c)
{
    struct ExecAESForm *f=c->form;
    UWORD saved=c->diagnostic;
    if (!f) return TRUE;
    if (f->running || c->updateDepth || c->mouseDepth) {
        c->diagnostic=AES_BUSY; return FALSE;
    }
    if (f->ownWindow) {
        if (c->view && c->view->shown && !wind_close(f->window)) return FALSE;
        if (!wind_delete(f->window)) return FALSE;
        f->ownWindow=0;
    } else if (f->ready && c->view && c->view->shown) {
        c->repair=c->view->work;
        c->repairWindow=c->view->handle;
        c->repairEpoch=c->endpoint->guiEpoch;
    }
    if (f->ownView && c->view && !c->view->handle) {
        FreeMem(c->view,sizeof(*c->view)); c->view=NULL; c->request.view=NULL;
    }
    if (f->ownWorkstation) {
        if (!ExecVDIClose(c)) return FALSE;
        f->ownWorkstation=0;
    }
    if (f->tree) {
        f->tree[0].ob_x=f->originalX; f->tree[0].ob_y=f->originalY;
    }
    if (f->alert) FreeMem(f->alert,sizeof(*f->alert));
    if (f->fileSelector) ExecAESFileFree(f->fileSelector);
    FreeMem(f,sizeof(*f)); c->form=NULL;
    c->diagnostic=saved;
    return TRUE;
}

WORD ExecAESFormBegin(struct ExecAESContext *c,const GRECT *area,const char *title)
{
    struct ExecAESForm *f;
    WORD x,y,w,h,handle=1,i;
    if (!c->identity) { c->diagnostic=AES_IDENTITY; return 0; }
    if (c->busy || c->form || c->editTree || c->updateDepth || c->mouseDepth ||
        (c->view && c->view->handle && !c->view->shown)) {
        c->diagnostic=AES_BUSY; return 0;
    }
    c->diagnostic=AES_RESOURCE;
    /* Widen the extent calculation once, before allocating or painting. */
    if (area->g_w<=0 || area->g_h<=0) return 0;
    if (c->view && c->view->shown) {
        if (area->g_x<c->view->work.left || area->g_y<c->view->work.top ||
            (LONG)area->g_x+area->g_w>c->view->work.right ||
            (LONG)area->g_y+area->g_h>c->view->work.bottom) return 0;
    } else if (area->g_x<8 || area->g_y<32 ||
        (LONG)area->g_x+area->g_w>632 || (LONG)area->g_y+area->g_h>232) return 0;
    f=AllocMem(sizeof(*f),MEMF_PUBLIC|MEMF_CLEAR);
    if (!f) return 0;
    c->form=f; f->area=*area;
    if (!c->view || !c->view->handle) {
        if (!wind_calc(WC_BORDER,NAME|CLOSER|MOVER,area->g_x,area->g_y,
                       area->g_w,area->g_h,&x,&y,&w,&h)) goto failure;
        if (w<32) w=32;
        if (h<32) h=32;
        f->ownView=c->view==NULL;
        f->window=wind_create(NAME|CLOSER|MOVER,x,y,w,h);
        if (f->window<=0) goto failure;
        f->ownWindow=1;
        if (!wind_set_str(f->window,WF_NAME,title) ||
            !wind_open(f->window,x,y,w,h)) goto failure;
    } else f->window=c->view->handle;
    if (!c->workstation) {
        for (i=0;i<10;++i) f->workIn[i]=1;
        f->workIn[10]=2;
        v_opnvwk(f->workIn,&handle,f->workOut);
        if (!handle) goto failure;
        f->ownWorkstation=1;
    }
    f->ready=1; c->diagnostic=AES_OK;
    return 1;
failure:
    ExecAESFormFinish(c);
    return 0;
}

WORD form_dial(WORD type,WORD x1,WORD y1,WORD w1,WORD h1,
               WORD x2,WORD y2,WORD w2,WORD h2)
{
    struct ExecAESContext *c=ExecAESContext();
    GRECT area={x2,y2,w2,h2};
    (void)x1; (void)y1; (void)w1; (void)h1;
    if (!c) return 0;
    if (c->busy) { c->diagnostic=AES_BUSY; return 0; }
    c->diagnostic=AES_OK;
    switch (type) {
    case FMD_START: return ExecAESFormBegin(c,&area,"Dialog");
    case FMD_FINISH: return ExecAESFormFinish(c);
    case FMD_GROW: case FMD_SHRINK:
        if (c->form && !c->form->running) return 1;
        c->diagnostic=AES_BUSY; return 0;
    default: c->diagnostic=AES_UNSUPPORTED; return 0;
    }
}

BOOL ExecAESForms(struct ExecAESContext *c,AESPB *pb)
{
    WORD result,*a=pb->int_in,op=pb->control[0];
    if (op<50 || op>52) return FALSE;
    if (pb->control[1]!=(op==51 ? 9:1) || pb->control[2]!=1 ||
        pb->control[3]!=(op==51 ? 0:1) || pb->control[4]) {
        c->diagnostic=AES_MALFORMED; pb->int_out[0]=op==50 ? -1:0; return TRUE;
    }
    if (op==50) result=form_do((OBJECT *)(ULONG)pb->addr_in[0],a[0]);
    else if (op==52) result=form_alert(a[0],(const char *)(ULONG)pb->addr_in[0]);
    else result=form_dial(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8]);
    pb->int_out[0]=result;
    return TRUE;
}

static WORD eligible(OBJECT *tree,WORD object)
{
    WORD at=object;
    if (object<=0 || !(tree[object].ob_flags&(SELECTABLE|EDITABLE)) ||
        (tree[object].ob_state&DISABLED)) return 0;
    while (at!=NIL) {
        if (tree[at].ob_flags&HIDETREE) return 0;
        at=App_ob_get_par(tree,at);
    }
    return 1;
}

static WORD draw_object(struct ExecAESContext *c,OBJECT *tree,WORD object,WORD depth)
{
    struct AESRect *r=&c->view->work;
    return objc_draw(tree,object,depth,r->left,r->top,r->right-r->left,r->bottom-r->top);
}

/* Repaint changed controls only. The focus underline belongs to the dialog,
 * never to the caller's OBJECT states or the presenter's model. */
WORD ExecAESFormPaint(struct ExecAESContext *c,WORD full)
{
    struct ExecAESForm *f=c->form;
    OBJECT *o;
    WORD i,okay=1;
    UWORD status;
    if (!wind_update(BEG_UPDATE)) return 0;
    if (full) {
        f->paper.ob_next=f->paper.ob_head=f->paper.ob_tail=NIL;
        f->paper.ob_type=G_BOX; f->paper.ob_flags=LASTOB; f->paper.ob_spec=0x1170;
        f->paper.ob_x=c->view->work.left; f->paper.ob_y=c->view->work.top;
        f->paper.ob_width=c->view->work.right-f->paper.ob_x;
        f->paper.ob_height=c->view->work.bottom-f->paper.ob_y;
        okay=draw_object(c,&f->paper,0,0) && draw_object(c,f->tree,0,MAX_DEPTH);
        if (okay && f->alert) okay=ExecAESAlertPaint(c);
    } else for (i=1;i<f->count && okay;++i)
        if (f->saved[i]!=f->tree[i].ob_state ||
            (f->focus!=f->oldFocus && (i==f->focus || i==f->oldFocus)))
            okay=draw_object(c,f->tree,i,0);
    if (okay && f->focus>0 && !(f->tree[f->focus].ob_flags&EDITABLE)) {
        o=&f->tree[f->focus];
        f->focusLine.ob_next=f->focusLine.ob_head=f->focusLine.ob_tail=NIL;
        f->focusLine.ob_type=G_BOX; f->focusLine.ob_flags=LASTOB;
        f->focusLine.ob_spec=(o->ob_state&SELECTED) ? 0x1170:0x1171;
        objc_offset(f->tree,f->focus,&f->focusLine.ob_x,&f->focusLine.ob_y);
        f->focusLine.ob_x+=3; f->focusLine.ob_y+=o->ob_height-3;
        f->focusLine.ob_width=o->ob_width-6; f->focusLine.ob_height=1;
        if (f->focusLine.ob_width>0) okay=draw_object(c,&f->focusLine,0,0);
    }
    status=c->diagnostic;
    if (!wind_update(END_UPDATE)) return 0;
    c->diagnostic=status;
    return okay;
}

/* Move the existing one-field editor without retaining UPDATE in a wait. */
WORD ExecAESFormFocus(struct ExecAESContext *c,WORD focus)
{
    struct ExecAESForm *f=c->form;
    if (f->edit!=NIL && f->edit!=focus) {
        if (!objc_edit(f->tree,f->edit,0,&f->index,ED_END)) return 0;
        f->edit=NIL;
    }
    f->focus=focus;
    if (focus>0 && (f->tree[focus].ob_flags&EDITABLE) && f->edit!=focus) {
        f->edit=focus;
        if (!objc_edit(f->tree,focus,0,&f->index,ED_INIT)) return 0;
    }
    return 1;
}

void ExecAESFormCancelPress(struct ExecAESForm *f)
{
    if (f->armed!=NIL) f->tree[f->armed].ob_state=f->pressedState;
    f->armed=NIL;
}

/* Return 1 for handled GUI policy, 0 for dismissal/interruption, -1 for a
 * failed operation. Ordinary WM-shaped application messages stay opaque. */
WORD ExecAESFormMessage(struct ExecAESContext *c)
{
    struct ExecAESForm *f=c->form;
    WORD i,x,y;
    if (c->messageEpoch && f->message[3]==f->window) {
        switch (f->message[0]) {
        case WM_REDRAW: return ExecAESFormPaint(c,1) ? 1:-1;
        case WM_TOPPED:
            return wind_set(f->window,WF_TOP,0,0,0,0) ? 1:-1;
        case WM_CLOSED:
            if (f->ownWindow) { c->diagnostic=AES_OK; return 0; }
            break;
        case WM_MOVED:
            if (!f->ownWindow) break;
            ExecAESFormCancelPress(f); f->down=1;
            x=c->view->work.left; y=c->view->work.top;
            if (!wind_set(f->window,WF_CURRXYWH,f->message[4],f->message[5],
                          f->message[6],f->message[7])) return -1;
            f->tree[0].ob_x+=c->view->work.left-x;
            f->tree[0].ob_y+=c->view->work.top-y;
            return ExecAESFormPaint(c,1) ? 1:-1;
        }
    }
    for (i=0;i<8;++i) c->deferredMessage[i]=f->message[i];
    c->deferredEpoch=c->messageEpoch; c->deferredMenuEpoch=c->messageMenuEpoch;
    c->messagePending=1; c->diagnostic=AES_PENDING;
    return 0;
}

WORD ExecAESFormRun(struct ExecAESContext *c,WORD start)
{
    struct ExecAESForm *f=c->form;
    WORD i,events,hit,next,unused,result=-1,proceed,step;
    UWORD status;
    f->count=1;
    while (!(f->tree[f->count-1].ob_flags&LASTOB)) ++f->count;
    f->running=1; f->armed=f->edit=NIL; f->focus=NIL;
    f->down=1; /* Ignore entry's held sequence before accepting a fresh press. */
    if (start) f->focus=start;
    else {
        for (i=1;i<f->count;++i)
            if (eligible(f->tree,i) && (f->tree[i].ob_flags&EDITABLE)) { f->focus=i; break; }
        if (f->focus==NIL) for (i=1;i<f->count;++i)
            if (eligible(f->tree,i)) { f->focus=i; break; }
    }
    if (!ExecAESFormPaint(c,1) || !ExecAESFormFocus(c,f->focus)) goto finish;
    for (;;) {
        f->oldFocus=f->focus;
        for (i=0;i<f->count;++i) f->saved[i]=f->tree[i].ob_state;
        c->intin[1]=1; c->intin[2]=1; c->intin[3]=f->down ? 0:1;
        events=ExecAESEvents(c,MU_KEYBD|MU_BUTTON|MU_MESAG,0,f->message);
        if (!events) {
            if (c->diagnostic!=AES_INPUT_LOST) break;
            ExecAESFormCancelPress(f); f->down=1;
            if (!ExecAESFormPaint(c,0)) break;
            continue;
        }
        f->mx=c->intout[1]; f->my=c->intout[2];
        f->buttons=c->intout[3]; f->key=c->intout[5];
        if ((events&MU_MESAG) && ExecAESFormMessage(c)!=1) break;
        if (events&MU_BUTTON) {
            hit=objc_find(f->tree,0,MAX_DEPTH,f->mx,f->my);
            if (f->buttons&1) {
                f->down=1;
                if (eligible(f->tree,hit)) {
                    f->armed=hit; f->pressedState=f->tree[hit].ob_state;
                    if (!(f->tree[hit].ob_flags&EDITABLE)) f->tree[hit].ob_state^=SELECTED;
                }
            } else {
                f->down=0; next=f->armed; ExecAESFormCancelPress(f);
                if (hit==next && eligible(f->tree,hit)) {
                    proceed=form_button(f->tree,hit,1,&next);
                    if (!ExecAESFormFocus(c,hit)) break;
                    if (!proceed) { result=hit; break; }
                }
            }
        }
        if (events&MU_KEYBD) {
            if (f->down) {
                if ((f->key&255)==27) ExecAESFormCancelPress(f);
            } else if (f->focus!=NIL) {
                next=f->focus;
                if (f->key==0x4800 || f->key==0x5000) {
                    step=f->key==0x4800 ? -1:1; i=f->focus;
                    do {
                        i+=step; if (i<1) i=f->count-1; if (i>=f->count) i=1;
                        if (eligible(f->tree,i) && (f->tree[i].ob_flags&EDITABLE)) { next=i; break; }
                    } while (i!=f->focus);
                    if (!ExecAESFormFocus(c,next)) break;
                } else {
                    proceed=form_keybd(f->tree,f->focus,f->focus,f->key,&next,&unused);
                    if (!ExecAESFormFocus(c,next)) break;
                    if (!proceed) { result=next; break; }
                    if (unused && f->edit!=NIL &&
                        !objc_edit(f->tree,f->edit,unused,&f->index,ED_CHAR)) break;
                }
            }
        }
        if (!ExecAESFormPaint(c,0)) break;
    }
finish:
    status=c->diagnostic;
    ExecAESFormCancelPress(f);
    if (f->edit!=NIL && !objc_edit(f->tree,f->edit,0,&f->index,ED_END)) {
        result=-1; status=c->diagnostic;
    }
    f->edit=NIL;
    if (result>=0) f->tree[result].ob_state|=SELECTED;
    /* Repaint old focus/press and the returned EXIT without an underline. */
    for (i=1;i<f->count;++i)
        if (i==f->oldFocus || i==f->focus) f->saved[i]=~f->tree[i].ob_state;
    f->oldFocus=f->focus; f->focus=NIL;
    if (!ExecAESFormPaint(c,0)) { result=-1; status=c->diagnostic; }
    f->running=0; c->diagnostic=status;
    return result;
}

WORD form_do(OBJECT *tree,WORD start)
{
    struct ExecAESContext *c=ExecAESContext();
    GRECT area;
    WORD implicit,originalX=tree[0].ob_x,originalY=tree[0].ob_y,result;
    if (!c) return -1;
    if (c->busy || c->updateDepth || c->mouseDepth || c->editTree ||
        (c->form && (c->form->running || (c->form->tree && c->form->tree!=tree)))) {
        c->diagnostic=AES_BUSY; return -1;
    }
    implicit=c->form==NULL;
    if (implicit) {
        if ((!c->view || !c->view->handle) &&
            !form_center(tree,&area.g_x,&area.g_y,&area.g_w,&area.g_h)) return -1;
        ExecAESFormExtent(tree,&area);
        if (!ExecAESFormBegin(c,&area,"Dialog")) {
            tree[0].ob_x=originalX; tree[0].ob_y=originalY;
            return -1;
        }
    } else {
        ExecAESFormExtent(tree,&area);
        if (area.g_x<c->view->work.left || area.g_y<c->view->work.top ||
            (LONG)area.g_x+area.g_w>c->view->work.right ||
            (LONG)area.g_y+area.g_h>c->view->work.bottom) {
            c->diagnostic=AES_RESOURCE; return -1;
        }
    }
    if (!c->form->tree) {
        c->form->tree=tree;
        c->form->originalX=originalX; c->form->originalY=originalY;
    }
    c->diagnostic=AES_OK;
    result=ExecAESFormRun(c,start);
    if (implicit && !ExecAESFormFinish(c)) return -1;
    return result;
}
