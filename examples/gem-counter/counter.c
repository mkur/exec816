/* SPDX-License-Identifier: MIT */
#include "counter.h"

static void label(struct Counter *app)
{
    ULONG value=app->count;
    WORD i;
    const char *prefix="Count: ";
    for (i=0;i<7;++i) app->label[i]=prefix[i];
    for (i=12;i>=7;--i) {
        app->label[i]='0'+value%10;
        value/=10;
    }
    app->label[13]=0;
}

/* WM_REDRAW and timer changes share one ordinary GEM redraw loop. Damage and
 * enumeration use x/y/w/h; only the VDI boundary uses inclusive corners. */
static WORD redraw(struct Counter *app,const WORD *damage)
{
    WORD x,y,w,h,l,t,r,b,clip[4],okay=1;
    const struct CounterConfig *config=app->config;
    if (!wind_update(BEG_UPDATE)) return 0;
    if (!wind_get(app->window,WF_WXYWH,&app->work[0],&app->work[1],
                  &app->work[2],&app->work[3])) okay=0;
    if (okay) okay=wind_get(app->window,WF_FIRSTXYWH,&x,&y,&w,&h);
    label(app);
    while (okay && w>0 && h>0) {
        l=x>damage[0] ? x:damage[0]; t=y>damage[1] ? y:damage[1];
        r=x+w<damage[0]+damage[2] ? x+w:damage[0]+damage[2];
        b=y+h<damage[1]+damage[3] ? y+h:damage[1]+damage[3];
        if (l<r && t<b) {
            clip[0]=l; clip[1]=t; clip[2]=r-1; clip[3]=b-1;
            vs_clip(app->vdi,1,clip);
            vsf_color(app->vdi,config->paper);
            v_bar(app->vdi,clip);
            vst_color(app->vdi,config->ink);
            v_gtext(app->vdi,app->work[0]+8,app->work[1]+14,"GEM counter");
            v_gtext(app->vdi,app->work[0]+8,app->work[1]+30,app->label);
        }
        okay=wind_get(app->window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++app->paints;
    return okay;
}

WORD CounterRun(struct Counter *app)
{
    WORD i,cw,ch,bw,bh,events,mx,my,mb,ks,kr,br,damage[4],quit=0,result=1;
    const struct CounterConfig *config=app->config;
    app->id=appl_init(); app->window=-1;
    if (app->id<0) return 1;
    app->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) app->input[i]=1;
    app->input[6]=config->ink; app->input[9]=config->paper;
    app->input[10]=2;
    v_opnvwk(app->input,&app->vdi,app->output);
    if (!app->vdi) goto finish;
    app->window=wind_create(NAME|CLOSER|MOVER,0,0,config->width,config->height);
    if (app->window<0) goto finish;
    if (!wind_set_str(app->window,WF_NAME,config->title)) goto finish;
    if (!wind_open(app->window,config->x,config->y,config->width,config->height)) goto finish;
    app->opened=1; app->ready=1;
    result=0;
    while (!quit) {
        events=evnt_multi(MU_MESAG|MU_TIMER,0,0,0,
            0,0,0,0,0,0,0,0,0,0,app->message,1000,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) { result=2; break; }
        if (events & MU_TIMER) {
            if (++app->count==1000000UL) app->count=0;
        }
        /* Handle both ready bits, including a timer beside a close/redraw. */
        if ((events & MU_MESAG) && app->message[3]==app->window) {
            switch (app->message[0]) {
            case WM_CLOSED: quit=1; break;
            case WM_TOPPED:
                if (!wind_set(app->window,WF_TOP,0,0,0,0)) result=2;
                break;
            case WM_MOVED:
                if (!wind_set(app->window,WF_CXYWH,app->message[4],app->message[5],
                              app->message[6],app->message[7])) result=2;
                break;
            case WM_REDRAW:
                if (!redraw(app,&app->message[4])) result=2;
                break;
            }
        }
        if (!quit && (events & MU_TIMER)) {
            if (!wind_get(app->window,WF_WXYWH,&damage[0],&damage[1],&damage[2],&damage[3])) result=2;
            else {
                damage[0]+=8; damage[1]+=24; damage[2]=104; damage[3]=8;
                if (!redraw(app,damage)) result=2;
            }
        }
        if (result) break;
    }
finish:
    app->ready=0;
    if (app->opened && wind_close(app->window)) app->opened=0;
    if (app->window>0 && !app->opened && wind_delete(app->window)) app->window=-1;
    if (app->vdi) { v_clsvwk(app->vdi); app->vdi=0; }
    if (!appl_exit()) result=3;
    app->id=0;
    return result;
}
