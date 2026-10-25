/* SPDX-License-Identifier: MIT */
#include "editor.h"
#include "file-ui.h"
#include "assist-ui.h"
#include "assist.h"
#include "build.h"
#include <exec816/aes-wait.h>
#include <exec816/aes.h>
#include <string.h>

enum { MENU_NEW=8,MENU_OPEN=9,MENU_SAVE=10,MENU_SAVE_AS=11,MENU_QUIT=12,MENU_RECOVERY=13,
    MENU_UNDO=15,MENU_REDO=16,MENU_ALL=17,MENU_FIND=18,MENU_NEXT=19,MENU_REPLACE=20,
    MENU_PROC_NEXT=22,MENU_PROC_PREVIOUS=23,MENU_FOLD=24,
    MENU_CHECK=27,MENU_RUN=28,MENU_STOP=29,MENU_BUILD=30,MENU_INTEGER=31,MENU_OUTPUT=32,MENU_RESTART=33 };
static const OBJECT menu[]={
    {-1,1,6,G_IBOX,0,0,0,0,0,640,240},
    {6,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,25,G_IBOX,0,0,0,8,0,424,11},
    {4,-1,-1,G_TITLE,0,0,(ULONG)"File",0,0,48,11},
    {5,-1,-1,G_TITLE,0,0,(ULONG)"Edit",48,0,48,11},
    {25,-1,-1,G_TITLE,0,0,(ULONG)"Navigate",96,0,80,11},
    {0,7,26,G_IBOX,0,0,0,0,11,640,229},
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
    {26,22,24,G_BOX,0,0,0x1100,104,0,184,33},
    {23,-1,-1,G_STRING,0,0,(ULONG)"Next procedure",0,0,184,11},
    {24,-1,-1,G_STRING,0,0,(ULONG)"Previous procedure",0,11,184,11},
    {21,-1,-1,G_STRING,0,0,(ULONG)"Fold / Unfold",0,22,184,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Program",176,0,72,11},
    {6,27,33,G_BOX,0,0,0x1100,184,0,240,77},
    {28,-1,-1,G_STRING,0,0,(ULONG)"Check    ^Shift Return",0,0,208,11},
    {29,-1,-1,G_STRING,0,0,(ULONG)"Run      ^Return",0,11,208,11},
    {30,-1,-1,G_STRING,0,0,(ULONG)"Stop     ^K",0,22,208,11},
    {31,-1,-1,G_STRING,0,0,(ULONG)"Build    ^B",0,33,208,11},
    {32,-1,-1,G_STRING,0,0,(ULONG)"Integer mode",0,44,208,11},
    {33,-1,-1,G_STRING,0,0,(ULONG)"Output",0,55,240,11},
    {26,-1,-1,G_STRING,LASTOB,0,(ULONG)"Restart interpreter",0,66,240,11}
};
static WORD min(WORD a,WORD b) { return a<b ? a:b; }
static WORD max(WORD a,WORD b) { return a>b ? a:b; }

void BasicEditorDamage(struct BasicEditor *e,UWORD first,UWORD end)
{
    WORD a=BasicAssistanceRow(e,first),b=end>=BASIC_LINES ? e->rows:BasicAssistanceRow(e,end);
    if (a>=b) return;
    BasicEditorRows(e,a,b);
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

static WORD drag_edge(const struct BasicEditor *e,WORD x,WORD y)
{
    return x<e->app.work[0]+4 || x>=e->app.work[0]+4+e->columns*8 ||
        y<e->app.work[1] || y>=e->app.work[1]+e->rows*8;
}

/* One selection step at an edge. The same viewport translation is used by
 * keys, gadgets and this captured gesture; no separate mouse paint path. */
void BasicEditorDrag(struct BasicEditor *e,WORD x,WORD y)
{
    WORD left=e->app.work[0]+4,top=e->app.work[1];
    UWORD first=e->first,column=e->left;
    BasicEditorDamage(e,BasicLine(&e->document,e->anchor<e->caret ? e->anchor:e->caret),
        BasicLine(&e->document,e->anchor>e->caret ? e->anchor:e->caret)+1);
    if (y<top) e->first=BasicAssistancePrevious(e,e->first);
    else if (y>=top+e->rows*8 && e->first<BasicAssistanceTop(e)) e->first=BasicAssistanceNext(e,e->first);
    if (x<left && e->left) --e->left;
    else if (x>=left+e->columns*8 && e->left<BASIC_COLUMNS*8) ++e->left;
    e->caret=BasicEditorPosition(e,min(max(x,left),left+e->columns*8-1),
        min(max(y,top),top+e->rows*8-1));
    BasicEditorDamage(e,BasicLine(&e->document,e->anchor<e->caret ? e->anchor:e->caret),
        BasicLine(&e->document,e->anchor>e->caret ? e->anchor:e->caret)+1);
    BasicEditorReveal(e);
    if (first!=e->first || column!=e->left) BasicEditorRows(e,0,e->rows);
}

WORD BasicEditorKey(struct BasicEditor *e,WORD key,WORD mods)
{
    struct BasicDocument *d=&e->document;UBYTE c=key&255;
    struct BasicMotion *m=&e->motion.state;
    ULONG before=e->caret,at=e->caret,lo=e->anchor<at ? e->anchor:at,hi=e->anchor>at ? e->anchor:at;
    ULONG oldGeneration=d->generation,oldBytes=d->bytes;
    UWORD line=BasicLine(d,at),editFirst=lo==at ? line:BasicLine(d,lo);
    UWORD editLast=hi==at ? line:BasicLine(d,hi),oldLines=d->lines;
    WORD result=0,scan=(UWORD)key>>8,unselected=lo==hi,whole=0,map=0;
    UWORD sourceLine=0,targetLine=0;
    m->editReady=0;
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
        editLast=BasicLine(d,hi);
        whole=lo<hi && lo==d->line[editFirst] && hi==d->line[editLast];
        sourceLine=whole ? editLast:editLast+1;targetLine=whole ? editFirst:editFirst+1;
        map=unselected || whole;
        result=BasicReplace(d,lo,hi-lo,0,0);if (result) return result;
        e->caret=e->anchor=lo;goto edited;
    } else if (c==9 || c==13 || (c>=32 && c<=126 && !(mods&12))) {
        if (c==13) {
            whole=lo==d->line[editFirst] && hi==d->line[editLast];
            sourceLine=whole ? editLast:editLast+1;targetLine=editFirst+2;
            if (whole) targetLine=editFirst+1;
            map=unselected || whole;
            result=BasicAssistanceIndent(e,lo,hi-lo,&at);if (result) return result;
            e->caret=e->anchor=at;goto edited;
        }
        result=BasicReplace(d,lo,hi-lo,&c,1);if (result) return result;
        e->caret=e->anchor=lo+1;goto edited;
    } else return BASIC_OK;
    e->caret=at;if (!(mods&3)) e->anchor=at;
selected:
    if (lo!=hi) BasicEditorDamage(e,BasicLine(d,lo),BasicLine(d,hi)+1);
    BasicEditorDamage(e,BasicLine(d,before),BasicLine(d,before)+1);
    if (e->anchor!=e->caret) BasicEditorDamage(e,
        BasicLine(d,e->anchor<e->caret ? e->anchor:e->caret),
        BasicLine(d,e->anchor>e->caret ? e->anchor:e->caret)+1);
    BasicEditorReveal(e);return BASIC_OK;
edited:
    ++e->edits;
    if (map && oldLines!=d->lines && m->settled && m->linear &&
        m->document==d->data && m->generation==oldGeneration &&
        m->caret==before && (unselected || whole)) {
        m->editBefore=oldGeneration;m->editAfter=d->generation;
        m->editFirst=editFirst;m->editLast=editLast;m->wholeLine=whole;
        m->sourceLine=sourceLine;m->targetLine=targetLine;
        m->lineDelta=(WORD)d->lines-(WORD)oldLines;
        m->byteDelta=(LONG)d->bytes-(LONG)oldBytes;m->editReady=1;
    }
    line=editFirst;
    if (oldLines!=d->lines) BasicEditorDamage(e,line,min(e->first+e->rows,max(oldLines,d->lines)));
    else BasicEditorDamage(e,line,editLast+1);
    BasicEditorReveal(e);return BASIC_OK;
}

WORD BasicEditorRun(struct BasicEditor *e)
{
    WORD quit=0,quitPending=0,result=20;
    /* Each mutable application image owns one editor Task. Keep its event
     * workspace in upper image data, leaving headroom for nested GEM/DOS calls. */
    static WORD events,mx,my,buttons,mods,key,clicks,i,action,x,y;
    static struct ExecAESWaitSpec wait;
    struct BasicApp *a=&e->app;
    mx=my=0;
    BasicAssistanceInit(e);
    if (!BasicOpen(a)) goto finish;
    if (!wind_calc(WC_BORDER,BASIC_WINDOW_KIND,0,0,288,128,&x,&y,&e->minw,&e->minh)) goto finish;
    memcpy(e->menu,menu,sizeof(menu));if (!menu_bar(e->menu,1)) goto finish;
    e->sliderSize=e->sliderPosition=-1;
    if (!viewport(e)) goto finish;
    BasicEditorStatus(e,"Ctrl+O Open  Ctrl+S Save");
    BasicEditorDamage(e,0,BASIC_LINES);result=0;
    while (!quit && !result) {
        memset(&wait,0,sizeof(wait));
        wait.flags=MU_KEYBD|MU_BUTTON|MU_MESAG|(e->dragging ? MU_M1:0)|
            ((e->dirty || BasicFilesWork() || BasicAssistanceWork(e) || BasicBuildWork() ||
                (e->dragging && drag_edge(e,mx,my))) ? MU_TIMER:0);
        if (e->dragging && !e->dirty && drag_edge(e,mx,my)) wait.milliseconds=80;
        wait.buttonClicks=1;wait.buttonMask=1;wait.buttonState=e->dragging ? 0:1;
        wait.m1Flags=1;wait.m1X=mx;wait.m1Y=my;wait.m1Width=wait.m1Height=1;
        wait.signalMask=BasicBuildMask();
        events=ExecAESWait(&wait);
        mx=wait.mouseX;my=wait.mouseY;buttons=wait.mouseButtons;mods=wait.keyState;
        key=wait.key;clicks=wait.clicks;memcpy(a->message,wait.message,sizeof(a->message));
        if (!events) {
            if (ExecAESDiagnostic()==AES_INPUT_LOST) { e->dragging=0;continue; }
            result=20;break;
        }
        action=0;
        if (events&MU_MESAG) {
            WORD *m=a->message;
            if (m[0]==MN_SELECTED) { action=m[4];if (!menu_tnormal(e->menu,m[3],1)) result=20; }
            else if (BasicBuildMessage(e,m)) { }
            else if (m[3]==a->window) switch (m[0]) {
            case WM_CLOSED:
                BasicAssistanceCancel(e);
                if (BasicBuildBusy()) { quitPending=1;BasicBuildStop(); }
                else BasicFilesRequest(BASIC_FILE_QUIT);
                break;
            case WM_TOPPED:if (!wind_set(a->window,WF_TOP,0,0,0,0)) result=20;break;
            case WM_SIZED:
                m[6]=max(e->minw,m[6]);m[7]=max(e->minh,m[7]);
                /* Fall through. */
            case WM_MOVED:
                if (!wind_set(a->window,WF_CXYWH,m[4],m[5],m[6],m[7]) || !viewport(e)) result=20;
                BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);break;
            case WM_REDRAW:BasicEditorExpose(e,m[4],m[5],m[6],m[7]);break;
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
            if ((mods&4) && (key&255)==13) { action=(mods&3) ? MENU_CHECK:MENU_RUN;events&=~MU_KEYBD; }
            switch (key&255) {
            case 11:action=MENU_STOP;break;
            case 2:action=MENU_BUILD;break;
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
        if (action>=MENU_CHECK && action<=MENU_RESTART) {
            BasicBuildRequest(e,action-MENU_CHECK+BASIC_BUILD_CHECK);events&=~MU_KEYBD;action=0;
        }
        if (action==MENU_QUIT && BasicBuildBusy()) {
            quitPending=1;BasicBuildStop();events&=~MU_KEYBD;action=0;
        }
        if ((action==MENU_NEW || action==MENU_OPEN) && BasicBuildBusy()) { events&=~MU_KEYBD;action=0; }
        if (action>=MENU_NEW && action<=MENU_QUIT) {
            BasicAssistanceCancel(e);BasicFilesRequest(action-MENU_NEW+BASIC_FILE_NEW);events&=~MU_KEYBD;
        }
        if (action==MENU_RECOVERY && !BasicBuildRecovery(e)) BasicFilesRequest(BASIC_FILE_RECOVERY);
        if (!BasicBuildBusy() && action>=MENU_FIND && action<=MENU_REPLACE) {
            BasicAssistanceRequest(action-MENU_FIND+BASIC_ASSIST_FIND);events&=~MU_KEYBD;
        }
        if (!BasicBuildBusy() && action>=MENU_PROC_NEXT && action<=MENU_FOLD) {
            BasicAssistanceRequest(action-MENU_PROC_NEXT+BASIC_ASSIST_PROC_NEXT);events&=~MU_KEYBD;
        }
        if (action==MENU_UNDO) { key=26;events|=MU_KEYBD; }
        if (action==MENU_REDO) { key=25;events|=MU_KEYBD; }
        if (action==MENU_ALL) { key=1;events|=MU_KEYBD; }
        if ((events&MU_KEYBD) && !BasicBuildBusy() && !BasicFilesLoading() && !BasicAssistanceBusy()) {
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
                BasicEditorStatus(e,message);
                if (!form_alert(1,"[1][Edit exceeds limits][OK]") &&
                    ExecAESDiagnostic()!=AES_PENDING)
                    wind_set_str(a->window,WF_NAME,"FastBasic - edit rejected");
                if (ExecAESDiagnostic()==AES_PENDING) continue;
            }
            if (!viewport(e)) result=20;
        }
        if ((events&MU_BUTTON) && buttons && ExecAESInputWindow(MU_BUTTON)==a->window) {
            BasicEditorDamage(e,BasicLine(&e->document,e->anchor<e->caret ? e->anchor:e->caret),
                BasicLine(&e->document,e->anchor>e->caret ? e->anchor:e->caret)+1);
            e->caret=BasicEditorPosition(e,mx,my);if (!(mods&3)) e->anchor=e->caret;e->dragging=1;
            BasicEditorDamage(e,BasicLine(&e->document,e->anchor<e->caret ? e->anchor:e->caret),
                BasicLine(&e->document,e->anchor>e->caret ? e->anchor:e->caret)+1);
            BasicEditorReveal(e);
        }
        if (e->dragging && ((events&MU_M1) || ((events&MU_TIMER) && !e->dirty && drag_edge(e,mx,my)))) {
            BasicEditorDrag(e,mx,my);
            if (!viewport(e)) result=20;
        }
        if ((events&MU_BUTTON) && !buttons) e->dragging=0;
        BasicBuildStep(e);
        if (quitPending && !BasicBuildBusy()) { quitPending=0;BasicFilesRequest(BASIC_FILE_QUIT); }
        if (BasicFilesWork()) {
            i=BasicFilesStep(e);if (i==1) break;if (i==2) continue;
            if (!viewport(e)) result=20;
        }
        if (BasicAssistanceWork(e)) {
            i=BasicAssistanceStep(e);if (i==2) continue;
            if (i==1 && !viewport(e)) result=20;
        }
        if (e->dirty && !BasicEditorPaint(e)) result=20;
    }
finish:
    BasicBuildDispose();
    BasicAssistanceDispose();
    BasicFilesDispose();
    if (!BasicClose(a)) result=20;
    return result;
}
