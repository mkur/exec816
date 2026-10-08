/* SPDX-License-Identifier: MIT */
#include "browser.h"
#include <exec816/aes.h>
#include <string.h>
#include <proto/exec.h>

enum { MENU_TITLE=3, MENU_OPEN=6, MENU_REFRESH=7, MENU_STOP=8, MENU_QUIT=9 };
static const OBJECT menuSource[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Files",0,0,64,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,9,G_BOX,0,0,0x00011100,8,0,112,66},
    {7,-1,-1,G_STRING,0,DISABLED,(ULONG)"Open",1,1,110,16},
    {8,-1,-1,G_STRING,0,0,(ULONG)"Refresh",1,17,110,16},
    {9,-1,-1,G_STRING,0,DISABLED,(ULONG)"Stop",1,33,110,16},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Quit",1,49,110,16}
};
static WORD menu_state(struct Browser *b)
{
    WORD enabled=(b->selected>=0 && (b->entries[b->selected].kind>0 || !b->child) ? 1:0)
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
static void label(char *to,const char *from,WORD max)
{
    WORD i=0;
    while (i<max && from[i]) { to[i]=from[i];++i; }
    to[i]=0;
}
/* Reuse a bounded set of row objects; names and selection belong to Files. */
static void layout(struct Browser *b)
{
    WORD i,index,columns=(b->work[2]-16)/8;
    b->visible=(b->work[3]-48)/12;
    if (b->visible<1) b->visible=1;
    if (b->visible>BROWSER_ROWS) b->visible=BROWSER_ROWS;
    if (b->first>b->count-b->visible) b->first=b->count-b->visible;
    if (b->first<0) b->first=0;
    if (columns>80) columns=80;
    b->tree[0].ob_x=b->work[0];b->tree[0].ob_y=b->work[1];
    b->tree[0].ob_width=b->work[2];b->tree[0].ob_height=b->work[3];
    for (i=0;i<BROWSER_ROWS;++i) {
        OBJECT *row=&b->tree[BROWSER_ROW_FIRST+i];
        index=b->first+i;
        row->ob_spec=(ULONG)b->labels[i];row->ob_width=b->work[2]-16;
        row->ob_flags=i<b->visible ? SELECTABLE:SELECTABLE|HIDETREE;
        row->ob_state=index<b->count ? (index==b->selected ? SELECTED:0):DISABLED;
        b->labels[i][0]=0;
        if (index<b->count) {
            b->labels[i][0]=b->entries[index].kind>0 ? '>':' ';
            label(b->labels[i]+1,b->entries[index].name,columns-1);
        }
    }
    b->tree[BROWSER_STATUS].ob_spec=(ULONG)b->status;
    b->tree[BROWSER_STATUS].ob_width=b->work[2]-16;
    b->tree[BROWSER_STATUS].ob_y=b->work[3]-12;
}
static WORD sliders(struct Browser *b)
{
    WORD extent=b->count>b->visible ? b->count-b->visible:0;
    WORD position=extent ? (LONG)b->first*1000/extent:0;
    WORD size=extent ? (LONG)b->visible*1000/b->count:1000;
    return wind_set(b->window,WF_VSLSIZE,size,0,0,0) &&
           wind_set(b->window,WF_VSLIDE,position,0,0,0);
}
static WORD redraw(struct Browser *b,const WORD *damage)
{
    WORD okay;
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3]);
    if (okay) { layout(b);okay=objc_draw(b->tree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]); }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++b->paints;
    return okay;
}
/* Enumerate only on navigation/refresh. Preserve a selected name, not its row. */
static WORD refresh(struct Browser *b)
{
    BPTR lock;
    LONG error=0;
    WORD more=0;
    b->savedName[0]=0;
    if (b->selected>=0) strcpy(b->savedName,b->entries[b->selected].name);
    lock=Lock(b->path,SHARED_LOCK);
    if (!lock) { strcpy(b->status,"Directory unavailable");return redraw(b,b->work); }
    b->count=0;b->selected=-1;b->truncated=0;
    if (Examine(lock,&b->info) && b->info.fib_DirEntryType>0) {
        while ((more=ExNext(lock,&b->info)!=0) && b->count<BROWSER_ENTRIES) {
            struct BrowserEntry *entry=&b->entries[b->count];
            strcpy(entry->name,(char *)b->info.fib_FileName);entry->kind=b->info.fib_DirEntryType;
            if (!strcmp(entry->name,b->savedName)) b->selected=b->count;
            ++b->count;
        }
        if (more) b->truncated=1;
        else { error=IoErr();if (error==ERROR_NO_MORE_ENTRIES) error=0; }
    } else error=ERROR_OBJECT_WRONG_TYPE;
    UnLock(lock);
    if (error) strcpy(b->status,"Directory read failed");
    else if (b->truncated) strcpy(b->status,"First 256 entries (list full)");
    else label(b->status,b->path,63);
    layout(b);
    return sliders(b) && redraw(b,b->work);
}
static WORD scroll(struct Browser *b,WORD first)
{
    b->first=first;layout(b);
    return sliders(b) && redraw(b,b->work);
}
static WORD select_row(struct Browser *b,WORD index)
{
    if (!b->count) return 1;
    if (index<0) index=0;
    if (index>=b->count) index=b->count-1;
    b->selected=index;
    if (index<b->first) b->first=index;
    if (index>=b->first+b->visible) b->first=index-b->visible+1;
    return scroll(b,b->first);
}
static WORD up(struct Browser *b)
{
    WORD length=strlen(b->path);
    while (length && b->path[length-1]!=':' && b->path[length-1]!='/') --length;
    if (length && b->path[length-1]=='/') --length;
    b->path[length]=0;b->first=0;b->selected=-1;
    return refresh(b);
}
static WORD open_item(struct Browser *b)
{
    WORD i=b->selected,n;
    if (i<0 || i>=b->count) return 1;
    n=strlen(b->path);
    if (n+strlen(b->entries[i].name)+2>=sizeof(b->target)) return 1;
    strcpy(b->target,b->path);
    if (n && b->target[n-1]!=':') strcat(b->target,"/");
    strcat(b->target,b->entries[i].name);
    if (b->entries[i].kind>0) {
        if (strlen(b->target)>=sizeof(b->path)) { strcpy(b->status,"Path too long");return redraw(b,b->work); }
        strcpy(b->path,b->target);b->first=0;b->selected=-1;return refresh(b);
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
    b->entries=AllocMem((ULONG)sizeof(*b->entries)*BROWSER_ENTRIES,MEMF_PUBLIC);
    if (!b->entries) goto finish;
    strcpy(b->path,"SYS:");
    b->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) b->input[i]=1;
    b->input[10]=2;v_opnvwk(b->input,&b->vdi,b->output);
    if (!b->vdi) goto finish;
    b->window=wind_create(NAME|CLOSER|MOVER|SIZER|UPARROW|DNARROW|VSLIDE,0,0,240,176);
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
                    else if (hit==3) { if (!refresh(b)) result=2; }
                    else if (hit>=BROWSER_ROW_FIRST && hit<BROWSER_ROW_FIRST+b->visible &&
                             b->first+hit-BROWSER_ROW_FIRST<b->count) {
                        if (!select_row(b,b->first+hit-BROWSER_ROW_FIRST)) result=2;
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
                if (!select_row(b,b->selected+((b->kr>>8)==0x48 ? -1:1))) result=2;
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
            case WM_SIZED:
                if (b->message[6]<240) b->message[6]=240;
                if (b->message[7]<104) b->message[7]=104;
                if (b->message[4]+b->message[6]>640) b->message[4]=640-b->message[6];
                if (b->message[5]+b->message[7]>240) b->message[5]=240-b->message[7];
                /* Fall through: the application accepts and relayouts. */
            case WM_MOVED:
                if (!wind_set(b->window,WF_CXYWH,b->message[4],b->message[5],b->message[6],b->message[7])) result=2;
                if (!wind_get(b->window,WF_WXYWH,&b->work[0],&b->work[1],&b->work[2],&b->work[3])) result=2;
                layout(b);if (!sliders(b)) result=2;
                break;
            case WM_VSLID:
                if (!scroll(b,(LONG)b->message[4]*(b->count>b->visible ? b->count-b->visible:0)/1000)) result=2;
                break;
            case WM_ARROWED:
                hit=b->message[4];
                if (!scroll(b,b->first+(hit==WA_UPLINE ? -1:hit==WA_DNLINE ? 1:
                    hit==WA_UPPAGE ? -b->visible:b->visible))) result=2;
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
    if (b->entries) { FreeMem(b->entries,(ULONG)sizeof(*b->entries)*BROWSER_ENTRIES);b->entries=0; }
    if (!appl_exit()) result=3;
    b->id=0;return result;
}
