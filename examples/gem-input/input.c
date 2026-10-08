/* SPDX-License-Identifier: MIT */
#include "input.h"

#define KEY_CHANGED 1
#define BUTTON_CHANGED 2
#define TIMER_CHANGED 4

static WORD inside(struct InputApp *app,WORD x,WORD y)
{
    return x>=app->work[0]+8 && x<app->work[0]+136 &&
           y>=app->work[1]+48 && y<app->work[1]+72;
}

static void key_label(struct InputApp *app,UWORD key)
{
    static const char hex[]="0123456789ABCDEF";
    WORD i;
    for (i=8;i>=5;--i) { app->key[i]=hex[key&15]; key>>=4; }
}

static void activate(struct InputApp *app)
{
    WORD i;
    ++app->activations;
    for (i=12;i>=8;--i) {
        if (app->clicks[i]!='9') { ++app->clicks[i]; break; }
        app->clicks[i]='0';
    }
}

/* The normal GEM visible-rectangle loop owns UPDATE only while drawing. The
 * control stays highlighted until release, even when the pointer leaves it. */
static WORD redraw(struct InputApp *app,const WORD *damage)
{
    WORD x,y,w,h,l,t,r,b,clip[4],box[4],okay=1;
    const struct InputConfig *config=app->config;
    if (!wind_update(BEG_UPDATE)) return 0;
    if (!wind_get(app->window,WF_WXYWH,&app->work[0],&app->work[1],
                  &app->work[2],&app->work[3])) okay=0;
    if (okay) okay=wind_get(app->window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w>0 && h>0) {
        l=x>damage[0] ? x:damage[0]; t=y>damage[1] ? y:damage[1];
        r=x+w<damage[0]+damage[2] ? x+w:damage[0]+damage[2];
        b=y+h<damage[1]+damage[3] ? y+h:damage[1]+damage[3];
        if (l<r && t<b) {
            clip[0]=l; clip[1]=t; clip[2]=r-1; clip[3]=b-1;
            vs_clip(app->vdi,1,clip);
            vsf_color(app->vdi,config->paper); v_bar(app->vdi,clip);
            vst_color(app->vdi,config->ink);
            if (t<app->work[1]+48) {
                v_gtext(app->vdi,app->work[0]+8,app->work[1]+14,"GEM input");
                v_gtext(app->vdi,app->work[0]+8,app->work[1]+30,app->key);
                v_gtext(app->vdi,app->work[0]+8,app->work[1]+46,app->clicks);
            }
            if (t<app->work[1]+72 && b>app->work[1]+48) {
                box[0]=app->work[0]+8; box[1]=app->work[1]+48;
                box[2]=app->work[0]+135; box[3]=app->work[1]+71;
                vsf_color(app->vdi,config->ink); v_bar(app->vdi,box);
                if (!app->armed) {
                    ++box[0]; ++box[1]; --box[2]; --box[3];
                    vsf_color(app->vdi,config->paper); v_bar(app->vdi,box);
                }
                /* The current VDI profile uses opaque white text cells. */
                vst_color(app->vdi,config->ink);
                v_gtext(app->vdi,app->work[0]+32,app->work[1]+64,"Activate");
            }
            if (b>app->work[1]+80) {
                vst_color(app->vdi,config->ink);
                v_gtext(app->vdi,app->work[0]+8,app->work[1]+88,
                        app->tick ? "Tick: *":"Tick: .");
            }
        }
        okay=wind_get(app->window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++app->paints;
    return okay;
}

static WORD changed(struct InputApp *app,WORD parts)
{
    WORD damage[4]={app->work[0]+8,app->work[1]+24,128,8};
    if ((parts&KEY_CHANGED) && !redraw(app,damage)) return 0;
    if (parts&BUTTON_CHANGED) {
        damage[1]=app->work[1]+40; damage[3]=32;
        if (!redraw(app,damage)) return 0;
    }
    if (parts&TIMER_CHANGED) {
        damage[1]=app->work[1]+82; damage[3]=8;
        if (!redraw(app,damage)) return 0;
    }
    return 1;
}

WORD InputRun(struct InputApp *app)
{
    WORD i,cw,ch,bw,bh,events,mx,my,mb,ks,kr,br,parts,quit=0,result=1;
    const struct InputConfig *config=app->config;
    const char *initialKey="Key: 0000",*initialClicks="Clicks: 00000";
    for (i=0;i<10;++i) app->key[i]=initialKey[i];
    for (i=0;i<14;++i) app->clicks[i]=initialClicks[i];
    app->id=appl_init(); app->window=-1;
    if (app->id<0) return 1;
    app->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) app->input[i]=1;
    app->input[6]=config->ink; app->input[9]=config->paper; app->input[10]=2;
    v_opnvwk(app->input,&app->vdi,app->output);
    if (!app->vdi) goto finish;
    app->window=wind_create(NAME|CLOSER|MOVER,0,0,config->width,config->height);
    if (app->window<0) goto finish;
    if (!wind_set_str(app->window,WF_NAME,config->title)) goto finish;
    if (!wind_open(app->window,config->x,config->y,config->width,config->height)) goto finish;
    app->opened=1;
    if (!wind_get(app->window,WF_WXYWH,&app->work[0],&app->work[1],
                  &app->work[2],&app->work[3])) goto finish;
    app->ready=1; result=0;
    while (!quit) {
        parts=0;
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|MU_TIMER,1,1,app->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,app->message,1000,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) {
            if (!InputRecover()) { result=2; break; }
            /* Loss cannot activate a control. Wait for a released baseline
             * before accepting another press, including after a lost up. */
            app->armed=0; app->down=1;
            if (!changed(app,BUTTON_CHANGED)) { result=2; break; }
            continue;
        }
        if (events&MU_BUTTON) {
            if (mb&1) { app->down=1; app->armed=inside(app,mx,my); }
            else {
                if (app->armed && inside(app,mx,my)) activate(app);
                app->down=app->armed=0;
            }
            parts|=BUTTON_CHANGED;
        }
        if (events&MU_KEYBD) {
            key_label(app,(UWORD)kr); parts|=KEY_CHANGED;
            if (kr==0x011b && app->armed) {
                app->armed=0; parts|=BUTTON_CHANGED;
            }
        }
        if (events&MU_TIMER) { app->tick=!app->tick; parts|=TIMER_CHANGED; }
        if ((events&MU_MESAG) && app->message[3]==app->window) {
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
        if (!quit && parts && !changed(app,parts)) result=2;
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
