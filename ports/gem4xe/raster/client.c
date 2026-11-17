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

static WORD surface(struct ExecAESContext *c,const MFDB *m,struct GemRasterSurface *s)
{
    LONG pitch;
    if (!m || !m->fd_addr) { screen(s); return 1; }
    if (m->fd_stand!=0 || m->fd_nplanes!=4) { c->diagnostic=AES_UNSUPPORTED; return 0; }
    pitch=(LONG)m->fd_wdwidth*8;
    if (m->fd_w<=0 || m->fd_h<=0 || pitch<=0 || pitch>65535 || pitch*2<m->fd_w) {
        c->diagnostic=AES_MALFORMED; return 0;
    }
    s->address=m->fd_addr; s->pitch=pitch; s->width=m->fd_w; s->height=m->fd_h;
    return 1;
}

static UWORD copy(struct ExecVDIWorkstation *w,struct GemRasterCopy *p)
{
    struct VbxeCopy *v=&w->copy;
    struct GemRasterRect *r=&p->rect;
    if (p->mode==S_ONLY && !p->source.address && !p->destination.address && ((r->sx^r->dx)&1)==0) {
        v->source.offset=v->destination.offset=0;
        v->source.pitch=v->destination.pitch=320;
        v->source.width=v->destination.width=640;
        v->source.height=v->destination.height=240;
        v->sourceX=r->sx; v->sourceY=r->sy;
        v->destinationX=r->dx; v->destinationY=r->dy;
        v->width=r->width; v->height=r->height;
        return GemDrawingCopyBorrow(&w->grant,v);
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
    if (status!=DISPLAY_OK) { c->diagnostic=AES_DISPLAY_ERROR; return 0; }
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
    if ((UWORD)mode>15) {
        c->diagnostic=AES_UNSUPPORTED; return;
    }
    if (!surface(c,source,&p.source) || !surface(c,destination,&p.destination)) return;
    if (!p.source.address || !p.destination.address) {
        if (!view) { c->diagnostic=AES_IDENTITY; return; }
        if (!view->updates) { c->diagnostic=AES_BUSY; return; }
    }
    p.mode=mode;
    GemRasterNormalize(&p.rect,points);
    l=0; t=0; r=p.destination.width; b=p.destination.height;
    if (!p.destination.address) {
        if (l<view->work.left) l=view->work.left;
        if (t<view->work.top) t=view->work.top;
        if (r>view->work.right) r=view->work.right;
        if (b>view->work.bottom) b=view->work.bottom;
    }
    if (!p.destination.address && w->clipped) {
        if (l<w->clip[0]) l=w->clip[0];
        if (t<w->clip[1]) t=w->clip[1];
        if (r>(LONG)w->clip[2]+1) r=(LONG)w->clip[2]+1;
        if (b>(LONG)w->clip[3]+1) b=(LONG)w->clip[3]+1;
    }
    if (!GemRasterClip(&p.rect,0,0,p.source.width,p.source.height,l,t,r,b)) return;
    if (mode==D_ONLY) return;
    if (mode==S_ONLY && p.source.address==p.destination.address && p.source.pitch==p.destination.pitch &&
        p.rect.sx==p.rect.dx && p.rect.sy==p.rect.dy) return;
    whole=p.rect; client.context=c; client.copy=&p;
    if (p.destination.address) draw(&client,&whole);
    else GemRasterVisible(&whole,view->visible,view->visibleCount,draw,&client);
}
