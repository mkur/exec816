/* GEM4XE copy geometry over Exec's caller-local workstation and UPDATE.
 * Donor algorithms/provenance: inputs.json. GPL-2.0-or-later. */
#include "../../../c/calypsi/aes-private.h"
#include "../../../c/calypsi/vdi-private.h"
#include "../adapter/gem-drawing.h"
#include "drawing.h"
#include "visible.h"

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

struct RasterClient { struct ExecAESContext *context; struct GemRasterCopy *copy; };

static int16_t draw(void *opaque,const struct GemRasterRect *r)
{
    struct RasterClient *client=opaque;
    struct ExecAESContext *c=client->context;
    UWORD status;
    client->copy->rect=*r;
    status=copy(c->workstation,client->copy);
    ExecAESChanged(c,r->dx,r->dy,r->dx+r->width,r->dy+r->height);
    if (status!=DISPLAY_OK) { c->request.paintFailed=1; c->diagnostic=AES_DISPLAY_ERROR; return 0; }
    return 1;
}

void ExecGemRasterCopy(struct ExecAESContext *c,WORD mode,const WORD *points,
    const MFDB *source,const MFDB *destination)
{
    struct ExecVDIWorkstation *w=c->workstation;
    struct AESWindowView *view=c->view;
    struct GemRasterCopy p;
    struct GemRasterRect whole;
    struct RasterClient client;
    LONG l,t,r,b;
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
    if (p.rect.sx==p.rect.dx && p.rect.sy==p.rect.dy) return;
    whole=p.rect; client.context=c; client.copy=&p;
    GemRasterVisible(&whole,view->visible,view->visibleCount,draw,&client);
}
