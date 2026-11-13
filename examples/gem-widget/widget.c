/* SPDX-License-Identifier: MIT */
#include "widget.h"

static const OBJECT objects[]={
    {NIL,1,3,G_BOX,0,0,0x1170UL,0,0,304,128},
    {2,NIL,NIL,G_STRING,0,0,0,16,12,272,16},
    {3,NIL,NIL,G_BUTTON,SELECTABLE,0,(ULONG)"Toggle",16,44,128,24},
    {0,NIL,NIL,G_STRING,LASTOB,0,(ULONG)"Space: toggle   Q: quit",16,96,272,16}
};

static void label(struct Widget *app)
{
    uint32_t value=app->actions;
    WORD i;
    const char *prefix="Clicks: ";
    for (i=0;i<8;++i) app->label[i]=prefix[i];
    for (i=13;i>=8;--i) {
        app->label[i]='0'+value%10;
        value/=10;
    }
    app->label[14]=0;
}

/* One conventional GEM drawing transaction. Clip each object draw to the
 * damage, work area and one visible rectangle; reconstruct covered pixels
 * only when AES later asks for their exposure. */
static WORD redraw(struct Widget *app,const WORD *damage)
{
    WORD x,y,w,h,l,t,r,b,okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(app->window,WF_WORKXYWH,&app->work[0],&app->work[1],
        &app->work[2],&app->work[3]);
    app->tree[0].ob_x=app->work[0];
    app->tree[0].ob_y=app->work[1];
    app->tree[0].ob_width=app->work[2];
    app->tree[0].ob_height=app->work[3];
    if (!damage) damage=app->work;
    if (okay) okay=wind_get(app->window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w>0 && h>0) {
        l=app->work[0]>damage[0] ? app->work[0]:damage[0];
        t=app->work[1]>damage[1] ? app->work[1]:damage[1];
        r=app->work[0]+app->work[2];
        b=app->work[1]+app->work[3];
        if (r>damage[0]+damage[2]) r=damage[0]+damage[2];
        if (b>damage[1]+damage[3]) b=damage[1]+damage[3];
        if (l<x) l=x;
        if (t<y) t=y;
        if (r>x+w) r=x+w;
        if (b>y+h) b=y+h;
        if (l<r && t<b)
            okay=objc_draw(app->tree,0,MAX_DEPTH,l,t,r-l,b-t);
        if (okay) okay=wind_get(app->window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++app->paints;
    return okay;
}

static WORD activate(struct Widget *app)
{
    if (++app->actions==1000000UL) app->actions=0;
    app->tree[WIDGET_BUTTON].ob_state^=SELECTED;
    label(app);
    return redraw(app,NULL);
}

WORD WidgetRun(struct Widget *app)
{
    const WORD kind=NAME|CLOSER|MOVER;
    WORD i,x,y,w,h,cw,ch,bw,bh,events,mx,my,mb,ks,kr,br,down=1,quit=0,result=1;
    app->id=appl_init();
    app->window=-1;
    if (app->id<0) return 1;
    app->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) app->input[i]=1;
    app->input[9]=0;
    app->input[10]=2;
    v_opnvwk(app->input,&app->vdi,app->output);
    if (!app->vdi) goto finish;
    for (i=0;i<WIDGET_OBJECTS;++i) app->tree[i]=objects[i];
    app->tree[WIDGET_LABEL].ob_spec=(ULONG)app->label;
    label(app);
    /* Match the actual canvas, allowing each AES its own frame dimensions. */
    if (!wind_calc(WC_BORDER,kind,32,56,304,128,&x,&y,&w,&h)) goto finish;
    app->window=wind_create(kind,x,y,w,h);
    if (app->window<0) goto finish;
    if (!wind_set_str(app->window,WF_NAME,"GEM widget")) goto finish;
    if (!wind_open(app->window,x,y,w,h)) goto finish;
    app->opened=1;
    if (!redraw(app,NULL)) goto finish;
    app->ready=1;
    result=0;
    while (!quit) {
        /* No foreground timer: idle means waiting for input or a message.
         * Alternate down/up predicates so a held mouse cannot repeat clicks. */
        events=evnt_multi(MU_MESAG|MU_BUTTON|MU_KEYBD,1,1,down,
            0,0,0,0,0,0,0,0,0,0,app->message,0,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) { result=2; break; }
        if ((events & MU_MESAG) && app->message[3]==app->window) {
            switch (app->message[0]) {
            case WM_CLOSED: quit=1; break;
            case WM_TOPPED:
                if (!wind_set(app->window,WF_TOP,0,0,0,0)) result=2;
                break;
            case WM_MOVED:
                if (!wind_set(app->window,WF_CURRXYWH,app->message[4],app->message[5],
                              app->message[6],app->message[7]) || !redraw(app,NULL)) result=2;
                break;
            case WM_REDRAW:
                if (!redraw(app,&app->message[4])) result=2;
                break;
            }
        }
        if (events & MU_BUTTON) {
            if (!quit && down && objc_find(app->tree,0,MAX_DEPTH,mx,my)==WIDGET_BUTTON)
                if (!activate(app)) result=2;
            down=(mb & 1) ? 0:1;
        }
        if (!quit && (events & MU_KEYBD)) {
            if ((kr & 255)=='q' || (kr & 255)=='Q') quit=1;
            else if ((kr & 255)==' ' && !activate(app)) result=2;
        }
        if (result) break;
    }
finish:
    app->ready=0;
    if (app->opened && wind_close(app->window)) app->opened=0;
    if (app->window>=0 && !app->opened && wind_delete(app->window)) app->window=-1;
    if (app->vdi) { v_clsvwk(app->vdi); app->vdi=0; }
    if (!appl_exit()) result=3;
    app->id=0;
    return result;
}
