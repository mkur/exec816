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
