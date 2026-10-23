/* SPDX-License-Identifier: MIT
 * Local convenience operations over the public GEM ABI, with no trap bindings.
 */
#include "qed-native.h"
#include <macros.h>
#include <string.h>
/* Kept private to the rebuilt CFLIB interface. */
typedef int (*QedFileSelectCallback)(char *,char *);
int select_file(char *path,char *name,char *mask,char *title,QedFileSelectCallback callback)
{
    WORD button=0;
    size_t directory=strlen(path);
    if(directory+strlen(mask)>=255)return 0;
    strcat(path,*mask?mask:"*");
    if(!fsel_exinput(path,name,&button,title) || button!=FSEL_OK){path[directory]=0;return 0;}
    {
        char *slash=strrchr(path,'/'),*volume=strrchr(path,':');
        if(volume && (!slash || volume>slash))slash=volume;
        if(slash)slash[1]=0;else path[0]=0;
    }
    if(callback){callback(path,name);path[0]=name[0]=0;}
    return 1;
}
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
WORD form_center_grect(OBJECT *t,GRECT *r){return form_center(t,&r->g_x,&r->g_y,&r->g_w,&r->g_h);}
WORD form_dial_grect(WORD f,const GRECT *a,const GRECT *b)
{
    return form_dial(f,a->g_x,a->g_y,a->g_w,a->g_h,b->g_x,b->g_y,b->g_w,b->g_h);
}
WORD objc_draw_grect(OBJECT *t,WORD start,WORD depth,const GRECT *r)
{
    return objc_draw(t,start,depth,r->g_x,r->g_y,r->g_w,r->g_h);
}
WORD objc_change_grect(OBJECT *t,WORD obj,WORD depth,const GRECT *r,WORD state,WORD redraw)
{
    return objc_change(t,obj,depth,r->g_x,r->g_y,r->g_w,r->g_h,state,redraw);
}
