/* SPDX-License-Identifier: MIT */
#include "panel.h"
#include <exec816/aes.h>
#include <string.h>

static const OBJECT initial[8]={
    {-1,1,7,G_BOX,0,0,0x1170,0,0,192,136},
    {2,-1,-1,G_STRING,0,0,0,8,8,176,8},
    {3,-1,-1,G_BUTTON,SELECTABLE,0,0,8,32,80,16},
    {4,-1,-1,G_BUTTON,SELECTABLE,DISABLED,0,104,32,80,16},
    {5,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,SELECTED,0,8,64,80,16},
    {6,-1,-1,G_BUTTON,SELECTABLE|RBUTTON,0,0,104,64,80,16},
    {7,-1,-1,G_BUTTON,SELECTABLE|DEFAULT|EXIT,0,0,8,104,80,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|EXIT|LASTOB,0,0,104,104,80,16}
};

static WORD paint(struct Panel *p,WORD object,const WORD *damage)
{
    WORD okay,x,y,clip[4],mark[4];
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(p->window,WF_WXYWH,&p->work[0],&p->work[1],&p->work[2],&p->work[3]);
    p->tree[0].ob_x=p->work[0]; p->tree[0].ob_y=p->work[1];
    if (okay) okay=objc_draw(p->tree,object,object ? 0:MAX_DEPTH,
                           damage[0],damage[1],damage[2],damage[3]);
    if (okay && (object==0 || object==p->focus)) {
        objc_offset(p->tree,p->focus,&x,&y);
        clip[0]=damage[0]; clip[1]=damage[1];
        clip[2]=damage[0]+damage[2]-1; clip[3]=damage[1]+damage[3]-1;
        vs_clip(p->vdi,1,clip); vsf_color(p->vdi,1);
        mark[0]=x+3; mark[1]=y+13; mark[2]=x+76; mark[3]=y+13;
        v_bar(p->vdi,mark);
    }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++p->paints;
    return okay;
}
static WORD object(struct Panel *p,WORD index)
{
    WORD damage[4],x,y;
    objc_offset(p->tree,index,&x,&y);
    damage[0]=x-3; damage[1]=y-3;
    damage[2]=p->tree[index].ob_width+6; damage[3]=p->tree[index].ob_height+6;
    /* Strings are transparent; repaint their background in the same region. */
    return paint(p,index==1 ? 0:index,damage);
}
static WORD cancel(struct Panel *p)
{
    WORD armed=p->armed;
    if (armed<0) return 1;
    p->tree[armed].ob_state=p->saved; p->armed=-1;
    return object(p,armed);
}
static WORD action(struct Panel *p,WORD target)
{
    WORD i;
    ++p->actions;
    if (target==7) {
        p->tree[2].ob_state=0; p->tree[4].ob_state=SELECTED; p->tree[5].ob_state=0;
        strcpy(p->status,"Reset");
        for (i=2;i<=5;++i) if (i!=3 && !object(p,i)) return 0;
    } else {
        strcpy(p->status,target==6 ? "Applied":"Changed");
        if (target==4 || target==5) {
            if (!object(p,4) || !object(p,5)) return 0;
        } else if (!object(p,target)) return 0;
    }
    return object(p,1);
}
WORD PanelRun(struct Panel *p)
{
    WORD i,cw,ch,bw,bh,mx,my,mb,ks,kr,br,events,hit,next,unused,previous,quit=0,result=1;
    memcpy(p->tree,initial,sizeof(initial));
    strcpy(p->status,"Ready");
    p->tree[1].ob_spec=(ULONG)p->status;
    p->tree[2].ob_spec=(ULONG)"Toggle"; p->tree[3].ob_spec=(ULONG)"Locked";
    p->tree[4].ob_spec=(ULONG)"Small"; p->tree[5].ob_spec=(ULONG)"Large";
    p->tree[6].ob_spec=(ULONG)"Apply"; p->tree[7].ob_spec=(ULONG)"Cancel";
    p->focus=2; p->armed=-1; p->down=0;
    p->id=appl_init(); p->window=-1;
    if (p->id<0) return 1;
    p->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) p->input[i]=1;
    p->input[10]=2; v_opnvwk(p->input,&p->vdi,p->output);
    if (!p->vdi) goto finish;
    p->window=wind_create(NAME|CLOSER|MOVER,0,0,208,160);
    if (p->window<0 || !wind_set_str(p->window,WF_NAME,"GEM Control Panel")) goto finish;
    if (!wind_open(p->window,416,48,208,160)) goto finish;
    p->opened=1;
    wind_get(p->window,WF_WXYWH,&p->work[0],&p->work[1],&p->work[2],&p->work[3]);
    p->tree[0].ob_x=p->work[0]; p->tree[0].ob_y=p->work[1];
    p->ready=1; result=0;
    while (!quit) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG,1,1,p->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,p->message,0,0,&mx,&my,&mb,&ks,&kr,&br);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=2; break; }
            if (!cancel(p)) { result=2; break; }
            p->down=1; continue;
        }
        if (events&MU_BUTTON) {
            hit=objc_find(p->tree,0,MAX_DEPTH,mx,my);
            if (mb&1) {
                p->down=1;
                if (hit>=2 && !(p->tree[hit].ob_state&DISABLED)) {
                    previous=p->focus; p->focus=hit;
                    p->armed=hit; p->saved=p->tree[hit].ob_state;
                    p->tree[hit].ob_state^=SELECTED;
                    if (!object(p,hit) || (previous!=hit && !object(p,previous))) result=2;
                }
            } else {
                next=p->armed;
                p->down=0;
                if (next>=0 && hit==next) {
                    p->tree[next].ob_state=p->saved; p->armed=-1;
                    form_button(p->tree,hit,1,&next);
                    if (!action(p,hit)) result=2;
                } else if (!cancel(p)) result=2;
            }
        }
        if ((events&MU_KEYBD) && !result) {
            if (!cancel(p)) result=2;
            previous=p->focus;
            if ((kr&255)!=27) {
                if ((kr&255)==9 && (ks&3)) kr=0x0f00;
                form_keybd(p->tree,p->focus,p->focus,kr,&next,&unused);
                p->focus=next;
                if (!unused && ((kr&255)==13 || (kr&255)==32)) {
                    if (!action(p,next)) result=2;
                }
                if (p->focus!=previous && (!object(p,previous) || !object(p,p->focus))) result=2;
            }
        }
        if ((events&MU_MESAG) && p->message[3]==p->window) {
            switch (p->message[0]) {
            case WM_CLOSED: quit=1; break;
            case WM_TOPPED: if (!wind_set(p->window,WF_TOP,0,0,0,0)) result=2; break;
            case WM_MOVED:
                if (!cancel(p) || !wind_set(p->window,WF_CXYWH,p->message[4],p->message[5],p->message[6],p->message[7])) result=2;
                break;
            case WM_REDRAW: if (!paint(p,0,&p->message[4])) result=2; break;
            }
        }
        if (result) break;
    }
finish:
    p->ready=0;
    if (p->opened && wind_close(p->window)) p->opened=0;
    if (p->window>0 && !p->opened && wind_delete(p->window)) p->window=-1;
    if (p->vdi) { v_clsvwk(p->vdi); p->vdi=0; }
    if (!appl_exit()) result=3;
    p->id=0;
    return result;
}
