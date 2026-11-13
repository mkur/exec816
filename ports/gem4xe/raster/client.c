/* GEM4XE copy geometry over Exec's caller-local workstation and UPDATE.
 * Donor algorithms/provenance: inputs.json. GPL-2.0-or-later. */
#include "../../../c/calypsi/aes-private.h"
#include "../../../c/calypsi/vdi-private.h"
#include "../adapter/gem-drawing.h"
#include "drawing.h"

static void screen(struct GemRasterSurface *s)
{
    s->address=NULL; s->pitch=320; s->width=640; s->height=240;
}

static UWORD copy(struct ExecVDIWorkstation *w,struct GemRasterCopy *p)
{
    struct VbxeCopy *v=&w->copy;
    struct GemRasterRect *r=&p->rect;
    if (((r->sx^r->dx)&1)==0) {
        v->source.offset=v->destination.offset=0;
        v->source.pitch=v->destination.pitch=320;
        v->source.width=v->destination.width=640;
        v->source.height=v->destination.height=240;
        v->sourceX=r->sx; v->sourceY=r->sy;
        v->destinationX=r->dx; v->destinationY=r->dy;
        v->width=r->width; v->height=r->height;
        return GemDrawingCopyBorrow(&w->grant,v,w->copyEdges);
    }
    return GemDrawingRasterBorrow(&w->grant,p,w->copyEdges);
}

void ExecGemRasterCopy(struct ExecAESContext *c,WORD mode,const WORD *points,
    const MFDB *source,const MFDB *destination)
{
    struct ExecVDIWorkstation *w=c->workstation;
    struct AESWindowView *view=c->view;
    struct GemRasterCopy p;
    struct GemRasterRect candidate,chosen;
    LONG l,t,r,b;
    UWORD i,count=0,status;
    if (mode!=S_ONLY || (source && source->fd_addr) || (destination && destination->fd_addr)) {
        c->diagnostic=AES_UNSUPPORTED; return;
    }
    if (!view) { c->diagnostic=AES_IDENTITY; return; }
    if (!view->updates) { c->diagnostic=AES_BUSY; return; }
    p.mode=mode; screen(&p.source); screen(&p.destination);
    GemRasterNormalize(&p.rect,points);
    l=view->work.left; t=view->work.top; r=view->work.right; b=view->work.bottom;
    if (w->clipped) {
        if (l<w->clip[0]) l=w->clip[0];
        if (t<w->clip[1]) t=w->clip[1];
        if (r>(LONG)w->clip[2]+1) r=(LONG)w->clip[2]+1;
        if (b>(LONG)w->clip[3]+1) b=(LONG)w->clip[3]+1;
    }
    if (!GemRasterClip(&p.rect,0,0,640,240,l,t,r,b)) return;
    for (i=0;i<view->visibleCount;++i) {
        candidate=p.rect;
        if (!GemRasterClip(&candidate,0,0,640,240,view->visible[i].left,
            view->visible[i].top,view->visible[i].right,view->visible[i].bottom)) continue;
        chosen=candidate;
        if (++count>1) { c->diagnostic=AES_UNSUPPORTED; return; }
    }
    if (!count) return;
    p.rect=chosen;
    if (chosen.sx==chosen.dx && chosen.sy==chosen.dy) return;
    status=copy(w,&p);
    ExecAESChanged(c,chosen.dx,chosen.dy,chosen.dx+chosen.width,chosen.dy+chosen.height);
    if (status!=DISPLAY_OK) { c->request.paintFailed=1; c->diagnostic=AES_DISPLAY_ERROR; }
}
