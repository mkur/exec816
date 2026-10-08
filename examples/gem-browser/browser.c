/* SPDX-License-Identifier: MIT */
#include "browser.h"
#include <exec816/aes.h>
#include <string.h>

enum { MENU_TITLE=3, MENU_OPEN=6, MENU_REFRESH=7, MENU_STOP=8, MENU_QUIT=9 };
static const OBJECT menuSource[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Files",0,0,64,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,9,G_BOX,0,0,0x1100,8,0,112,64},
    {7,-1,-1,G_STRING,0,DISABLED,(ULONG)"Open",0,0,112,16},
    {8,-1,-1,G_STRING,0,0,(ULONG)"Refresh",0,16,112,16},
    {9,-1,-1,G_STRING,0,DISABLED,(ULONG)"Stop",0,32,112,16},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Quit",0,48,112,16}
};
static WORD menu_state(struct Browser *b)
{
    WORD enabled=(b->selected>=0 && (b->kinds[b->selected]>0 || !b->child) ? 1:0)
        |(b->child ? 2:0);
    WORD changed=enabled^b->menuEnabled;
    if ((changed&1) && !menu_ienable(b->bar,MENU_OPEN,enabled&1)) return 0;
    if ((changed&2) && !menu_ienable(b->bar,MENU_STOP,enabled&2)) return 0;
    b->menuEnabled=enabled;return 1;
}
static void stop(struct Browser *b)
{
    if (b->child) { ExecBreakProgram(b->child);strcpy(b->status,"Stopping"); }
}
static WORD redraw(struct Browser *b,const WORD *damage)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
    b->tree[0].ob_x=b->work[0];b->tree[0].ob_y=b->work[1];
    if (okay) okay=objc_draw(b->tree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++b->paints;
    return okay;
}
static void label(char *to,const char *from,WORD max)
{
    WORD i=0;
    while (i<max && from[i]) { to[i]=from[i];++i; }
    to[i]=0;
}
static WORD refresh(struct Browser *b)
{
    BPTR lock;
    WORD i,skip=b->page*8,more=1;
    b->count=0;b->selected=-1;
    lock=Lock(b->path,SHARED_LOCK);
    if (lock) {
        if (Examine(lock,&b->info)) {
            while (skip-- && more) more=ExNext(lock,&b->info)!=0;
            while (more && b->count<8 && ExNext(lock,&b->info)) {
                i=b->count++;
                strcpy(b->names[i],(char *)b->info.fib_FileName);b->kinds[i]=b->info.fib_DirEntryType;
                b->labels[i][0]=b->kinds[i]>0 ? '>':' ';
                label(b->labels[i]+1,b->names[i],25);
            }
        }
        UnLock(lock);
        label(b->status,b->path,26);
    } else strcpy(b->status,"Directory unavailable");
    for (i=0;i<8;++i) {
        b->tree[4+i].ob_spec=(ULONG)b->labels[i];
        b->tree[4+i].ob_state=i<b->count ? 0:DISABLED;
        if (i>=b->count) b->labels[i][0]=0;
    }
    return redraw(b,b->work);
}
static WORD up(struct Browser *b)
{
    WORD length=strlen(b->path);
    while (length && b->path[length-1]!=':' && b->path[length-1]!='/') --length;
    if (length && b->path[length-1]=='/') --length;
    b->path[length]=0;b->page=0;
    return refresh(b);
}
static WORD open_item(struct Browser *b)
{
    WORD i=b->selected,n;
    if (i<0 || i>=b->count) return 1;
    n=strlen(b->path);
    if (n+strlen(b->names[i])+2>=sizeof(b->target)) return 1;
    strcpy(b->target,b->path);
    if (n && b->target[n-1]!=':') strcat(b->target,"/");
    strcat(b->target,b->names[i]);
    if (b->kinds[i]>0) {
        if (strlen(b->target)>=sizeof(b->path)) { strcpy(b->status,"Path too long");return redraw(b,b->work); }
        strcpy(b->path,b->target);b->page=0;return refresh(b);
    }
    if (b->child) strcpy(b->status,"Command still running");
    else {
        b->child=ExecStartProgram(b->target);
        if (b->child) { ++b->launches;strcpy(b->status,"Running (File > Stop)"); }
        else strcpy(b->status,"Cannot launch this file");
    }
    return redraw(b,b->work);
}
static WORD file_menu(struct Browser *b)
{
    WORD okay;
    b->popupInput.mn_tree=(LONG)(ULONG)b->menu;
    b->popupInput.mn_menu=0;b->popupInput.mn_item=1;
    b->popupInput.mn_scroll=0;b->popupInput.mn_keystate=0;
    menu_ienable(b->menu,1,b->selected>=0);
    menu_ienable(b->menu,3,b->child!=0);
    okay=menu_popup(&b->popupInput,b->work[0]+8,b->work[1]+32,&b->popupOutput);
    if (okay) {
        if (b->popupOutput.mn_item==1) return open_item(b);
        if (b->popupOutput.mn_item==2) return refresh(b);
        if (b->popupOutput.mn_item==3 && b->child) {
            stop(b);
        }
    }
    return redraw(b,b->work);
}
WORD BrowserRun(struct Browser *b)
{
    WORD i,cw,ch,bw,bh,events,hit,quit=0,result=1;
    b->id=appl_init();b->window=-1;b->selected=b->armed=-1;
    if (b->id<0) return 1;
    if (!rsrc_load("SYS:DESKTOP.RSC") || !rsrc_gaddr(R_TREE,0,(void **)&b->tree) ||
        !rsrc_gaddr(R_TREE,1,(void **)&b->menu)) goto finish;
    for (i=0;i<10;++i) b->bar[i]=menuSource[i];
    if (!menu_bar(b->bar,1)) goto finish;
    b->menuInstalled=1;b->menuEnabled=0;
    strcpy(b->path,"SYS:");b->tree[12].ob_spec=(ULONG)b->status;
    b->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) b->input[i]=1;
    b->input[10]=2;v_opnvwk(b->input,&b->vdi,b->output);
    if (!b->vdi) goto finish;
    b->window=wind_create(NAME|CLOSER|MOVER,0,0,240,176);
    if (b->window<0 || !wind_set_str(b->window,WF_NAME,"Files")) goto finish;
    if (!wind_open(b->window,16,56,240,176)) goto finish;
    b->opened=1;
    wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
    if (!refresh(b)) goto finish;
    b->ready=1;result=0;
    while (!quit) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|(b->child ? MU_TIMER:0),1,1,b->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,b->message,100,0,&b->mx,&b->my,&b->mb,&b->ks,&b->kr,&b->br);
        if (!events) {
            if (ExecAESDiagnostic()!=AES_INPUT_LOST) { result=2;break; }
            b->armed=-1;b->down=1;continue;
        }
        if (events&MU_BUTTON) {
            hit=objc_find(b->tree,0,MAX_DEPTH,b->mx,b->my);
            if (b->mb&1) { b->down=1;b->armed=hit; }
            else {
                b->down=0;
                if (hit==b->armed) {
                    if (hit==1) { if (!file_menu(b)) result=2; }
                    else if (hit==2) { if (!up(b)) result=2; }
                    else if (hit==3) { b->page=b->count==8 ? b->page+1:0;if (!refresh(b)) result=2; }
                    else if (hit>=4 && hit<4+b->count) {
                        if (b->selected>=0) b->tree[4+b->selected].ob_state=0;
                        b->selected=hit-4;b->tree[hit].ob_state=SELECTED;
                        if (!redraw(b,b->work)) result=2;
                    }
                }
                b->armed=-1;
            }
        }
        if (events&MU_KEYBD) {
            if ((b->kr&255)==13) { if (!open_item(b)) result=2; }
            else if ((b->kr&255)=='f' || (b->kr&255)=='F') { if (!file_menu(b)) result=2; }
            else if ((b->kr&255)==8) { if (!up(b)) result=2; }
            else if ((b->kr>>8)==0x48 || (b->kr>>8)==0x50) {
                if (b->selected>=0) b->tree[4+b->selected].ob_state=0;
                if ((b->kr>>8)==0x48) b->selected=b->selected>0 ? b->selected-1:b->count-1;
                else b->selected=b->selected+1<b->count ? b->selected+1:0;
                if (b->count) b->tree[4+b->selected].ob_state=SELECTED;
                if (!redraw(b,b->work)) result=2;
            }
        }
        if ((events&MU_TIMER) && b->child && ExecCollectProgram(b->child,&b->result)) {
            b->child=0;
            strcpy(b->status,b->result.primary ? "Command returned error":"Command finished");
            if (!redraw(b,b->work)) result=2;
        }
        if ((events&MU_MESAG) && b->message[0]==MN_SELECTED) {
            switch (b->message[4]) {
            case MENU_OPEN:if (!open_item(b)) result=2;break;
            case MENU_REFRESH:if (!refresh(b)) result=2;break;
            case MENU_STOP:stop(b);if (!redraw(b,b->work)) result=2;break;
            case MENU_QUIT:quit=1;break;
            }
            if (!menu_tnormal(b->bar,b->message[3],1)) result=2;
        }
        if ((events&MU_MESAG) && b->message[3]==b->window) {
            switch (b->message[0]) {
            case WM_CLOSED:quit=1;break;
            case WM_TOPPED:if (!wind_set(b->window,WF_TOP,0,0,0,0)) result=2;break;
            case WM_MOVED:
                if (!wind_set(b->window,WF_CXYWH,b->message[4],b->message[5],b->message[6],b->message[7])) result=2;
                break;
            case WM_REDRAW:if (!redraw(b,&b->message[4])) result=2;break;
            }
        }
        if (!menu_state(b)) result=2;
        if (result) break;
    }
finish:
    b->ready=0;
    if (b->child) {
        ExecBreakProgram(b->child);
        if (!ExecWaitProgram(b->child,&b->result)) return 3;
        b->child=0;
    }
    if (b->opened && wind_close(b->window)) b->opened=0;
    if (b->window>0 && !b->opened && wind_delete(b->window)) b->window=-1;
    if (b->menuInstalled) {
        if (!menu_bar(b->bar,0)) result=3;
        else b->menuInstalled=0;
    }
    if (b->vdi) { v_clsvwk(b->vdi);b->vdi=0; }
    if (!appl_exit()) result=3;
    b->id=0;return result;
}
