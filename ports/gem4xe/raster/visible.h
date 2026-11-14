/* Ordered visible fragments over GEM4XE paired clipping. GPL-2.0-or-later.
 * AESRect is the current published half-open rectangle, defined by the caller. */
#ifndef EXEC_GEM_RASTER_VISIBLE_H
#define EXEC_GEM_RASTER_VISIBLE_H
#include "geometry.h"
typedef int16_t (*GemRasterVisit)(void *,const struct GemRasterRect *);

static int16_t GemRasterVisible(const struct GemRasterRect *whole,
    const struct AESRect *visible,uint16_t count,GemRasterVisit visit,void *context)
{
    struct GemRasterRect p,chosen;
    int32_t y,next,x,edge,top,bottom;
    uint16_t i,hits=0,found,backY=whole->dy>whole->sy,backX=whole->dx>whole->sx;
    for (i=0;i<count;++i) {
        p=*whole;
        if (!GemRasterClip(&p,0,0,INT32_MAX,INT32_MAX,visible[i].left,
            visible[i].top,visible[i].right,visible[i].bottom)) continue;
        chosen=p;
        if (++hits>1) break;
    }
    if (!hits) return 1;
    if (hits==1) return visit(context,&chosen);
    y=backY ? whole->dy+whole->height:whole->dy;
    while (backY ? y>whole->dy:y<whole->dy+whole->height) {
        next=backY ? whole->dy:whole->dy+whole->height;
        for (i=0;i<count;++i) {
            edge=visible[i].top;
            if (backY ? edge<y && edge>next:edge>y && edge<next) next=edge;
            edge=visible[i].bottom;
            if (backY ? edge<y && edge>next:edge>y && edge<next) next=edge;
        }
        top=backY ? next:y; bottom=backY ? y:next;
        x=backX ? whole->dx+whole->width:whole->dx;
        for (;;) {
            found=0;
            for (i=0;i<count;++i) {
                if (visible[i].top>top || visible[i].bottom<bottom) continue;
                p=*whole;
                if (!GemRasterClip(&p,0,0,INT32_MAX,INT32_MAX,visible[i].left,
                    top,visible[i].right,bottom)) continue;
                if (backX ? p.dx+p.width>x:p.dx<x) continue;
                if (!found || (backX ? p.dx>chosen.dx:p.dx<chosen.dx)) { chosen=p; found=1; }
            }
            if (!found) break;
            if (!visit(context,&chosen)) return 0;
            x=backX ? chosen.dx:chosen.dx+chosen.width;
        }
        y=next;
    }
    return 1;
}
#endif
