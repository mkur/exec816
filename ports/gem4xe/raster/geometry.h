/* Paired raster clipping adapted from GEM4XE vdi_vro_cpyfm (inputs.json).
 * All coordinate arithmetic is widened before subtraction or addition.
 * GPL-2.0-or-later; retain upstream COPYING. */
#ifndef EXEC_GEM_RASTER_GEOMETRY_H
#define EXEC_GEM_RASTER_GEOMETRY_H
#include <stdint.h>
struct GemRasterRect { int32_t sx,sy,dx,dy,width,height; };

static void GemRasterNormalize(struct GemRasterRect *r,const int16_t *p)
{
    int32_t sx=p[0],sy=p[1],sr=p[2],sb=p[3],dx=p[4],dy=p[5];
    if (sx>sr) { sx=p[2]; sr=p[0]; }
    if (sy>sb) { sy=p[3]; sb=p[1]; }
    if (dx>p[6]) dx=p[6];
    if (dy>p[7]) dy=p[7];
    r->sx=sx; r->sy=sy; r->dx=dx; r->dy=dy;
    r->width=sr-sx+1; r->height=sb-sy+1;
}

/* Bounds are half-open. Both coordinates advance by the same lost span. */
static int16_t GemRasterClip(struct GemRasterRect *r,int32_t sl,int32_t st,
    int32_t sr,int32_t sb,int32_t dl,int32_t dt,int32_t dr,int32_t db)
{
    int32_t loss;
    if (r->dx<dl) { loss=dl-r->dx; r->dx+=loss; r->sx+=loss; r->width-=loss; }
    if (r->dy<dt) { loss=dt-r->dy; r->dy+=loss; r->sy+=loss; r->height-=loss; }
    if (r->dx+r->width>dr) r->width=dr-r->dx;
    if (r->dy+r->height>db) r->height=db-r->dy;
    if (r->sx<sl) { loss=sl-r->sx; r->sx+=loss; r->dx+=loss; r->width-=loss; }
    if (r->sy<st) { loss=st-r->sy; r->sy+=loss; r->dy+=loss; r->height-=loss; }
    if (r->sx+r->width>sr) r->width=sr-r->sx;
    if (r->sy+r->height>sb) r->height=sb-r->sy;
    return r->width>0 && r->height>0;
}
#endif
