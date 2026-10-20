/* SPDX-License-Identifier: MIT */
#include "editor.h"
#include "file-ui.h"
#include "assist-ui.h"
#include "assist.h"
#include <exec816/aes.h>
#include <string.h>

enum { MENU_NEW=8,MENU_OPEN=9,MENU_SAVE=10,MENU_SAVE_AS=11,MENU_QUIT=12,MENU_RECOVERY=13,
    MENU_UNDO=15,MENU_REDO=16,MENU_ALL=17,MENU_FIND=18,MENU_NEXT=19,MENU_REPLACE=20,
    MENU_PROC_NEXT=22,MENU_PROC_PREVIOUS=23,MENU_FOLD=24 };
static const OBJECT menu[]={
    {-1,1,6,G_IBOX,0,0,0,0,0,640,240},
    {6,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,5,G_IBOX,0,0,0,8,0,424,11},
    {4,-1,-1,G_TITLE,0,0,(ULONG)"File",0,0,48,11},
    {5,-1,-1,G_TITLE,0,0,(ULONG)"Edit",48,0,48,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Navigate",96,0,80,11},
    {0,7,21,G_IBOX,0,0,0,0,11,640,229},
    {14,8,13,G_BOX,0,0,0x1100,8,0,160,66},
    {9,-1,-1,G_STRING,0,0,(ULONG)"New       ^N",0,0,160,11},
    {10,-1,-1,G_STRING,0,0,(ULONG)"Open      ^O",0,11,160,11},
    {11,-1,-1,G_STRING,0,0,(ULONG)"Save      ^S",0,22,160,11},
    {12,-1,-1,G_STRING,0,0,(ULONG)"Save As   ^W",0,33,160,11},
    {13,-1,-1,G_STRING,0,0,(ULONG)"Quit      ^Q",0,44,160,11},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Recovery paths",0,55,160,11},
    {21,15,20,G_BOX,0,0,0x1100,56,0,160,66},
    {16,-1,-1,G_STRING,0,0,(ULONG)"Undo      ^Z",0,0,160,11},
    {17,-1,-1,G_STRING,0,0,(ULONG)"Redo      ^Y",0,11,160,11},
    {18,-1,-1,G_STRING,0,0,(ULONG)"Select All ^A",0,22,160,11},
    {19,-1,-1,G_STRING,0,0,(ULONG)"Find      ^F",0,33,160,11},
    {20,-1,-1,G_STRING,0,0,(ULONG)"Find Next ^G",0,44,160,11},
    {14,-1,-1,G_STRING,0,0,(ULONG)"Replace All ^R",0,55,160,11},
    {6,22,24,G_BOX,0,0,0x1100,104,0,184,33},
    {23,-1,-1,G_STRING,0,0,(ULONG)"Next procedure",0,0,184,11},
    {24,-1,-1,G_STRING,0,0,(ULONG)"Previous procedure",0,11,184,11},
    {21,-1,-1,G_STRING,LASTOB,0,(ULONG)"Fold / Unfold",0,22,184,11}
};
static WORD min(WORD a,WORD b) { return a<b ? a:b; }
static WORD max(WORD a,WORD b) { return a>b ? a:b; }

void BasicEditorDamage(struct BasicEditor *e,UWORD first,UWORD end)
{
    WORD a=BasicAssistanceRow(e,first),b=end>=BASIC_LINES ? e->rows:BasicAssistanceRow(e,end);
    if (a>=b) return;
    if (!e->dirty) { e->damageFirst=a;e->damageEnd=b; }
    else { e->damageFirst=min(a,e->damageFirst);e->damageEnd=max(b,e->damageEnd); }
    e->dirty=e->publish=1;
}

static WORD viewport(struct BasicEditor *e)
{
    WORD extent,size,position;struct BasicApp *a=&e->app;
    if (!wind_get(a->window,WF_WXYWH,&a->work[0],&a->work[1],&a->work[2],&a->work[3])) return 0;
    e->rows=max(1,(a->work[3]-16)/a->cellh);e->columns=min(80,max(1,(a->work[2]-8)/a->cellw));
    BasicAssistanceReveal(e,e->first);
    extent=BasicAssistanceTop(e);e->first=min(e->first,extent);
    size=extent ? (LONG)e->rows*1000/BasicAssistanceCount(e):1000;
    position=extent ? (LONG)e->first*1000/extent:0;
    if (size!=e->sliderSize) {
        if (!wind_set(a->window,WF_VSLSIZE,size,0,0,0)) return 0;e->sliderSize=size;
    }
    if (position!=e->sliderPosition) {
        if (!wind_set(a->window,WF_VSLIDE,position,0,0,0)) return 0;e->sliderPosition=position;
    }
    return 1;
}

void BasicEditorReveal(struct BasicEditor *e)
{
    UWORD line=BasicLine(&e->document,e->caret),old=e->first,left=e->left;
    ULONG column=BasicColumn(&e->document,e->caret);
    BasicAssistanceReveal(e,line);
    if (column<e->left) e->left=column;
    if (column>=e->left+e->columns) e->left=column-e->columns+1;
    if (e->first!=old || e->left!=left) BasicEditorDamage(e,0,BASIC_LINES);
    BasicEditorDamage(e,line,line+1);
}

static ULONG at_column(const struct BasicDocument *d,UWORD line,ULONG column)
{
    ULONG at=d->line[line],c=0,next;
    while (at<d->bytes && BasicByte(d,at)!=10) {
        next=BasicByte(d,at)==9 ? (c+8)&~7UL:c+1;
        if (next>column) break;
        c=next;++at;
    }
    return at;
}

ULONG BasicEditorPosition(const struct BasicEditor *e,WORD x,WORD y)
{
    WORD line=BasicAssistanceLine(e,max(0,(y-e->app.work[1])/e->app.cellh));
    ULONG col=max(0,(x-e->app.work[0]-4)/e->app.cellw)+e->left;
    if (line>=e->document.lines) return e->document.bytes;
    return at_column(&e->document,line,col);
}

static void row_text(struct BasicEditor *e,UWORD line)
{
    ULONG at,col=0,next;UWORD i=0;UBYTE c;
    memset(e->row,' ',e->columns);e->row[e->columns]=0;
    if (line>=e->document.lines) return;
    at=e->document.line[line];
    while (at<e->document.bytes && i<e->columns) {
        c=BasicByte(&e->document,at++);if (c==10) break;
        next=c==9 ? (col+8)&~7UL:col+1;
        while (col<next) { if (col>=e->left) e->row[i++]=c==9 ? ' ':c;++col;if (i==e->columns) break; }
    }
}

static WORD paint(struct BasicEditor *e)
{
    struct BasicApp *a=&e->app;WORD r[4],clip[4],bar[4],i,y,end,okay=1;
    ULONG lo=e->anchor<e->caret ? e->anchor:e->caret,hi=e->anchor>e->caret ? e->anchor:e->caret;
    ULONG start,finish,at;UWORD line;
    end=min(e->damageEnd,e->damageFirst+4);
    if (end==e->damageEnd && end-e->damageFirst==4) --end;
    y=a->work[1]+e->damageFirst*a->cellh;
    if (!ExecAESBeginUpdate(a->window)) return 0;
    if (!wind_get(a->window,WF_FIRSTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    while (okay && r[2] && r[3]) {
        clip[0]=max(a->work[0],r[0]);clip[1]=max(y,r[1]);
        clip[2]=min(a->work[0]+a->work[2],r[0]+r[2])-1;
        clip[3]=min(a->work[1]+end*a->cellh,r[1]+r[3])-1;
        if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
            vs_clip(a->vdi,1,clip);vsf_color(a->vdi,0);v_bar(a->vdi,clip);vst_color(a->vdi,1);
            for (i=e->damageFirst;i<end;++i) {
                line=BasicAssistanceLine(e,i);row_text(e,line);
                BasicAssistanceColors(e,line,e->colors);
                {
                    UWORD column=0,stop;char saved;
                    while (column<e->columns) {
                        stop=column+1;while (stop<e->columns && e->colors[stop]==e->colors[column]) ++stop;
                        saved=e->row[stop];e->row[stop]=0;vst_color(a->vdi,e->colors[column]);
                        v_gtext(a->vdi,a->work[0]+4+column*a->cellw,a->work[1]+i*a->cellh+6,e->row+column);
                        e->row[stop]=saved;column=stop;
                    }
                }
                if (line<e->document.lines && lo<hi && lo<e->document.line[line+1] && hi>e->document.line[line]) {
                    at=lo>e->document.line[line] ? lo:e->document.line[line];start=BasicColumn(&e->document,at);
                    at=hi<e->document.line[line+1] ? hi:e->document.line[line+1];
                    if (at>e->document.line[line] && at<=e->document.bytes && BasicByte(&e->document,at-1)==10) --at;
                    finish=BasicColumn(&e->document,at);if (hi>at) ++finish;
                    bar[0]=a->work[0]+4+max(0,(WORD)start-e->left)*a->cellw;
                    bar[2]=a->work[0]+3+min(e->columns,(WORD)finish-e->left)*a->cellw;
                    bar[1]=a->work[1]+i*a->cellh+7;bar[3]=bar[1];
                    if (bar[0]<=bar[2]) { vsf_color(a->vdi,3);v_bar(a->vdi,bar); }
                }
                if (line==BasicLine(&e->document,e->caret)) {
                    start=BasicColumn(&e->document,e->caret);
                    if (start>=e->left && start<e->left+e->columns) {
                        bar[0]=bar[2]=a->work[0]+4+(start-e->left)*a->cellw;
                        bar[1]=a->work[1]+i*a->cellh;bar[3]=bar[1]+a->cellh-1;
                        vsf_color(a->vdi,1);v_bar(a->vdi,bar);
                    }
                }
            }
            okay=ExecAESDiagnostic()==AES_OK;
        }
        if (end==e->damageEnd) {
            clip[0]=max(a->work[0],r[0]);clip[1]=max(a->work[1]+e->rows*a->cellh,r[1]);
            clip[2]=min(a->work[0]+a->work[2],r[0]+r[2])-1;
            clip[3]=min(a->work[1]+a->work[3],r[1]+r[3])-1;
            if (clip[0]<=clip[2] && clip[1]<=clip[3]) {
                vs_clip(a->vdi,1,clip);vsf_color(a->vdi,0);v_bar(a->vdi,clip);vst_color(a->vdi,1);
                memset(e->row,' ',e->columns);e->row[e->columns]=0;
                e->row[0]=BasicDirty(&e->document) ? '*':' ';
                if (e->columns>2) {
                    UWORD n=strlen(e->status);if (n>e->columns-2) n=e->columns-2;
                    memcpy(e->row+2,e->status,n);
                }
                v_gtext(a->vdi,a->work[0]+4,a->work[1]+e->rows*a->cellh+10,e->row);
                if (!ExecAESPainted(a->window,clip[0],clip[1],clip[2]-clip[0]+1,clip[3]-clip[1]+1)) okay=0;
            }
        }
        if (!wind_get(a->window,WF_NEXTXYWH,&r[0],&r[1],&r[2],&r[3])) okay=0;
    }
    if (okay) okay=ExecAESPainted(a->window,a->work[0],y,a->work[2],(end-e->damageFirst)*a->cellh);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) { e->damageFirst=end;e->dirty=end<e->damageEnd;++e->paintTurns; }
    return okay;
}

WORD BasicEditorKey(struct BasicEditor *e,WORD key,WORD mods)
{
    struct BasicDocument *d=&e->document;UBYTE c=key&255;
    ULONG before=e->caret,at=e->caret,lo=e->anchor<at ? e->anchor:at,hi=e->anchor>at ? e->anchor:at;
    UWORD line=BasicLine(d,at),editFirst=BasicLine(d,lo),oldLines=d->lines;
    WORD result=0,scan=(UWORD)key>>8;
    if (c==1 || ((mods&4) && (c=='a' || c=='A'))) { e->anchor=0;e->caret=d->bytes;goto selected; }
    if (c==26 || c==25 || ((mods&4) && (c=='z' || c=='Z' || c=='y' || c=='Y'))) {
        if (c==25 || c=='y' || c=='Y') result=BasicRedo(d);else result=BasicUndo(d);
        if (result) { if (e->caret>d->bytes) e->caret=d->bytes;e->anchor=e->caret;BasicEditorDamage(e,0,BASIC_LINES); }
        BasicEditorReveal(e);return BASIC_OK;
    }
    if (scan==0x4b) { if (at) --at; }
    else if (scan==0x4d) { if (at<d->bytes) ++at; }
    else if (scan==0x48 && line) at=at_column(d,BasicAssistancePrevious(e,line),BasicColumn(d,at));
    else if (scan==0x50 && BasicAssistanceNext(e,line)<d->lines) at=at_column(d,BasicAssistanceNext(e,line),BasicColumn(d,at));
    else if (scan==0x47) at=d->line[line];
    else if (scan==0x4f) at=line+1<d->lines ? d->line[line+1]-1:d->bytes;
    else if (c==8 || c==127) {
        if (lo==hi) { if (c==8 && lo) --lo;else if (c==127 && hi<d->bytes) ++hi; }
        editFirst=BasicLine(d,lo);
        result=BasicReplace(d,lo,hi-lo,0,0);if (result) return result;
        e->caret=e->anchor=lo;goto edited;
    } else if (c==9 || c==13 || (c>=32 && c<=126 && !(mods&12))) {
        if (c==13) {
            result=BasicIndent(d,lo,hi-lo,&at);if (result) return result;
            e->caret=e->anchor=at;goto edited;
        }
        result=BasicReplace(d,lo,hi-lo,&c,1);if (result) return result;
        e->caret=e->anchor=lo+1;goto edited;
    } else return BASIC_OK;
    e->caret=at;if (!(mods&3)) e->anchor=at;
selected:
    if (lo!=hi) BasicEditorDamage(e,BasicLine(d,lo),BasicLine(d,hi)+1);
    BasicEditorDamage(e,BasicLine(d,before),BasicLine(d,before)+1);
    if (e->anchor!=e->caret) BasicEditorDamage(e,0,BASIC_LINES);
    BasicEditorReveal(e);return BASIC_OK;
edited:
    ++e->edits;
    line=editFirst;
    if (oldLines!=d->lines || lo!=hi) BasicEditorDamage(e,line,e->first+e->rows);
    else BasicEditorDamage(e,line,line+1);
    BasicEditorReveal(e);return BASIC_OK;
}

WORD BasicEditorRun(struct BasicEditor *e)
{
    WORD quit=0,result=20,events,mx=0,my=0,buttons,mods,key,clicks,i,action,x,y;
    struct BasicApp *a=&e->app;
    BasicAssistanceInit(e);
    if (!BasicOpen(a)) goto finish;
    if (!wind_calc(WC_BORDER,BASIC_WINDOW_KIND,0,0,288,128,&x,&y,&e->minw,&e->minh)) goto finish;
    memcpy(e->menu,menu,sizeof(menu));if (!menu_bar(e->menu,1)) goto finish;
    e->sliderSize=e->sliderPosition=-1;
    if (!viewport(e)) goto finish;
    strcpy(e->status,"Ctrl+O Open  Ctrl+S Save");
    BasicEditorDamage(e,0,BASIC_LINES);result=0;
    while (!quit && !result) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG|(e->dragging ? MU_M1:0)|((e->dirty || BasicFilesWork() || BasicAssistanceWork(e)) ? MU_TIMER:0),
            1,1,e->dragging ? 0:1,1,mx,my,1,1,0,0,0,0,0,a->message,
            0,0,&mx,&my,&buttons,&mods,&key,&clicks);
        if (!events) {
            if (ExecAESDiagnostic()==AES_INPUT_LOST) { e->dragging=0;continue; }
            result=20;break;
        }
        action=0;
        if (events&MU_MESAG) {
            WORD *m=a->message;
            if (m[0]==MN_SELECTED) { action=m[4];if (!menu_tnormal(e->menu,m[3],1)) result=20; }
            else if (m[3]==a->window) switch (m[0]) {
            case WM_CLOSED:BasicAssistanceCancel(e);BasicFilesRequest(BASIC_FILE_QUIT);break;
            case WM_TOPPED:if (!wind_set(a->window,WF_TOP,0,0,0,0)) result=20;break;
            case WM_SIZED:
                m[6]=max(e->minw,m[6]);m[7]=max(e->minh,m[7]);
                /* Fall through. */
            case WM_MOVED:
                if (!wind_set(a->window,WF_CXYWH,m[4],m[5],m[6],m[7]) || !viewport(e)) result=20;
                BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);break;
            case WM_REDRAW:BasicEditorDamage(e,0,BASIC_LINES);break;
            case WM_ARROWED:
                i=m[4];action=i==WA_UPPAGE || i==WA_DNPAGE ? e->rows:1;
                while (action--) e->first=i==WA_UPLINE || i==WA_UPPAGE ?
                    BasicAssistancePrevious(e,e->first):BasicAssistanceNext(e,e->first);
                action=0;
                if (!viewport(e)) result=20;BasicEditorDamage(e,0,BASIC_LINES);break;
            case WM_VSLID:
                e->first=(ULONG)m[4]*BasicAssistanceTop(e)/1000;
                if (!viewport(e)) result=20;BasicEditorDamage(e,0,BASIC_LINES);break;
            }
        }
        if (quit || result) break;
        if (events&MU_KEYBD) {
            switch (key&255) {
            case 14:action=MENU_NEW;break;
            case 15:action=MENU_OPEN;break;
            case 19:action=MENU_SAVE;break;
            case 23:action=MENU_SAVE_AS;break;
            case 17:action=MENU_QUIT;break;
            case 27:BasicFilesCancel();BasicAssistanceCancel(e);break;
            case 6:action=MENU_FIND;break;
            case 7:action=MENU_NEXT;break;
            case 18:action=MENU_REPLACE;break;
            }
        }
        if (action>=MENU_NEW && action<=MENU_QUIT) {
            BasicAssistanceCancel(e);BasicFilesRequest(action-MENU_NEW+BASIC_FILE_NEW);events&=~MU_KEYBD;
        }
        if (action==MENU_RECOVERY) BasicFilesRequest(BASIC_FILE_RECOVERY);
        if (action>=MENU_FIND && action<=MENU_REPLACE) {
            BasicAssistanceRequest(action-MENU_FIND+BASIC_ASSIST_FIND);events&=~MU_KEYBD;
        }
        if (action>=MENU_PROC_NEXT && action<=MENU_FOLD) {
            BasicAssistanceRequest(action-MENU_PROC_NEXT+BASIC_ASSIST_PROC_NEXT);events&=~MU_KEYBD;
        }
        if (action==MENU_UNDO) { key=26;events|=MU_KEYBD; }
        if (action==MENU_REDO) { key=25;events|=MU_KEYBD; }
        if (action==MENU_ALL) { key=1;events|=MU_KEYBD; }
        if ((events&MU_KEYBD) && !BasicFilesLoading() && !BasicAssistanceBusy()) {
            i=BasicEditorKey(e,key,mods);
            if (i) {
                const char *message="Edit rejected";
                if (i==BASIC_MEMORY) message="Not enough memory";
                if (i==BASIC_CAPACITY) message="Source exceeds 32768 bytes";
                if (i==BASIC_LINE_CAPACITY) message="Source exceeds 4096 lines";
                if (i==BASIC_LINE_LENGTH) message="Line exceeds 255 bytes";
                if (i==BASIC_CHARACTER) message="Unsupported source byte";
                if (i==BASIC_UNDO_CAPACITY) message="Edit exceeds the undo budget";
                if (i==BASIC_POSITION) message="Caret outside source";
                if (i==BASIC_GENERATION) message="Edit identity exhausted";
                strcpy(e->status,message);
                BasicEditorDamage(e,0,BASIC_LINES);
                if (!form_alert(1,"[1][Edit exceeds limits][OK]") &&
                    ExecAESDiagnostic()!=AES_PENDING)
                    wind_set_str(a->window,WF_NAME,"FastBasic - edit rejected");
                if (ExecAESDiagnostic()==AES_PENDING) continue;
            }
            if (!viewport(e)) result=20;
        }
        if ((events&MU_BUTTON) && buttons && ExecAESInputWindow(MU_BUTTON)==a->window) {
            e->caret=BasicEditorPosition(e,mx,my);if (!(mods&3)) e->anchor=e->caret;e->dragging=1;
            BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);
        }
        if ((events&MU_M1) && e->dragging) {
            e->caret=BasicEditorPosition(e,mx,my);BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);
        }
        if ((events&MU_BUTTON) && !buttons) e->dragging=0;
        if (BasicFilesWork()) {
            i=BasicFilesStep(e);if (i==1) break;if (i==2) continue;
            if (!viewport(e)) result=20;
        }
        if (BasicAssistanceWork(e)) {
            i=BasicAssistanceStep(e);if (i==2) continue;
            if (i==1 && !viewport(e)) result=20;
        }
        if (e->publish) {
            if (!ExecAESBeginUpdate(a->window) || !wind_update(END_UPDATE)) { result=20;break; }
            e->publish=0;
        }
        if (e->dirty && !paint(e)) result=20;
    }
finish:
    BasicAssistanceDispose();
    BasicFilesDispose();
    if (!BasicClose(a)) result=20;
    return result;
}
