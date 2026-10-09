/* Synchronous forms run in their caller, using ordinary window ownership. */
#include "aes-form-private.h"
#include "vdi-private.h"
#include <proto/exec.h>

void ExecAESFormExtent(OBJECT *tree,GRECT *r)
{
    WORD border=0;
    if (tree[0].ob_type==G_BOX || tree[0].ob_type==G_IBOX)
        border=(BYTE)(tree[0].ob_spec>>16);
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
    WORD result,*a=pb->int_in;
    if (pb->control[0]!=51) return FALSE;
    if (pb->control[1]!=9 || pb->control[2]!=1 || pb->control[3] || pb->control[4]) {
        c->diagnostic=AES_MALFORMED; pb->int_out[0]=0; return TRUE;
    }
    result=form_dial(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8]);
    pb->int_out[0]=result;
    return TRUE;
}
