/* SPDX-License-Identifier: MIT */
#include "browser.h"
#include <exec816/aes.h>
#include <string.h>
#include <proto/exec.h>

enum { MENU_TITLE=3, MENU_OPEN=6, MENU_REFRESH=7, MENU_STOP=8, MENU_QUIT=9, MENU_PATH=10, MENU_NEW=11, MENU_RENAME=12 };
static const OBJECT menuSource[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Files",0,0,64,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,12,G_BOX,0,0,0x00011100,8,0,112,114},
    {7,-1,-1,G_STRING,0,DISABLED,(ULONG)"Open",1,1,110,16},
    {8,-1,-1,G_STRING,0,0,(ULONG)"Refresh",1,17,110,16},
    {9,-1,-1,G_STRING,0,DISABLED,(ULONG)"Stop",1,33,110,16},
    {10,-1,-1,G_STRING,0,0,(ULONG)"Quit",1,49,110,16},
    {11,-1,-1,G_STRING,0,0,(ULONG)"Path...",1,65,110,16},
    {12,-1,-1,G_STRING,0,0,(ULONG)"New Folder",1,81,110,16},
    {5,-1,-1,G_STRING,LASTOB,DISABLED,(ULONG)"Rename...",1,97,110,16}
};
static WORD menu_state(struct Browser *b)
{
    WORD enabled=(!b->dialog && b->selected>=0 && (b->entries[b->selected].kind>0 || !b->child) ? 1:0)
        |(b->child ? 2:0)|(!b->dialog && b->selected>=0 ? 4:0)|(!b->dialog ? 8:0);
    WORD changed=enabled^b->menuEnabled;
    if ((changed&1) && !menu_ienable(b->bar,MENU_OPEN,enabled&1)) return 0;
    if ((changed&2) && !menu_ienable(b->bar,MENU_STOP,enabled&2)) return 0;
    if ((changed&4) && !menu_ienable(b->bar,MENU_RENAME,enabled&4)) return 0;
    if (changed&8) {
        if (!menu_ienable(b->bar,MENU_REFRESH,enabled&8) ||
            !menu_ienable(b->bar,MENU_PATH,enabled&8) || !menu_ienable(b->bar,MENU_NEW,enabled&8)) return 0;
    }
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
    if (b->dialog) {
        b->dialogTree[0].ob_x=b->work[0];b->dialogTree[0].ob_y=b->work[1];
        b->dialogTree[0].ob_width=b->work[2];b->dialogTree[0].ob_height=b->work[3];
        b->dialogTree[2].ob_width=b->work[2]-16;
        b->dialogTree[5].ob_y=b->work[3]-10;b->dialogTree[5].ob_width=b->work[2]-16;
        return;
    }
    b->visible=(b->work[3]-48)/12;
    if (b->visible<1) b->visible=1;
    if (b->visible>BROWSER_ROWS) b->visible=BROWSER_ROWS;
    b->first=FileFirst(b->first,b->count,b->visible);
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
    WORD extent=!b->dialog && b->count>b->visible ? b->count-b->visible:0;
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
    if (okay) { layout(b);okay=objc_draw(b->dialog ? b->dialogTree:b->tree,0,MAX_DEPTH,damage[0],damage[1],damage[2],damage[3]); }
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++b->paints;
    return okay;
}
/* Enumerate only on navigation/refresh. Preserve a selected name, not its row. */
static WORD refresh_path(struct Browser *b,const char *path)
{
    WORD i,changed=strcmp(path,b->path)!=0;
    b->savedName[0]=0;
    if (!changed && b->selected>=0) strcpy(b->savedName,b->entries[b->selected].name);
    if (!FileScanBegin(&b->scan,path,&b->info,b->entries)) {
        strcpy(b->status,"Directory unavailable");return redraw(b,b->work);
    }
    if (changed) { strcpy(b->path,path); b->first=0; }
    while (FileScanNext(&b->scan)) {}
    b->count=b->scan.count;b->truncated=b->scan.truncated;b->selected=-1;
    for (i=0;i<b->count;++i)
        if (!strcmp(b->entries[i].name,b->savedName)) b->selected=i;
    if (b->scan.error) strcpy(b->status,"Directory read failed");
    else if (b->truncated) strcpy(b->status,"First 256 entries (list full)");
    else label(b->status,b->path,63);
    layout(b);
    return sliders(b) && redraw(b,b->work);
}
static WORD refresh(struct Browser *b)
{
    return refresh_path(b,b->path);
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
    b->first=FileExpose(b->first,index,b->visible);
    return scroll(b,b->first);
}
enum { DIALOG_PATH=1,DIALOG_NEW=2,DIALOG_RENAME=3 };
static const OBJECT dialogSource[]={
    {-1,1,5,G_BOX,0,0,0x1170,0,0,216,144},
    {2,-1,-1,G_STRING,0,0,0,8,2,192,8},
    {3,-1,-1,G_BOXTEXT,EDITABLE,0,0,8,16,200,16},
    {4,-1,-1,G_BUTTON,SELECTABLE|DEFAULT|EXIT,0,(ULONG)"OK",8,40,64,16},
    {5,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Cancel",96,40,88,16},
    {0,-1,-1,G_STRING,LASTOB,0,0,8,134,200,8}
};
static WORD dialog_open(struct Browser *b,WORD kind)
{
    WORD i;
    TEDINFO *ted=&b->dialogTed;
    if (b->dialog || (kind==DIALOG_RENAME && b->selected<0)) return 1;
    for (i=0;i<6;++i) b->dialogTree[i]=dialogSource[i];
    if (kind==DIALOG_PATH) b->dialogTree[1].ob_spec=(ULONG)"Path";
    else if (kind==DIALOG_NEW) b->dialogTree[1].ob_spec=(ULONG)"New Folder";
    else b->dialogTree[1].ob_spec=(ULONG)"Rename";
    b->dialogTree[2].ob_spec=(ULONG)ted;b->dialogTree[5].ob_spec=(ULONG)b->status;
    b->dialogTed.te_ptext=(ULONG)b->editText;b->dialogTed.te_ptmplt=(ULONG)"";
    b->dialogTed.te_pvalid=(ULONG)"x";b->dialogTed.te_font=IBM;b->dialogTed.te_just=TE_LEFT;
    b->dialogTed.te_color=0x1180;b->dialogTed.te_thickness=-1;
    b->dialogTed.te_txtlen=kind==DIALOG_PATH ? sizeof(b->editText):108;b->dialogTed.te_tmplen=1;
    strcpy(b->editText,kind==DIALOG_PATH ? b->path:kind==DIALOG_RENAME ? b->entries[b->selected].name:"");
    b->dialog=kind;b->focus=2;b->armed=-1;b->dialogError=0;b->status[0]=0;
    layout(b);
    return sliders(b) && redraw(b,b->work) && objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT);
}
static WORD dialog_end(struct Browser *b)
{
    WORD okay=objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END);
    b->dialog=0;b->armed=-1;layout(b);
    return okay && sliders(b);
}
static WORD dialog_cancel(struct Browser *b)
{
    if (!dialog_end(b)) return 0;
    label(b->status,b->path,63);return redraw(b,b->work);
}
static WORD dialog_focus(struct Browser *b,WORD focus)
{
    if (b->focus==focus) return 1;
    if (b->focus==2 && !objc_edit(b->dialogTree,2,0,&b->editIndex,ED_END)) return 0;
    if (b->focus!=2) b->dialogTree[b->focus].ob_state=0;
    b->focus=focus;
    if (focus!=2) b->dialogTree[focus].ob_state=SELECTED;
    if (!redraw(b,b->work)) return 0;
    if (focus==2) return objc_edit(b->dialogTree,2,0,&b->editIndex,ED_INIT);
    return 1;
}
static void full_name(struct Browser *b,const char *leaf,char *target)
{
    FileJoin(target,sizeof(b->target),b->path,leaf);
}
static WORD dialog_accept(struct Browser *b)
{
    BPTR lock;
    WORD i,kind=b->dialog,okay=0;
    if (!b->editText[0] || (kind!=DIALOG_PATH &&
        (strchr(b->editText,':') || strchr(b->editText,'/') || strchr(b->editText,'\\') ||
         !strcmp(b->editText,".") || !strcmp(b->editText,"..")))) {
        strcpy(b->status,kind==DIALOG_PATH ? "Enter a directory":"Enter one leaf name");
        return redraw(b,b->work);
    }
    if (kind==DIALOG_PATH) {
        lock=Lock(b->editText,SHARED_LOCK);
        if (lock) {
            okay=Examine(lock,&b->info)!=0;
            b->dialogError=okay ? 0:IoErr();
            if (okay && b->info.fib_DirEntryType<=0) { okay=0;b->dialogError=ERROR_OBJECT_WRONG_TYPE; }
            UnLock(lock);
        } else b->dialogError=IoErr();
    } else {
        full_name(b,b->editText,b->target);
        if (kind==DIALOG_NEW) {
            lock=CreateDir(b->target);okay=lock!=0;b->dialogError=okay ? 0:IoErr();
            if (lock) UnLock(lock);
        } else {
            /* Keep both full paths off the Task stack during the DOS call. */
            char *destination=AllocMem(256UL,MEMF_PUBLIC);
            if (!destination) { strcpy(b->status,"No memory");return redraw(b,b->work); }
            strcpy(destination,b->target);full_name(b,b->entries[b->selected].name,b->target);
            okay=Rename(b->target,destination)!=0;b->dialogError=okay ? 0:IoErr();
            FreeMem(destination,256UL);
        }
    }
    if (!okay) {
        strcpy(b->status,b->dialogError==ERROR_OBJECT_EXISTS ? "Name already exists":
            b->dialogError==ERROR_OBJECT_NOT_FOUND ? "Not found":
            b->dialogError==ERROR_DISK_WRITE_PROTECTED || b->dialogError==ERROR_WRITE_PROTECTED ? "Read-only volume":
            b->dialogError==ERROR_INVALID_COMPONENT_NAME ? "Invalid name":
            b->dialogError==ERROR_DISK_FULL ? "Disk full":
            kind==DIALOG_PATH ? "Directory unavailable":"Operation failed");
        return redraw(b,b->work);
    }
    if (!dialog_end(b)) return 0;
    if (!refresh_path(b,kind==DIALOG_PATH ? b->editText:b->path)) return 0;
    if (kind!=DIALOG_PATH) {
        for (i=0;i<b->count;++i) if (!strcmp(b->entries[i].name,b->editText)) return select_row(b,i);
    }
    return 1;
}
static WORD dialog_key(struct Browser *b)
{
    WORD next=b->focus,key=b->kr;
    if ((key&255)==27) return dialog_cancel(b);
    form_keybd(b->dialogTree,b->focus,b->focus,key,&next,&key);
    if (!key && next==3 && (b->kr&255)!=9 && b->kr!=0x0f00) return dialog_accept(b);
    if (!key && next==4 && (b->kr&255)!=9 && b->kr!=0x0f00) return dialog_cancel(b);
    if (!dialog_focus(b,next)) return 0;
    return key && b->focus==2 ? objc_edit(b->dialogTree,2,key,&b->editIndex,ED_CHAR):1;
}
static WORD dialog_click(struct Browser *b,WORD hit)
{
    if (hit==3) return dialog_accept(b);
    if (hit==4) return dialog_cancel(b);
    if (hit==2) return dialog_focus(b,2);
    return 1;
}
static WORD up(struct Browser *b)
{
    strcpy(b->target,b->path);FileParent(b->target);
    return refresh_path(b,b->target);
}
static WORD open_item(struct Browser *b)
{
    WORD i=b->selected;
    if (i<0 || i>=b->count) return 1;
    if (!FileJoin(b->target,sizeof(b->target),b->path,b->entries[i].name)) return 1;
    if (b->entries[i].kind>0) {
        if (strlen(b->target)>=sizeof(b->path)) { strcpy(b->status,"Path too long");return redraw(b,b->work); }
        return refresh_path(b,b->target);
    }
    if (b->child) strcpy(b->status,"Command still running");
    else {
        const char *name=b->entries[i].name;
        UWORD length=strlen(name);
        if (length>=4 && name[length-4]=='.' && (name[length-3]|32)=='t' &&
            (name[length-2]|32)=='x' && (name[length-1]|32)=='t') {
            length=strlen(b->target);
            if (length>127) { strcpy(b->status,"Text path too long");return redraw(b,b->work); }
            memmove(b->target+1,b->target,length);
            b->target[0]='"';b->target[length+1]='"';b->target[length+2]=0;
            b->child=ExecStartProgram("C:TEXT.APP",b->target,length+2);
        } else b->child=ExecStartProgram(b->target,NULL,0);
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
    for (i=0;i<13;++i) b->bar[i]=menuSource[i];
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
            hit=objc_find(b->dialog ? b->dialogTree:b->tree,0,MAX_DEPTH,b->mx,b->my);
            if (b->mb&1) { b->down=1;b->armed=hit; }
            else {
                b->down=0;
                if (hit==b->armed) {
                    if (b->dialog) { if (!dialog_click(b,hit)) result=2; }
                    else if (hit==1) { if (!file_menu(b)) result=2; }
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
            if (b->dialog) { if (!dialog_key(b)) result=2; }
            else if ((b->kr&255)=='p' || (b->kr&255)=='P') { if (!dialog_open(b,DIALOG_PATH)) result=2; }
            else if ((b->kr&255)=='n' || (b->kr&255)=='N') { if (!dialog_open(b,DIALOG_NEW)) result=2; }
            else if ((b->kr&255)=='r' || (b->kr&255)=='R') { if (!dialog_open(b,DIALOG_RENAME)) result=2; }
            else if ((b->kr&255)==13) { if (!open_item(b)) result=2; }
            else if ((b->kr&255)=='f' || (b->kr&255)=='F') { if (!file_menu(b)) result=2; }
            else if ((b->kr&255)==8) { if (!up(b)) result=2; }
            else if ((b->kr>>8)==0x48 || (b->kr>>8)==0x50) {
                if (!select_row(b,b->selected+((b->kr>>8)==0x48 ? -1:1))) result=2;
            }
        }
        if ((events&MU_TIMER) && b->child && ExecCollectProgram(b->child,&b->result)) {
            b->child=0;
            if (!b->dialog) strcpy(b->status,b->result.primary ? "Command returned error":"Command finished");
            if (!redraw(b,b->work)) result=2;
        }
        if ((events&MU_MESAG) && b->message[0]==MN_SELECTED) {
            switch (b->message[4]) {
            case MENU_OPEN:if (!open_item(b)) result=2;break;
            case MENU_REFRESH:if (!refresh(b)) result=2;break;
            case MENU_STOP:stop(b);if (!redraw(b,b->work)) result=2;break;
            case MENU_QUIT:quit=1;break;
            case MENU_PATH:if (!dialog_open(b,DIALOG_PATH)) result=2;break;
            case MENU_NEW:if (!dialog_open(b,DIALOG_NEW)) result=2;break;
            case MENU_RENAME:if (!dialog_open(b,DIALOG_RENAME)) result=2;break;
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
                if (b->dialog) break;
                if (!scroll(b,(LONG)b->message[4]*(b->count>b->visible ? b->count-b->visible:0)/1000)) result=2;
                break;
            case WM_ARROWED:
                if (b->dialog) break;
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
    if (b->dialog && !dialog_end(b)) result=3;
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
