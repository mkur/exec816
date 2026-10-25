/* SPDX-License-Identifier: MIT */
#include "editor.h"
#include "assist-ui.h"
#include "assist.h"
#include <exec816/aes.h>
#include <exec816/vdi.h>
#include <string.h>

enum { CANDIDATE=1,VALID=2,BASE_DIRTY=4,SELECTED_CELL=16,CARET_CELL=32,CELL_BUDGET=96,ROW_BUDGET=4 };
static WORD min(WORD a,WORD b) { return a<b ? a:b; }
static WORD max(WORD a,WORD b) { return a>b ? a:b; }

static struct BasicRefresh *state(struct BasicEditor *e)
{
    struct BasicRefresh *r=&e->refresh.state;UWORD row;
    if (!r->initialized) {
        memset(r,0,sizeof(*r));
        for (row=0;row<BASIC_VIEW_ROWS;++row) r->first[row]=r->forceFirst[row]=BASIC_VIEW_COLUMNS;
        r->statusFirst=r->statusForceFirst=BASIC_VIEW_COLUMNS;r->initialized=1;
    }
    return r;
}
static void changed(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);
    if (!++r->generation) ++r->generation;
    e->dirty=e->publish=1;
}
void BasicEditorRows(struct BasicEditor *e,UWORD first,UWORD end)
{
    struct BasicRefresh *r=state(e);UWORD row;
    end=min(end,e->rows);if (first>=end) return;
    if (!e->dirty) { e->damageFirst=first;e->damageEnd=end; }
    else { e->damageFirst=min(first,e->damageFirst);e->damageEnd=max(end,e->damageEnd); }
    for (row=first;row<end;++row) {
        /* A whole-viewport nomination also covers fold-map changes, which
         * do not advance the source document generation. */
        if (!first && end==e->rows) r->valid[row]|=CANDIDATE|BASE_DIRTY;
        else r->valid[row]|=CANDIDATE;
    }
    changed(e);
}
void BasicEditorStatus(struct BasicEditor *e,const char *text)
{
    UWORD n=strlen(text);if (n>BASIC_VIEW_COLUMNS) n=BASIC_VIEW_COLUMNS;
    if (e->status!=text) { memcpy(e->status,text,n);e->status[n]=0; }
    state(e)->statusState|=CANDIDATE;
    changed(e); /* The saved-generation marker may have changed too. */
}
static void interval(UBYTE *first,UBYTE *end,UWORD a,UWORD b)
{
    if (a>=b) return;
    if (a<*first) *first=a;if (b>*end) *end=b;
}
static void force_all(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    for (row=0;row<e->rows;++row) { r->forceFirst[row]=0;r->forceEnd[row]=e->columns; }
    r->statusForceFirst=0;r->statusForceEnd=e->columns;r->padding=15;r->paddingVisit=0;e->dirty=1;
}
static void force_text(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    for (row=0;row<e->rows;++row) { r->forceFirst[row]=0;r->forceEnd[row]=e->columns; }
    e->motion.state.applied=e->motion.state.settled=e->motion.state.prepared=0;
    e->dirty=e->publish=1;
}
void BasicEditorExpose(struct BasicEditor *e,WORD x,WORD y,WORD w,WORD h)
{
    struct BasicRefresh *r=state(e);WORD row,a,b,top,left=e->app.work[0]+4;
    if (e->motion.state.applied) force_text(e);
    r->hidden=0;e->motion.state.settled=e->motion.state.prepared=0;
    a=max(0,(x-left)/e->app.cellw);b=min(e->columns,(x+w-left+e->app.cellw-1)/e->app.cellw);
    for (row=0;row<e->rows;++row) {
        top=e->app.work[1]+row*e->app.cellh;
        if (a<b && y<top+e->app.cellh && y+h>top)
            interval(&r->forceFirst[row],&r->forceEnd[row],a,b);
    }
    top=e->app.work[1]+e->rows*e->app.cellh+4;
    if (a<b && y<top+8 && y+h>top) interval(&r->statusForceFirst,&r->statusForceEnd,a,b);
    if (x<left || x+w>left+e->columns*e->app.cellw || y+h>top-4) { r->padding=15;r->paddingVisit=0; }
    e->dirty=1;
}

static void remember(struct BasicEditor *e)
{
    struct BasicMotion *m=&e->motion.state;UWORD row,line;
    const struct AESWindowView *view=ExecAESWindowView(e->app.window);
    m->document=e->document.data;m->generation=e->document.generation;
    m->caret=e->caret;m->anchor=e->anchor;
    m->top=e->first;m->left=e->left;m->rows=e->rows;m->columns=e->columns;
    memcpy(m->work,e->app.work,sizeof(m->work));
    m->epoch=view ? view->paintEpoch:0;
    m->linear=1;
    for (row=0;row<e->rows;++row) {
        line=BasicAssistanceLine(e,row);m->line[row]=line;
        m->offset[row]=line<e->document.lines ? e->document.line[line]:e->document.bytes;
        if (line!=e->first+row) m->linear=0;
    }
    m->settled=!e->refresh.state.hidden;
    m->prepared=m->applied=m->editReady=0;
}

/* Nominations describe a newer model, while this identity describes the last
 * complete screen. A partial paint/exposure retires it before any later copy. */
WORD BasicEditorTranslation(struct BasicEditor *e)
{
    struct BasicMotion *m=&e->motion.state;WORD rows,columns;UWORD row;
    m->prepared=0;
    if (!m->settled || !m->linear || m->document!=e->document.data ||
        m->generation!=e->document.generation || m->rows!=e->rows ||
        m->columns!=e->columns || memcmp(m->work,e->app.work,sizeof(m->work))) return 0;
    if (m->top==e->first && m->left==e->left) return 0;
    for (row=0;row<e->rows;++row) if (BasicAssistanceLine(e,row)!=e->first+row) return 0;
    rows=(WORD)m->top-(WORD)e->first;columns=(WORD)m->left-(WORD)e->left;
    m->sourceRow=max(0,-rows);m->targetRow=max(0,rows);
    m->sourceColumn=max(0,-columns);m->targetColumn=max(0,columns);
    m->copyRows=e->rows-max(m->sourceRow,m->targetRow);
    m->copyColumns=e->columns-max(m->sourceColumn,m->targetColumn);
    if (m->copyRows<=0 || m->copyColumns<=0) return 0;
    m->prepared=1;return 1;
}

static void geometry(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    if (r->document==e->document.data && r->top==e->first && r->left==e->left &&
        r->rows==e->rows && r->columns==e->columns && !memcmp(r->work,e->app.work,sizeof(r->work))) return;
    if (r->document==e->document.data && r->rows==e->rows && r->columns==e->columns &&
        !memcmp(r->work,e->app.work,sizeof(r->work))) {
        r->top=e->first;r->left=e->left;
        for (row=0;row<e->rows;++row) r->valid[row]=CANDIDATE|BASE_DIRTY;
        force_text(e);changed(e);return;
    }
    e->motion.state.applied=e->motion.state.settled=e->motion.state.prepared=0;
    r->document=e->document.data;r->top=e->first;r->left=e->left;r->rows=e->rows;r->columns=e->columns;
    memcpy(r->work,e->app.work,sizeof(r->work));r->hidden=0;
    for (row=0;row<BASIC_VIEW_ROWS;++row) {
        r->first[row]=r->forceFirst[row]=BASIC_VIEW_COLUMNS;r->end[row]=r->forceEnd[row]=0;
        r->valid[row]=row<e->rows ? CANDIDATE:0;
    }
    r->statusFirst=0;r->statusEnd=e->columns;r->statusState=CANDIDATE;force_all(e);changed(e);
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
static void compose(struct BasicEditor *e,UWORD row)
{
    struct BasicRefresh *r=state(e);UWORD line=BasicAssistanceLine(e,row),i;
    UBYTE *text=r->text[row],*attributes=r->attributes[row];
    WORD source=!(r->valid[row]&VALID) || (r->valid[row]&BASE_DIRTY) || r->documentGeneration!=e->document.generation;
    ULONG lo=e->anchor<e->caret ? e->anchor:e->caret,hi=e->anchor>e->caret ? e->anchor:e->caret;
    ULONG at,start,finish;WORD first,last;
    if (source) { row_text(e,line);BasicAssistanceColors(e,line,e->colors); }
    else for (i=0;i<e->columns;++i) e->colors[i]=attributes[i]&15;
    if (line<e->document.lines) {
        if (lo<hi && lo<e->document.line[line+1] && hi>e->document.line[line]) {
            at=lo>e->document.line[line] ? lo:e->document.line[line];start=BasicColumn(&e->document,at);
            at=hi<e->document.line[line+1] ? hi:e->document.line[line+1];
            if (at>e->document.line[line] && at<=e->document.bytes && BasicByte(&e->document,at-1)==10) --at;
            finish=BasicColumn(&e->document,at);if (hi>at) ++finish;
            first=max(0,(WORD)start-e->left);last=min(e->columns,(WORD)finish-e->left);
            if (first<last) for (i=first;i<last;++i) e->colors[i]|=SELECTED_CELL;
        }
        if (line==BasicLine(&e->document,e->caret)) {
            start=BasicColumn(&e->document,e->caret);
            if (start>=e->left && start<e->left+e->columns) e->colors[start-e->left]|=CARET_CELL;
        }
    }
    for (i=0;i<e->columns;++i) {
        if (!(r->valid[row]&VALID) || (source && text[i]!=(UBYTE)e->row[i]) || attributes[i]!=e->colors[i])
            interval(&r->first[row],&r->end[row],i,i+1);
        if (source) text[i]=e->row[i];attributes[i]=e->colors[i];
    }
    r->valid[row]=VALID;
}
static void compose_status(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD n,i;
    memset(e->row,' ',e->columns);e->row[0]=BasicDirty(&e->document) ? '*':' ';
    if (e->columns>2) { n=strlen(e->status);if (n>e->columns-2) n=e->columns-2;memcpy(e->row+2,e->status,n); }
    for (i=0;i<e->columns;++i) {
        if (r->status[i]!=(UBYTE)e->row[i]) interval(&r->statusFirst,&r->statusEnd,i,i+1);
        r->status[i]=e->row[i];
    }
    r->statusState=VALID;
}
static WORD candidates(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    for (row=0;row<e->rows;++row) if (r->valid[row]&CANDIDATE) return 1;
    return 0;
}
static WORD pending(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    if (r->padding || r->statusEnd || r->statusForceEnd) return 1;
    for (row=0;row<e->rows;++row) if (r->end[row] || r->forceEnd[row]) return 1;
    return 0;
}
static void bounds(struct BasicEditor *e,UWORD row,UWORD first,UWORD end,WORD *rect)
{
    rect[0]=e->app.work[0]+4+first*e->app.cellw;
    rect[1]=e->app.work[1]+(row==e->rows ? e->rows*e->app.cellh+4:row*e->app.cellh);
    rect[2]=e->app.work[0]+4+end*e->app.cellw;rect[3]=rect[1]+8;
}
static WORD intersection(const WORD *a,const WORD *b,WORD *out)
{
    out[0]=max(a[0],b[0]);out[1]=max(a[1],b[1]);
    out[2]=min(a[2],b[0]+b[2]);out[3]=min(a[3],b[1]+b[3]);
    return out[0]<out[2] && out[1]<out[3];
}
static WORD visible(struct BasicEditor *e,UWORD index,WORD *rect)
{
    UWORD i;
    if (!wind_get(e->app.window,WF_FIRSTXYWH,&rect[0],&rect[1],&rect[2],&rect[3])) return 0;
    for (i=0;i<index && rect[2] && rect[3];++i)
        if (!wind_get(e->app.window,WF_NEXTXYWH,&rect[0],&rect[1],&rect[2],&rect[3])) return 0;
    return 1;
}
static WORD complete(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row,first,end,cells=0,rows=0,reports=0;
    WORD rect[4],clip[4],view[4];ULONG area;
    if (candidates(e) || r->padding) return 0;
    for (row=0;row<=e->rows;++row) {
        first=row==e->rows ? min(r->statusFirst,r->statusForceFirst):min(r->first[row],r->forceFirst[row]);
        end=row==e->rows ? max(r->statusEnd,r->statusForceEnd):max(r->end[row],r->forceEnd[row]);
        if (first>=end) continue;
        if (++rows>ROW_BUDGET) return 0;
        bounds(e,row,first,end,rect);area=0;
        if (!visible(e,0,view)) return -1;
        while (view[2] && view[3]) {
            if (intersection(rect,view,clip)) {
                area+=(ULONG)(clip[2]-clip[0])*(clip[3]-clip[1]);
                cells+=(clip[2]-rect[0]+7)/8-(clip[0]-rect[0])/8;
                if (++reports>AES_PAINT_REPORTS || cells>CELL_BUDGET) return 0;
            }
            if (!wind_get(e->app.window,WF_NEXTXYWH,&view[0],&view[1],&view[2],&view[3])) return -1;
        }
        if (area!=(ULONG)(rect[2]-rect[0])*8) return 0;
    }
    return 1;
}
struct Paint {
    struct BasicEditor *e;
    UWORD cells,rows,reports,visibleCount,paddingVisit,fills;
    WORD okay,drawn,locked;
};
static WORD begin(struct Paint *p)
{
    WORD view[4];
    if (!ExecAESBeginUpdate(p->e->app.window)) return 0;
    p->locked=1;p->reports=p->visibleCount=0;
    if (!ExecAESInvalidate(p->e->app.window,0,0,0,0)) return 0;
    if (!visible(p->e,0,view)) return 0;
    while (view[2] && view[3]) {
        ++p->visibleCount;
        if (!wind_get(p->e->app.window,WF_NEXTXYWH,&view[0],&view[1],&view[2],&view[3])) return 0;
    }
    return 1;
}
static WORD report(struct Paint *p,const WORD *clip)
{
    ++p->reports;
    return ExecAESPainted(p->e->app.window,clip[0],clip[1],clip[2]-clip[0],clip[3]-clip[1]);
}
static WORD room(struct Paint *p)
{
    if (p->reports<AES_PAINT_REPORTS) return 1;
    p->locked=0;
    if (!wind_update(END_UPDATE)) { p->okay=0;return 0; }
    if (!begin(p)) { p->okay=0;return 0; }
    return 1;
}
static void text_fragment(struct Paint *p,UWORD row,UWORD first,UWORD end,WORD *clip)
{
    struct BasicEditor *e=p->e;struct BasicRefresh *r=state(e);UWORD col,stop,i;WORD box[4],top;
    UBYTE *text=row==e->rows ? r->status:r->text[row];UBYTE pen;char saved;
    vs_clip(e->app.vdi,1,clip);memcpy(e->row,text,e->columns);e->row[e->columns]=0;
    top=e->app.work[1]+(row==e->rows ? e->rows*e->app.cellh+4:row*e->app.cellh);
    col=first;
    while (col<end) {
        pen=row==e->rows ? 1:r->attributes[row][col]&15;stop=col+1;
        while (stop<end && (row==e->rows || (r->attributes[row][stop]&15)==pen)) ++stop;
        saved=e->row[stop];e->row[stop]=0;vst_color(e->app.vdi,pen);
        v_gtext(e->app.vdi,e->app.work[0]+4+col*e->app.cellw,top+6,e->row+col);
        e->row[stop]=saved;col=stop;
    }
    if (row<e->rows) for (i=first;i<end;++i) {
        box[0]=e->app.work[0]+4+i*e->app.cellw;box[2]=box[0]+e->app.cellw-1;
        if (r->attributes[row][i]&SELECTED_CELL) {
            box[1]=box[3]=top+7;vsf_color(e->app.vdi,3);v_bar(e->app.vdi,box);
        }
        if (r->attributes[row][i]&CARET_CELL) {
            box[2]=box[0];box[1]=top;box[3]=top+7;vsf_color(e->app.vdi,1);v_bar(e->app.vdi,box);
        }
    }
    p->okay=ExecAESDiagnostic()==AES_OK;
}
static WORD span(struct Paint *p,UWORD row,UWORD first,UWORD end)
{
    struct BasicEditor *e=p->e;struct BasicRefresh *r=state(e);UWORD i,cost;WORD rect[4],clip[4],inclusive[4],view[4];
    bounds(e,row,first,end,rect);
    for (i=0;p->okay && i<p->visibleCount;++i) {
        if (!visible(e,i,view)) { p->okay=0;return 0; }
        if (!intersection(rect,view,clip)) continue;
        if (!room(p)) return 0;
        /* Re-read this fragment after a journal rollover obtains a fresh view. */
        if (!visible(e,i,view)) { p->okay=0;return 0; }
        if (!intersection(rect,view,clip)) continue;
        cost=(clip[2]-rect[0]+7)/8-(clip[0]-rect[0])/8;
        if (cost>p->cells) return 0; /* Visibility may grow at a journal rollover. */
        inclusive[0]=clip[0];inclusive[1]=clip[1];inclusive[2]=clip[2]-1;inclusive[3]=clip[3]-1;
        if (!ExecAESInvalidate(e->app.window,clip[0],clip[1],clip[2]-clip[0],clip[3]-clip[1])) { p->okay=0;return 0; }
        text_fragment(p,row,first,end,inclusive);
        if (p->okay) p->okay=report(p,clip);
        if (!p->okay) return 0;
        p->cells-=cost;r->glyphs+=cost;if (row==e->rows) r->statusGlyphs+=cost;p->drawn=1;
    }
    return p->okay;
}

/* A completed copy remains a presentation transaction until the strips and
 * overlays are repaired. Every reacquisition checks its epoch and visibility. */
static WORD copy_view(struct BasicEditor *e,WORD settled)
{
    const struct AESWindowView *v=ExecAESWindowView(e->app.window);
    struct BasicMotion *m=&e->motion.state;
    WORD x=e->app.work[0]+4,y=e->app.work[1];
    if (!v || v->paintEpoch!=m->epoch || (settled && !v->pixelsReady) || v->visibleCount!=1) return 0;
    return v->visible[0].left<=x && v->visible[0].top<=y &&
        v->visible[0].right>=x+e->columns*8 && v->visible[0].bottom>=y+e->rows*8;
}

static void shift_cells(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);struct BasicMotion *m=&e->motion.state;
    WORD i,src,dst,row;UWORD caretRow=BasicAssistanceRow(e,BasicLine(&e->document,e->caret));
    WORD overlays=m->anchor!=m->caret || e->anchor!=e->caret;
    for (i=0;i<m->copyRows;++i) {
        row=m->targetRow>m->sourceRow ? m->copyRows-1-i:i;
        src=m->sourceRow+row;dst=m->targetRow+row;
        memmove(r->text[dst]+m->targetColumn,r->text[src]+m->sourceColumn,m->copyColumns);
        memmove(r->attributes[dst]+m->targetColumn,r->attributes[src]+m->sourceColumn,m->copyColumns);
    }
    for (row=0;row<e->rows;++row) {
        r->first[row]=r->forceFirst[row]=BASIC_VIEW_COLUMNS;r->end[row]=r->forceEnd[row]=0;
        if (row<m->targetRow || row>=m->targetRow+m->copyRows) {
            r->valid[row]=CANDIDATE|BASE_DIRTY;r->forceFirst[row]=0;r->forceEnd[row]=e->columns;
        } else {
            r->valid[row]=VALID;
            if (m->copyColumns!=e->columns) {
                r->valid[row]|=CANDIDATE|BASE_DIRTY;
                if (m->targetColumn) interval(&r->forceFirst[row],&r->forceEnd[row],0,m->targetColumn);
                else interval(&r->forceFirst[row],&r->forceEnd[row],m->copyColumns,e->columns);
            }
            if (overlays || row==caretRow) r->valid[row]|=CANDIDATE;
        }
    }
    r->documentGeneration=e->document.generation;
    r->top=e->first;r->left=e->left;r->hidden=0;
    m->top=e->first;m->left=e->left;m->generation=e->document.generation;
    m->caret=e->caret;m->anchor=e->anchor;
    m->applied=1;m->settled=m->prepared=0;e->publish=0;
}

static WORD move_pixels(struct Paint *p)
{
    struct BasicEditor *e=p->e;struct BasicMotion *m=&e->motion.state;
    struct BasicRefresh *r=state(e);WORD box[4],inclusive[4],result;UWORD row,col;
    if (!copy_view(e,1)) { ++m->fallbacks;return EXEC_VDI_COPY_REDRAW; }
    bounds(e,0,0,e->columns,box);box[3]=e->app.work[1]+e->rows*8;
    if (!ExecAESInvalidate(e->app.window,box[0],box[1],box[2]-box[0],box[3]-box[1])) return EXEC_VDI_COPY_ERROR;
    /* The text caret is an application overlay. Erase its old source pixel
     * before translation; selection travels with text and is compared later. */
    for (row=0;row<e->rows;++row) for (col=0;col<e->columns;++col)
        if (r->attributes[row][col]&CARET_CELL) {
            r->attributes[row][col]&=~CARET_CELL;
            if (!span(p,row,col,col+1)) return EXEC_VDI_COPY_ERROR;
            ++p->rows;
        }
    inclusive[0]=box[0];inclusive[1]=box[1];inclusive[2]=box[2]-1;inclusive[3]=box[3]-1;
    vs_clip(e->app.vdi,1,inclusive);
    result=ExecVDICopyRect(e->app.vdi,box[0]+m->sourceColumn*8,box[1]+m->sourceRow*8,
        m->copyColumns*8,m->copyRows*8,(m->targetColumn-m->sourceColumn)*8,(m->targetRow-m->sourceRow)*8);
    if (result!=EXEC_VDI_COPY_DONE) { force_text(e);return result; }
    ++m->copies;m->copyPixels+=(ULONG)m->copyColumns*m->copyRows*64;
    ++r->publications;p->drawn=1;shift_cells(e);return result;
}

static WORD will_finish(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row;
    if (candidates(e) || (r->padding&~r->paddingAdvance)) return 0;
    for (row=0;row<e->rows;++row)
        if (max(r->end[row],r->forceEnd[row])>r->advance[row]) return 0;
    return max(r->statusEnd,r->statusForceEnd)<=r->advance[e->rows];
}
static void margin_bounds(struct BasicEditor *e,UWORD i,WORD *box)
{
    WORD x=e->app.work[0],y=e->app.work[1],right=x+e->app.work[2],bottom=y+e->app.work[3];
    WORD grid=x+4+e->columns*e->app.cellw,status=y+e->rows*e->app.cellh;
    box[0]=i==0 ? x:i==1 ? grid:x+4;
    box[1]=i<2 ? y:i==2 ? status:status+12;
    box[2]=i==0 ? x+4:i==1 ? right:grid;
    box[3]=i<2 ? bottom:i==2 ? status+4:bottom;
}
static WORD invalidate(struct BasicEditor *e,const WORD *box)
{
    return ExecAESInvalidate(e->app.window,box[0],box[1],box[2]-box[0],box[3]-box[1]);
}
/* Publish logical obligations without including unrelated status or margins.
 * Candidate rows not composed yet retain a bounded conservative text repair. */
static WORD deferred(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row,a=e->rows,b=0,first=e->columns,end=0,i;
    WORD box[4];
    for (row=0;row<e->rows && !e->motion.state.applied;++row) {
        if (r->valid[row]&CANDIDATE) { r->forceFirst[row]=0;r->forceEnd[row]=e->columns; }
        if (r->end[row] || r->forceEnd[row]) {
            a=min(a,row);b=row+1;
            first=min(first,min(r->first[row],r->forceFirst[row]));
            end=max(end,max(r->end[row],r->forceEnd[row]));
        }
    }
    if (a<b) {
        for (row=a;row<b;++row) interval(&r->forceFirst[row],&r->forceEnd[row],first,end);
        bounds(e,a,first,end,box);box[3]=e->app.work[1]+b*e->app.cellh;
        if (!invalidate(e,box)) return 0;
    }
    first=min(r->statusFirst,r->statusForceFirst);end=max(r->statusEnd,r->statusForceEnd);
    if (first<end) {
        interval(&r->statusForceFirst,&r->statusForceEnd,first,end);
        bounds(e,e->rows,first,end,box);if (!invalidate(e,box)) return 0;
    }
    for (i=0;i<4;++i) if (r->padding&(1<<i)) {
        margin_bounds(e,i,box);if (!invalidate(e,box)) return 0;
    }
    return 1;
}
static void margins(struct Paint *p)
{
    struct BasicEditor *e=p->e;struct BasicRefresh *r=state(e);WORD box[4],clip[4],inclusive[4],view[4];UWORD i,j;
    for (i=p->paddingVisit/AES_VISIBLE_RECTS;i<4 && p->okay;++i) if (r->padding&(1<<i)) {
        margin_bounds(e,i,box);
        for (j=p->paddingVisit%AES_VISIBLE_RECTS;j<p->visibleCount && p->okay;++j) {
            if (!visible(e,j,view)) { p->okay=0;return; }
            if (!intersection(box,view,clip)) continue;
            if (p->fills==8) { p->paddingVisit=i*AES_VISIBLE_RECTS+j;return; }
            if (!room(p)) return;
            if (!visible(e,j,view)) { p->okay=0;return; }
            if (!intersection(box,view,clip)) continue;
            inclusive[0]=clip[0];inclusive[1]=clip[1];inclusive[2]=clip[2]-1;inclusive[3]=clip[3]-1;
            if (!invalidate(e,clip)) { p->okay=0;return; }
            vs_clip(e->app.vdi,1,inclusive);vsf_color(e->app.vdi,0);v_bar(e->app.vdi,inclusive);
            p->okay=ExecAESDiagnostic()==AES_OK;
            if (p->okay) p->okay=report(p,clip);p->drawn=1;
            ++p->fills;
        }
        if (p->okay) { r->paddingAdvance|=1<<i;p->paddingVisit=(i+1)*AES_VISIBLE_RECTS; }
    }
}
static void acknowledge(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);UWORD row,end;
    for (row=0;row<e->rows;++row) if ((end=r->advance[row])!=0) {
        if (end>=r->end[row]) { r->first[row]=BASIC_VIEW_COLUMNS;r->end[row]=0; }else r->first[row]=max(r->first[row],end);
        if (end>=r->forceEnd[row]) { r->forceFirst[row]=BASIC_VIEW_COLUMNS;r->forceEnd[row]=0; }else r->forceFirst[row]=max(r->forceFirst[row],end);
    }
    if ((end=r->advance[e->rows])!=0) {
        if (end>=r->statusEnd) { r->statusFirst=BASIC_VIEW_COLUMNS;r->statusEnd=0; }else r->statusFirst=max(r->statusFirst,end);
        if (end>=r->statusForceEnd) { r->statusForceFirst=BASIC_VIEW_COLUMNS;r->statusForceEnd=0; }else r->statusForceFirst=max(r->statusForceFirst,end);
    }
    r->padding&=~r->paddingAdvance;
}
WORD BasicEditorPaint(struct BasicEditor *e)
{
    struct BasicRefresh *r=state(e);struct BasicMotion *m=&e->motion.state;
    struct Paint p;UWORD row,first,end,count=0,limit;WORD fast,result;
    memset(&p,0,sizeof(p));p.e=e;p.okay=1;p.cells=CELL_BUDGET;
    if (m->applied && (m->document!=e->document.data || m->generation!=e->document.generation ||
        m->top!=e->first || m->left!=e->left || m->rows!=e->rows || m->columns!=e->columns ||
        m->caret!=e->caret || m->anchor!=e->anchor ||
        memcmp(m->work,e->app.work,sizeof(m->work)))) force_text(e);
    if (BasicEditorTranslation(e)) {
        if (!begin(&p)) { if (p.locked) wind_update(END_UPDATE);return 0; }
        result=move_pixels(&p);
        if (result!=EXEC_VDI_COPY_DONE) {
            if (!wind_update(END_UPDATE) || result==EXEC_VDI_COPY_ERROR) { force_text(e);return 0; }
            p.locked=0;
        }
    }
    geometry(e);
    e->motion.state.settled=e->motion.state.prepared=0;
    for (row=0;row<e->rows && count<ROW_BUDGET;++row) if (r->valid[row]&CANDIDATE) { compose(e,row);++count; }
    if (!candidates(e)) r->documentGeneration=e->document.generation;
    if (r->statusState!=VALID || r->status[0]!=(BasicDirty(&e->document) ? '*':' ')) compose_status(e);
    if (!pending(e) && !candidates(e)) { e->dirty=e->publish=0;remember(e);return 1; }
    if (r->hidden && !e->publish) {
        for (row=0;row<e->rows;++row) { r->first[row]=r->forceFirst[row]=BASIC_VIEW_COLUMNS;r->end[row]=r->forceEnd[row]=0; }
        r->statusFirst=r->statusForceFirst=BASIC_VIEW_COLUMNS;r->statusEnd=r->statusForceEnd=r->padding=0;
        e->dirty=candidates(e);return 1;
    }
    if (!p.locked && !begin(&p)) { if (p.locked) wind_update(END_UPDATE);return 0; }
    if (m->applied && !copy_view(e,0)) force_text(e);
    fast=complete(e);
    if (fast<0) { wind_update(END_UPDATE);return 0; }
    if (e->publish && !fast) {
        p.okay=deferred(e);
        if (!wind_update(END_UPDATE)) p.okay=0;
        if (p.okay) { ++r->publications;e->publish=0;r->hidden=p.visibleCount==0; }
        return p.okay;
    }
    memset(r->advance,0,sizeof(r->advance));r->paddingAdvance=0;
    p.paddingVisit=r->paddingVisit;
    if (r->padding) margins(&p);
    for (row=0;row<=e->rows && p.okay && p.rows<ROW_BUDGET && p.cells;++row) {
        if (row<e->rows && r->valid[row]!=VALID) continue;
        first=row==e->rows ? min(r->statusFirst,r->statusForceFirst):min(r->first[row],r->forceFirst[row]);
        end=row==e->rows ? max(r->statusEnd,r->statusForceEnd):max(r->end[row],r->forceEnd[row]);
        if (first>=end) continue;
        limit=fast ? end-first:p.cells/max(1,p.visibleCount);if (!limit) break;
        if (end-first>limit) end=first+limit;
        if (span(&p,row,first,end)) r->advance[row]=end;else p.cells=0;
        ++p.rows;
    }
    if (p.okay && m->applied && will_finish(e))
        p.okay=ExecAESPainted(e->app.window,e->app.work[0]+4,e->app.work[1],e->columns*8,e->rows*8);
    else if (p.okay && fast) p.okay=ExecAESPaintedChanges(e->app.window);
    if (p.locked && !wind_update(END_UPDATE)) p.okay=0;
    if (!p.okay) { if (m->applied) force_text(e);return 0; }
    acknowledge(e);r->paddingVisit=r->padding ? p.paddingVisit:0;
    e->publish=0;e->dirty=pending(e) || candidates(e);++e->paintTurns;
    if (m->applied) m->epoch=ExecAESWindowView(e->app.window)->paintEpoch;
    if (!e->dirty) remember(e);
    return 1;
}
