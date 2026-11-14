/* SPDX-License-Identifier: MIT
 * Shared rectangle conveniences, extracted from the native QED adapter. */
#include <compat/gem-rect.h>
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
WORD *grect_to_array(const GRECT *r,WORD *xy)
{
    xy[0]=r->g_x;xy[1]=r->g_y;
    xy[2]=r->g_x+r->g_w-1;xy[3]=r->g_y+r->g_h-1;
    return xy;
}
WORD rc_intersect(const GRECT *a,GRECT *b)
{
    WORD x=max(a->g_x,b->g_x),y=max(a->g_y,b->g_y);
    WORD right=min(a->g_x+a->g_w,b->g_x+b->g_w);
    WORD bottom=min(a->g_y+a->g_h,b->g_y+b->g_h);
    b->g_x=x;b->g_y=y;b->g_w=max(0,right-x);b->g_h=max(0,bottom-y);
    return b->g_w>0 && b->g_h>0;
}
void rc_union(const GRECT *a,GRECT *b)
{
    WORD right=max(a->g_x+a->g_w,b->g_x+b->g_w);
    WORD bottom=max(a->g_y+a->g_h,b->g_y+b->g_h);
    b->g_x=min(a->g_x,b->g_x);b->g_y=min(a->g_y,b->g_y);
    b->g_w=right-b->g_x;b->g_h=bottom-b->g_y;
}
WORD wind_create_grect(WORD kind,const GRECT *r){return wind_create(kind,r->g_x,r->g_y,r->g_w,r->g_h);}
WORD wind_open_grect(WORD h,const GRECT *r){return wind_open(h,r->g_x,r->g_y,r->g_w,r->g_h);}
WORD wind_get_grect(WORD h,WORD f,GRECT *r){return wind_get(h,f,&r->g_x,&r->g_y,&r->g_w,&r->g_h);}
WORD wind_set_grect(WORD h,WORD f,const GRECT *r){return wind_set(h,f,r->g_x,r->g_y,r->g_w,r->g_h);}
WORD wind_calc_grect(WORD type,WORD kind,const GRECT *r,GRECT *o)
{
    return wind_calc(type,kind,r->g_x,r->g_y,r->g_w,r->g_h,&o->g_x,&o->g_y,&o->g_w,&o->g_h);
}
