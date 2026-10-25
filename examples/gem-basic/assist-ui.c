/* SPDX-License-Identifier: MIT */
#include "assist-ui.h"
#include "assist.h"
#include <exec816/aes.h>
#include <string.h>
static struct {
    struct BasicAssist index;
    struct BasicFind find;
    struct BasicReplaceJob replace;
    UBYTE *data;
    UWORD visible,sourceLines;
    WORD request,finding,wrapped;
    char needle[81],replacement[81];
    OBJECT dialog[8];TEDINFO fields[2];
    UBYTE lexical[BASIC_COLUMNS+1];
} ui;
static const OBJECT dialog[]={
    {-1,1,7,G_BOX,0,0,0x1170,0,0,400,100},
    {2,-1,-1,G_STRING,0,0,(ULONG)"Find:",12,20,64,8},
    {3,-1,-1,G_BOXTEXT,EDITABLE,0,0,80,16,304,16},
    {4,-1,-1,G_STRING,0,0,(ULONG)"Replace:",12,44,64,8},
    {5,-1,-1,G_BOXTEXT,EDITABLE,0,0,80,40,304,16},
    {6,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT,0,(ULONG)"Find Next",12,72,112,16},
    {7,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"All",140,72,112,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|EXIT|LASTOB,0,(ULONG)"Cancel",276,72,112,16}
};
static WORD current(const struct BasicEditor *e)
{ return ui.data==e->document.data && ui.index.generation==e->document.generation; }
static void status(struct BasicEditor *e,const char *text)
{ BasicEditorStatus(e,text); }
static void count_visible(const struct BasicEditor *e)
{
    UWORD i;ui.visible=ui.sourceLines=e->document.lines;
    for (i=0;i<e->document.lines;++i) if (BasicHidden(&ui.index,i)) --ui.visible;
}
void BasicAssistanceInit(struct BasicEditor *e)
{
    WORD i;memset(&ui,0,sizeof(ui));ui.data=e->document.data;ui.visible=ui.sourceLines=e->document.lines;
    BasicAssistBegin(&ui.index,&e->document);memcpy(ui.dialog,dialog,sizeof(dialog));
    for (i=0;i<2;++i) {
        ui.fields[i].te_ptext=(ULONG)(i ? ui.replacement:ui.needle);
        ui.fields[i].te_ptmplt=(ULONG)"";ui.fields[i].te_pvalid=(ULONG)"X";
        ui.fields[i].te_font=IBM;ui.fields[i].te_just=TE_LEFT;ui.fields[i].te_color=0x1180;
        ui.fields[i].te_thickness=-1;ui.fields[i].te_txtlen=81;ui.fields[i].te_tmplen=1;
        ui.dialog[i ? 4:2].ob_spec=(ULONG)&ui.fields[i];
    }
}
void BasicAssistanceDispose(void) { BasicReplaceCancel(&ui.replace);ui.finding=ui.request=0;ui.data=0; }
void BasicAssistanceRequest(WORD action) { ui.request=action; }
void BasicAssistanceCancel(struct BasicEditor *e)
{
    WORD active=ui.replace.phase || ui.finding || ui.request;
    BasicReplaceCancel(&ui.replace);ui.finding=ui.request=0;
    if (active) status(e,"Search/replacement cancelled");
}
WORD BasicAssistanceBusy(void) { return ui.replace.phase!=0; }
WORD BasicAssistanceIndent(struct BasicEditor *e,ULONG at,ULONG removed,ULONG *caret)
{
    /* Painting and edits run sequentially in this Task. Reuse the pen buffer
     * through BasicReplace, including its cooperative gap moves. */
    return BasicIndent(&e->document,at,removed,caret,ui.lexical);
}
WORD BasicAssistanceWork(const struct BasicEditor *e)
{ return !current(e) || ui.index.scan<e->document.lines || ui.request || ui.finding || ui.replace.phase; }
UWORD BasicAssistanceLine(const struct BasicEditor *e,UWORD row)
{ return current(e) ? BasicVisible(&ui.index,e->first,row):e->first+row; }
UWORD BasicAssistanceRow(const struct BasicEditor *e,UWORD line)
{
    UWORD row=0;
    if (line<=e->first) return 0;
    while (row<e->rows && BasicAssistanceLine(e,row)<line) ++row;
    return row;
}
UWORD BasicAssistancePrevious(const struct BasicEditor *e,UWORD line)
{
    if (line) --line;
    while (line && current(e) && BasicHidden(&ui.index,line)) --line;
    return line;
}
UWORD BasicAssistanceNext(const struct BasicEditor *e,UWORD line)
{ return current(e) ? BasicVisible(&ui.index,line,1):line+1; }
UWORD BasicAssistanceTop(const struct BasicEditor *e)
{
    UWORD line=e->document.lines-1,n=e->rows;
    while (current(e) && line && BasicHidden(&ui.index,line)) --line;
    while (--n && line) line=BasicAssistancePrevious(e,line);
    return line;
}
UWORD BasicAssistanceCount(const struct BasicEditor *e)
{ return current(e) ? ui.visible:e->document.lines; }
void BasicAssistanceReveal(struct BasicEditor *e,UWORD line)
{
    UWORD n;
    if (current(e) && BasicHidden(&ui.index,line)) {
        BasicUnfold(&ui.index,line);count_visible(e);BasicEditorDamage(e,0,BASIC_LINES);
    }
    if (line<e->first) e->first=line;
    if (BasicAssistanceRow(e,line)>=e->rows) {
        e->first=line;n=e->rows;
        while (--n && e->first) e->first=BasicAssistancePrevious(e,e->first);
    }
}
void BasicAssistanceSelect(struct BasicEditor *e,ULONG at,ULONG length)
{
    e->anchor=at;e->caret=at+length;
    BasicAssistanceReveal(e,BasicLine(&e->document,at));
    BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);
}
/* Read the line once. Retain only its tab positions while the same scratch
 * bytes become lexical colours; source text is already in the retained row. */
UBYTE BasicAssistanceCompose(struct BasicEditor *e,UWORD line)
{
    ULONG start,end;UWORD byte,count,col=0,next,i=0;UBYTE c,uniform,*tabs=e->motion.state.tabs;
    memset(e->row,' ',e->columns);e->row[e->columns]=0;
    memset(e->colors,BASIC_LEX_TEXT,e->columns);
    e->motion.state.composedLength=0;
    if (line>=e->document.lines) return BASIC_LEX_TEXT;
    start=e->document.line[line];end=e->document.line[line+1];
    if (end>start && BasicByte(&e->document,end-1)==10) --end;
    count=end-start;BasicCopy(&e->document,start,ui.lexical,count);memset(tabs,0,32);
    e->motion.state.composedLength=count;
    for (byte=0;byte<count && i<e->columns;++byte) {
        c=ui.lexical[byte];
        if (c==9) tabs[byte>>3]|=1U<<(byte&7);
        next=c==9 ? (col+8)&~7U:col+1;
        while (col<next) { if (col>=e->left) e->row[i++]=c==9 ? ' ':c;++col;if (i==e->columns) break; }
    }
    uniform=BasicLexBytes(ui.lexical,count,ui.lexical);col=i=0;
    for (byte=0;byte<count && i<e->columns;++byte) {
        next=(tabs[byte>>3]&(1U<<(byte&7))) ? (col+8)&~7U:col+1;
        while (col<next) { if (col>=e->left) e->colors[i++]=ui.lexical[byte];++col;if (i==e->columns) break; }
    }
    return uniform;
}
static WORD choose(struct BasicEditor *e)
{
    WORD x,y,w,h,result,i,width=e->app.work[2]<400 ? e->app.work[2]:400;UWORD diagnostic;
    ui.dialog[0].ob_width=width;
    ui.dialog[2].ob_width=ui.dialog[4].ob_width=width-96;
    for (i=0;i<3;++i) { ui.dialog[5+i].ob_x=12+i*((width-24)/3);ui.dialog[5+i].ob_width=(width-48)/3; }
    if (!form_center(ui.dialog,&x,&y,&w,&h) || !form_dial(FMD_START,0,0,0,0,x,y,w,h)) return -1;
    result=form_do(ui.dialog,2);diagnostic=ExecAESDiagnostic();
    if (result>=0) { result&=0x7fff;ui.dialog[result].ob_state&=~SELECTED; }
    if (!form_dial(FMD_FINISH,0,0,0,0,x,y,w,h)) return -1;
    return diagnostic==AES_PENDING ? -2:result;
}
WORD BasicAssistanceStep(struct BasicEditor *e)
{
    WORD step,action;UWORD line,i,index;
    if (!current(e)) {
        WORD repaint=ui.data!=e->document.data || ui.visible<ui.sourceLines;
        BasicReplaceCancel(&ui.replace);ui.finding=0;ui.data=e->document.data;
        BasicAssistBegin(&ui.index,&e->document);ui.visible=ui.sourceLines=e->document.lines;
        if (repaint) BasicEditorDamage(e,0,BASIC_LINES);
    }
    if (ui.index.scan<e->document.lines) {
        /* Finish accepted edits on screen before spending a turn indexing
         * unrelated lines. Lexical paint does not depend on this index. */
        if (!e->dirty) BasicAssistStep(&ui.index,&e->document);
        return 0;
    }
    if (ui.replace.phase) {
        step=BasicReplaceStep(&ui.replace,&e->document);
        if (step) {
            status(e,step<0 ? "Replacement rejected (source, capacity or undo limit)":"Replaced matches as one undo group");
            e->caret=e->anchor=ui.replace.first;BasicEditorReveal(e);return 1;
        }
        return 0;
    }
    if (ui.finding) {
        step=BasicFindStep(&ui.find,&e->document);
        if (step==1) { ui.finding=0;BasicAssistanceSelect(e,ui.find.result,ui.find.length);status(e,"Match selected");return 1; }
        else if (step<0) {
            if (!ui.wrapped && ui.find.start) {
                ui.wrapped=1;BasicFindBegin(&ui.find,&e->document,(UBYTE *)ui.needle,strlen(ui.needle),0,1);
            } else { ui.finding=0;status(e,"No match"); }
        }
        return 0;
    }
    action=ui.request;if (!action) return 0;
    if (action==BASIC_ASSIST_FIND || action==BASIC_ASSIST_REPLACE || (action==BASIC_ASSIST_NEXT && !*ui.needle)) {
        step=choose(e);if (step==-2) return 2;
        ui.request=0;
        if (step!=5 && step!=6) return 0;
        action=step==5 ? BASIC_ASSIST_NEXT:BASIC_ASSIST_REPLACE;
    } else ui.request=0;
    if (action==BASIC_ASSIST_REPLACE) {
        step=BasicReplaceBegin(&ui.replace,&e->document,(UBYTE *)ui.needle,strlen(ui.needle),
            (UBYTE *)ui.replacement,strlen(ui.replacement),1);
        status(e,step ? "Enter a nonempty search (80 bytes maximum)":"Replacing - Escape cancels");return 0;
    }
    if (action==BASIC_ASSIST_NEXT) {
        step=BasicFindBegin(&ui.find,&e->document,(UBYTE *)ui.needle,strlen(ui.needle),e->caret,1);
        ui.finding=!step;ui.wrapped=0;status(e,step ? "Enter a nonempty search":"Finding - Escape cancels");return 0;
    }
    line=BasicLine(&e->document,e->caret);index=0xffff;
    for (i=0;i<ui.index.count;++i) {
        if (ui.index.procedures[i].first<=line) index=i;
        if (action==BASIC_ASSIST_PROC_NEXT && ui.index.procedures[i].first>line) { index=i;break; }
    }
    if (action==BASIC_ASSIST_PROC_PREVIOUS && index!=0xffff && ui.index.procedures[index].first==line)
        index=index ? index-1:0xffff;
    if (action==BASIC_ASSIST_PROC_NEXT && (index==0xffff || ui.index.procedures[index].first<=line)) index=0xffff;
    if (index==0xffff) { status(e,"No procedure in that direction");return 0; }
    if (action==BASIC_ASSIST_FOLD) {
        if (BasicFold(&ui.index,index)) {
            count_visible(e);e->caret=e->anchor=e->document.line[ui.index.procedures[index].first];
            BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);status(e,"Procedure fold changed (source is unchanged)");
        } else status(e,"Unfinished procedure has no fold");
    } else BasicAssistanceSelect(e,e->document.line[ui.index.procedures[index].first],0);
    if (ui.index.overflow) status(e,"Procedure index limited to 256 entries");
    return 1;
}
