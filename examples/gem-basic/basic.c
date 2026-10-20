/* SPDX-License-Identifier: MIT */
#include "basic.h"
#include <exec816/aes.h>

static WORD paint(struct BasicApp *a,WORD *damage)
{
    WORD x,y,w,h,clip[4],okay=1;
    if (!ExecAESBeginUpdate(a->window)) return 0;
    if (!wind_get(a->window,WF_WXYWH,&a->work[0],&a->work[1],&a->work[2],&a->work[3]) ||
        !wind_get(a->window,WF_FIRSTXYWH,&x,&y,&w,&h)) okay=0;
    while (okay && w && h) {
        clip[0]=x>damage[0] ? x:damage[0];
        clip[1]=y>damage[1] ? y:damage[1];
        clip[2]=x+w<damage[0]+damage[2] ? x+w-1:damage[0]+damage[2]-1;
        clip[3]=y+h<damage[1]+damage[3] ? y+h-1:damage[1]+damage[3]-1;
        if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
            vs_clip(a->vdi,1,clip);vsf_color(a->vdi,0);v_bar(a->vdi,clip);
            vst_color(a->vdi,1);v_gtext(a->vdi,a->work[0]+4,a->work[1]+10,"FastBasic");
            okay=ExecAESDiagnostic()==AES_OK;
        }
        if (!wind_get(a->window,WF_NEXTXYWH,&x,&y,&w,&h)) okay=0;
    }
    if (okay) okay=ExecAESPainted(a->window,damage[0],damage[1],damage[2],damage[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++a->paints;
    return okay;
}

WORD BasicOpen(struct BasicApp *a)
{
    WORD i,bw,bh;
    a->window=-1;a->id=appl_init();
    if (a->id<0) return 0;
    a->vdi=graf_handle(&a->cellw,&a->cellh,&bw,&bh);
    for (i=0;i<10;++i) a->input[i]=1;
    a->input[10]=2;v_opnvwk(a->input,&a->vdi,a->output);
    if (!a->vdi) return 0;
    a->window=wind_create(NAME|CLOSER|MOVER|SIZER,0,0,480,192);
    if (a->window<0 || !wind_set_str(a->window,WF_NAME,"FastBasic") ||
        !wind_set(a->window,AES_WF_EXEC_PRESERVE,1,0,0,0) ||
        !wind_open(a->window,48,32,480,192)) return 0;
    a->opened=a->ready=1;return 1;
}

WORD BasicEvent(struct BasicApp *a,WORD *quit)
{
    WORD *m=a->message;
    if (m[3]!=a->window) return 1;
    switch (m[0]) {
    case WM_CLOSED:*quit=1;break;
    case WM_TOPPED:return wind_set(a->window,WF_TOP,0,0,0,0);
    case WM_SIZED:
        if (m[6]<208) m[6]=208;
        if (m[7]<128) m[7]=128;
        /* Fall through. Geometry changes never retain a visible iterator. */
    case WM_MOVED:return wind_set(a->window,WF_CXYWH,m[4],m[5],m[6],m[7]);
    case WM_REDRAW:return paint(a,&m[4]);
    }
    return 1;
}

WORD BasicClose(struct BasicApp *a)
{
    /* appl_exit retires menus, workstation and windows before model storage
     * can disappear. The shared Process wrapper detaches the endpoint. */
    a->ready=0;
    return appl_exit();
}

WORD BasicRun(struct BasicApp *a)
{
    WORD quit=0,result=20,mx,my,buttons,mods,key,clicks,events;
    if (BasicOpen(a)) {
        result=0;
        while (!quit && !result) {
            events=evnt_multi(MU_MESAG,1,1,1,0,0,0,0,0,0,0,0,0,0,a->message,
                0,0,&mx,&my,&buttons,&mods,&key,&clicks);
            if (!events || !BasicEvent(a,&quit)) result=20;
        }
    }
    if (!BasicClose(a)) result=20;
    return result;
}
