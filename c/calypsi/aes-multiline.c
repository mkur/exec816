/* SPDX-License-Identifier: GPL-3.0-only */
/* Multiline layout, key handling and drawing adapted from Andreas Kromke's EDITOB.C. */
#include "aes-private.h"
#include "aes-paint-private.h"
#include "vdi-private.h"
#include "application-hosted.h"
#include "../../ports/gem4xe/raster/client.h"
#include <proto/exec.h>

enum { CELL = 8, DEFAULT_TAB = 64 };

struct EditLine {
    LONG start, end, next;
};

struct XEDITINFO {
    XEDITINFO *next;
    char *buffer;
    LONG capacity, length;
    struct EditLine *lines;
    WORD rows, drawnRows;
    LONG first, shift, cursor, selectedStart, selectedEnd;
    LONG cursorX, cursorGoal;
    LONG firstRow, lineCount, maxWidth;
    WORD cursorRow, cursorHides, dirty;
};

static XEDITINFO *editor(const OBJECT *object)
{
    return (XEDITINFO *)(ULONG)object->ob_spec;
}

static void document_metrics(XEDITINFO *edit);

/* MagiC admits CR, LF, CRLF and LFCR. A final separator starts an empty row. */
static WORD line_break(char c)
{
    return c=='\r' || c=='\n';
}

static void read_line(const XEDITINFO *edit,LONG start,struct EditLine *line)
{
    LONG end=start,next;
    while (end<edit->length && !line_break(edit->buffer[end])) ++end;
    next=end;
    if (next<edit->length) {
        ++next;
        if (next<edit->length && line_break(edit->buffer[next]) &&
                edit->buffer[next]!=edit->buffer[end]) ++next;
    }
    line->start=start;
    line->end=end;
    line->next=next;
}

static void layout(XEDITINFO *edit)
{
    LONG start=edit->first;
    WORD row;
    for (row=0;row<edit->rows;++row) {
        struct EditLine *line=&edit->lines[row];
        read_line(edit,start,line);
        if (line->end==edit->length) { ++row;break; }
        start=line->next;
    }
    edit->drawnRows=row;
}

static void close_edit(XEDITINFO *edit)
{
    if (edit->lines) FreeMem(edit->lines,(ULONG)edit->rows*sizeof(*edit->lines));
    edit->lines=NULL;
    edit->rows=edit->drawnRows=0;
}

XEDITINFO *edit_create(void)
{
    struct ExecAESContext *c=ExecAESContext();
    XEDITINFO *edit;
    if (!c || !ExecAESEnter(c)) return NULL;
    edit=AllocMem(sizeof(*edit),MEMF_PUBLIC|MEMF_CLEAR);
    if (edit) {
        edit->next=c->multiline;
        c->multiline=edit;
    } else c->diagnostic=AES_RESOURCE;
    c->busy=0;
    return edit;
}

void edit_set_buf(OBJECT *tree,WORD object,char *buffer,LONG capacity)
{
    XEDITINFO *edit=editor(&tree[object]);
    edit->buffer=buffer;
    edit->capacity=capacity;
    edit->length=0;
    edit->dirty=0;
}

WORD edit_open(OBJECT *tree,WORD object)
{
    XEDITINFO *edit=editor(&tree[object]);
    WORD rows=tree[object].ob_height/CELL;
    LONG length=0;
    if (edit->lines || !edit->buffer || edit->capacity<=0 || rows<=0) return 0;
    while (length<edit->capacity && edit->buffer[length]) ++length;
    if (length==edit->capacity) return 0;
    edit->lines=AllocMem((ULONG)rows*sizeof(*edit->lines),MEMF_PUBLIC);
    if (!edit->lines) return 0;
    edit->rows=rows;
    edit->length=length;
    edit->first=edit->shift=edit->cursor=0;
    edit->firstRow=0;
    edit->lineCount=0;
    edit->selectedStart=edit->selectedEnd=0;
    edit->cursorX=edit->cursorGoal=0;
    edit->cursorRow=0;
    layout(edit);
    document_metrics(edit);
    return 1;
}

void edit_close(OBJECT *tree,WORD object)
{
    close_edit(editor(&tree[object]));
}

void edit_delete(XEDITINFO *edit)
{
    struct ExecAESContext *c=ExecAESContext();
    XEDITINFO **link;
    if (!edit || !c || !ExecAESEnter(c)) return;
    link=&c->multiline;
    while (*link!=edit) link=&(*link)->next;
    *link=edit->next;
    close_edit(edit);
    FreeMem(edit,sizeof(*edit));
    c->busy=0;
}

void ExecAESMultilineFree(struct ExecAESContext *c)
{
    while (c->multiline) {
        XEDITINFO *edit=c->multiline;
        c->multiline=edit->next;
        close_edit(edit);
        FreeMem(edit,sizeof(*edit));
    }
}

WORD edit_get_buf(OBJECT *tree,WORD object,char **buffer,LONG *capacity,LONG *length)
{
    const XEDITINFO *edit=editor(&tree[object]);
    *buffer=edit->buffer;
    *capacity=edit->capacity;
    *length=edit->length;
    return 1;
}

WORD edit_get_cursor(OBJECT *tree,WORD object,char **cursor)
{
    const XEDITINFO *edit=editor(&tree[object]);
    if (!edit->lines) return 0;
    *cursor=edit->buffer+edit->cursor;
    return 1;
}

WORD edit_get_dirty(OBJECT *tree,WORD object)
{
    return editor(&tree[object])->dirty;
}

void edit_set_dirty(OBJECT *tree,WORD object,WORD dirty)
{
    editor(&tree[object])->dirty=dirty!=0;
}

void edit_get_sel(OBJECT *tree,WORD object,char **start,char **end)
{
    const XEDITINFO *edit=editor(&tree[object]);
    *start=*end=NULL;
    if (edit->selectedStart!=edit->selectedEnd) {
        *start=edit->buffer+edit->selectedStart;
        *end=edit->buffer+edit->selectedEnd;
    }
}

static LONG tab_stop(LONG x)
{
    return (x/DEFAULT_TAB+1)*DEFAULT_TAB;
}

static LONG text_width(const char *text,LONG length)
{
    LONG x=0;
    while (length--) {
        if (*text++=='\t') x=tab_stop(x);
        else x+=CELL;
    }
    return x;
}

static WORD visible_row(const XEDITINFO *edit,LONG at)
{
    WORD row;
    for (row=0;row<edit->drawnRows;++row)
        if (at>=edit->lines[row].start && at<=edit->lines[row].end) return row;
    return -1;
}

static LONG line_at(const XEDITINFO *edit,LONG start,LONG at,struct EditLine *line)
{
    LONG number=0;
    read_line(edit,start,line);
    while (at>=line->next && line->end!=edit->length) {
        read_line(edit,line->next,line);
        ++number;
    }
    return number;
}

static void document_metrics(XEDITINFO *edit)
{
    struct EditLine line;
    LONG width;
    if (edit->lineCount) return;
    edit->maxWidth=0;
    read_line(edit,0,&line);
    for (;;) {
        width=text_width(edit->buffer+line.start,line.end-line.start);
        if (width>edit->maxWidth) edit->maxWidth=width;
        ++edit->lineCount;
        if (line.end==edit->length) break;
        read_line(edit,line.next,&line);
    }
}

/* Only move the viewport when the caret leaves the retained visible rows. */
static void reveal_cursor(XEDITINFO *edit,WORD width)
{
    WORD row=visible_row(edit,edit->cursor);
    if (row<0) {
        struct EditLine last,first,at;
        LONG number=line_at(edit,edit->cursor<edit->first ? 0:edit->first,edit->cursor,&at);
        if (edit->cursor>at.end) edit->cursor=at.next;
        if (edit->cursor<edit->first) {
            edit->first=at.start;
            edit->firstRow=number;
        } else {
            last=edit->lines[edit->drawnRows-1];
            read_line(edit,edit->first,&first);
            while (edit->cursor>last.end && last.end<edit->length) {
                read_line(edit,last.next,&last);
                read_line(edit,first.next,&first);
                ++edit->firstRow;
            }
            edit->first=first.start;
        }
        layout(edit);
        row=visible_row(edit,edit->cursor);
    }
    edit->cursorRow=row;
    if (row>=0) {
        LONG start=edit->lines[row].start;
        edit->cursorX=text_width(edit->buffer+start,edit->cursor-start);
        if (edit->cursorX<edit->shift) edit->shift=edit->cursorX;
        else if (edit->cursorX-edit->shift>=width) edit->shift=edit->cursorX-width+1;
    }
}

/* The Calypsi C library takes a 16-bit size_t. Keep the donor's LONG offsets
 * and move an overlapping suffix in the appropriate direction. */
static void move_suffix(char *buffer,LONG dest,LONG source,LONG remaining)
{
    if (dest==source) return;
    while (remaining) {
        UWORD bytes=remaining>SIZE_MAX ? SIZE_MAX:(UWORD)remaining;
        remaining-=bytes;
        if (dest<source) {
            memmove(buffer+dest,buffer+source,bytes);
            dest+=bytes;
            source+=bytes;
        } else memmove(buffer+dest+remaining,buffer+source+remaining,bytes);
    }
}

/* A replacement admits the whole edit before moving the NUL and its suffix. */
static BOOL replace_text(XEDITINFO *edit,LONG first,LONG last,const char *text,WORD count)
{
    LONG removed=last-first;
    if (count>edit->capacity-edit->length-1+removed) return FALSE;
    move_suffix(edit->buffer,first+count,last,edit->length-last+1);
    if (count) memcpy(edit->buffer+first,text,count);
    edit->length+=count-removed;
    edit->cursor=first+count;
    edit->selectedStart=edit->selectedEnd=0;
    edit->dirty=1;
    edit->lineCount=0;
    if (first<=edit->first) {
        struct EditLine line;
        edit->firstRow=line_at(edit,0,first,&line);
        edit->first=line.start;
    }
    layout(edit);
    return TRUE;
}

static LONG previous_position(const XEDITINFO *edit,const struct EditLine *line,LONG at)
{
    struct EditLine previous;
    if (at>line->start || !at) return at ? at-1:0;
    if (edit->cursorRow>0) return edit->lines[edit->cursorRow-1].end;
    line_at(edit,0,at-1,&previous);
    return previous.end;
}

static LONG next_position(const struct EditLine *line,LONG at)
{
    return at<line->end ? at+1:line->next;
}

static LONG position_at_x(const XEDITINFO *edit,const struct EditLine *line,LONG x);

static LONG key_edit(XEDITINFO *edit,UWORD key,BOOL *changed)
{
    LONG first=edit->cursor,last=first;
    BOOL selected=edit->selectedStart!=edit->selectedEnd;
    const struct EditLine *line=&edit->lines[edit->cursorRow];
    UBYTE ch=(UBYTE)key;
    char text[2];
    WORD count=0;

    switch (key) {
    case 0x1e01: /* Ctrl+A */
        edit->selectedStart=0;
        edit->selectedEnd=edit->length;
        return 0;
    case 0x4700: /* Home, End and their MagiC variants */
    case 0x3700: case 0x4f00: case 0x4737:
        edit->cursor=key==0x4700 ?
            (selected ? edit->selectedStart:0):(selected ? edit->selectedEnd:edit->length);
        break;
    case 0x4b00:
        edit->cursor=selected ? edit->selectedStart:previous_position(edit,line,first);
        break;
    case 0x4d00:
        edit->cursor=selected ? edit->selectedEnd:next_position(line,first);
        break;
    case 0x4b34:
        edit->cursor=line->start;
        break;
    case 0x4d36:
        edit->cursor=line->end;
        break;
    case 0x4800: case 0x5000:
        if (selected) edit->cursor=key==0x4800 ? edit->selectedStart:edit->selectedEnd;
        else {
            struct EditLine target;
            if (key==0x4800) {
                if (!line->start) break;
                if (edit->cursorRow>0) target=edit->lines[edit->cursorRow-1];
                else line_at(edit,0,line->start-1,&target);
            } else {
                if (line->end==edit->length) break;
                read_line(edit,line->next,&target);
            }
            edit->cursor=position_at_x(edit,&target,edit->cursorGoal);
        }
        break;
    default:
        if (selected) { first=edit->selectedStart;last=edit->selectedEnd; }
        if (ch==8) {
            if (!selected) first=previous_position(edit,line,first);
        } else if (key==0x5300 || key==0x537f) {
            if (!selected) last=next_position(line,last);
        } else if (ch>=32 || ch=='\t' || ch=='\r') {
            text[count++]=(char)ch;
            if (ch=='\r') text[count++]='\n';
        } else return 0;
        if (first!=last || count) {
            if (!replace_text(edit,first,last,text,count)) return EDITERR_BUFFER_FULL;
            *changed=TRUE;
        }
        return 0;
    }
    edit->selectedStart=edit->selectedEnd=0;
    return 0;
}

static BOOL select_edit_window(struct ExecAESContext *c,WORD window)
{
    struct AESWindowView *view;
    if (!c || c->busy || !c->updateDepth || !c->workstation) return FALSE;
    view=ExecAESFindView(c,window);
    if (!view || !view->shown || !view->updates) return FALSE;
    c->view=view;
    c->request.view=view;
    return TRUE;
}

static void object_rect(OBJECT *tree,WORD object,GRECT *bounds)
{
    objc_offset(tree,object,&bounds->g_x,&bounds->g_y);
    bounds->g_w=tree[object].ob_width;
    bounds->g_h=tree[object].ob_height;
}

static WORD redraw_rect(struct ExecAESContext *c,OBJECT *tree,WORD object,const GRECT *area)
{
    return ExecAESDraw(c,tree,object,0,area->g_x,area->g_y,area->g_w,area->g_h);
}

static WORD redraw_rows(struct ExecAESContext *c,OBJECT *tree,WORD object,WORD first,WORD last)
{
    WORD x,y;
    objc_offset(tree,object,&x,&y);
    return ExecAESDraw(c,tree,object,0,x,y+first*CELL,tree[object].ob_width,(last-first+1)*CELL);
}

static LONG position_at_x(const XEDITINFO *edit,const struct EditLine *line,LONG x)
{
    LONG at=line->start,pixel=0;
    while (at<line->end) {
        LONG next=edit->buffer[at]=='\t' ? tab_stop(pixel):pixel+CELL;
        if (x<pixel+(next-pixel+1)/2) break;
        pixel=next;
        ++at;
    }
    return at;
}

static void set_top(XEDITINFO *edit,LONG top)
{
    LONG row=edit->firstRow,start=edit->first;
    struct EditLine line;
    if (top==row) return;
    if (top<row) row=start=0;
    while (row<top) {
        read_line(edit,start,&line);
        start=line.next;
        ++row;
    }
    edit->first=start;
    edit->firstRow=top;
    layout(edit);
}

WORD edit_resized(OBJECT *tree,WORD object,WORD *oldHeight,WORD *newHeight)
{
    XEDITINFO *edit=editor(&tree[object]);
    WORD rows=tree[object].ob_height/CELL;
    struct EditLine *lines;
    *oldHeight=*newHeight=edit->rows*CELL;
    if (!edit->lines || rows<=0) return 0;
    if (rows!=edit->rows) {
        lines=AllocMem((ULONG)rows*sizeof(*lines),MEMF_PUBLIC);
        if (!lines) return 0;
        FreeMem(edit->lines,(ULONG)edit->rows*sizeof(*edit->lines));
        edit->lines=lines;
        edit->rows=rows;
        *newHeight=rows*CELL;
        layout(edit);
    }
    reveal_cursor(edit,tree[object].ob_width);
    return 1;
}

WORD edit_get_scrollinfo(OBJECT *tree,WORD object,LONG *lines,LONG *top,
    WORD *rows,WORD *drawnRows,WORD *width,WORD *left,WORD *visibleWidth)
{
    XEDITINFO *edit=editor(&tree[object]);
    if (!edit->lines) return 0;
    document_metrics(edit);
    *lines=edit->lineCount;
    *top=edit->firstRow;
    *rows=edit->rows;
    *drawnRows=edit->drawnRows;
    *width=edit->maxWidth>32767 ? 32767:(WORD)edit->maxWidth;
    *left=edit->shift>32767 ? 32767:(WORD)edit->shift;
    *visibleWidth=tree[object].ob_width;
    return 1;
}

static WORD repaint_caret(struct ExecAESContext *c,OBJECT *tree,WORD object,
    const XEDITINFO *edit,const GRECT *bounds)
{
    LONG x=edit->cursorX-edit->shift;
    GRECT line;
    if (edit->cursorRow<0 || x<0 || x>=bounds->g_w) return 1;
    r_set(&line,bounds->g_x+(WORD)x,bounds->g_y+edit->cursorRow*CELL,1,CELL);
    return redraw_rect(c,tree,object,&line);
}

/* The same visible clip contains the source and destination. The raster
 * primitive also handles odd packed-pixel edges and overlap. */
static BOOL copy_fragment(struct ExecAESContext *c,const GRECT *dest,WORD dx,WORD dy)
{
    WORD x=dest->g_x,y=dest->g_y,w=dest->g_w-1,h=dest->g_h-1;
    WORD p[8]={x-dx,y-dy,x+w-dx,y+h-dy,x,y,x+w,y+h};
    UBYTE clipped=c->workstation->clipped;
    c->diagnostic=AES_OK;
    c->busy=1;
    c->workstation->clipped=0;
    ExecGemRasterCopy(c,S_ONLY,p,NULL,NULL);
    c->workstation->clipped=clipped;
    c->busy=0;
    return c->diagnostic==AES_OK;
}

static WORD scroll_pixels(struct ExecAESContext *c,OBJECT *tree,WORD object,
    const GRECT *bounds,LONG dx,LONG dy)
{
    LONG ax=dx<0 ? -dx:dx,ay=dy<0 ? -dy:dy;
    UWORD i;
    if ((dx && dy) || ax>=bounds->g_w || ay>=bounds->g_h)
        return redraw_rect(c,tree,object,bounds);
    for (i=0;i<c->view->visibleCount;++i) {
        const struct AESRect *visible=&c->view->visible[i];
        WORD l=bounds->g_x,t=bounds->g_y,r=l+bounds->g_w,b=t+bounds->g_h;
        GRECT area,dest;
        if (l<visible->left) l=visible->left;
        if (t<visible->top) t=visible->top;
        if (r>visible->right) r=visible->right;
        if (b>visible->bottom) b=visible->bottom;
        if (l>=r || t>=b) continue;
        r_set(&area,l,t,r-l,b-t);
        if (ax<area.g_w && ay<area.g_h) {
            r_set(&dest,l+(dx>0 ? (WORD)dx:0),t+(dy>0 ? (WORD)dy:0),
                area.g_w-(WORD)ax,area.g_h-(WORD)ay);
            if (copy_fragment(c,&dest,(WORD)dx,(WORD)dy)) {
                if (dx) {
                    if (dx<0) area.g_x+=dest.g_w;
                    area.g_w=(WORD)ax;
                } else {
                    if (dy<0) area.g_y+=dest.g_h;
                    area.g_h=(WORD)ay;
                }
            }
        }
        if (!redraw_rect(c,tree,object,&area)) return 0;
    }
    return 1;
}

static WORD scroll_edit(struct ExecAESContext *c,OBJECT *tree,WORD object,
    XEDITINFO *edit,LONG top,LONG left)
{
    GRECT bounds;
    LONG maxTop,dx,dy,oldShift=edit->shift,oldTop=edit->firstRow;
    WORD result,oldHides=edit->cursorHides;
    BOOL caret=!oldHides && edit->selectedStart==edit->selectedEnd;
    object_rect(tree,object,&bounds);
    document_metrics(edit);
    maxTop=edit->lineCount-edit->rows;
    if (maxTop<0) maxTop=0;
    if (top>=0 && top>maxTop) top=maxTop;
    if (top<0) top=oldTop;
    if (left<0) left=oldShift;
    dx=oldShift-left;
    dy=(oldTop-top)*CELL;
    if (!dx && !dy) return 1;
    if (caret) {
        edit->cursorHides=1;
        if (!repaint_caret(c,tree,object,edit,&bounds)) {
            edit->cursorHides=oldHides;
            return 0;
        }
    }
    edit->shift=left;
    if (dy) {
        WORD row=edit->cursorRow;
        const struct EditLine *line;
        set_top(edit,top);
        if (row>=edit->drawnRows) row=edit->drawnRows-1;
        if (row<0) row=0;
        line=&edit->lines[row];
        edit->cursor=position_at_x(edit,line,edit->cursorGoal);
        edit->cursorRow=row;
        edit->cursorX=text_width(edit->buffer+line->start,edit->cursor-line->start);
        bounds.g_h=edit->rows*CELL;
    }
    result=scroll_pixels(c,tree,object,&bounds,dx,dy);
    edit->cursorHides=oldHides;
    return (!caret || repaint_caret(c,tree,object,edit,&bounds)) && result;
}

WORD edit_scroll(OBJECT *tree,WORD object,WORD window,LONG top,WORD left)
{
    struct ExecAESContext *c=ExecAESContext();
    XEDITINFO *edit=editor(&tree[object]);
    if (!edit->lines || !select_edit_window(c,window)) return 0;
    return scroll_edit(c,tree,object,edit,top,left);
}

static WORD edit_key(struct ExecAESContext *c,OBJECT *tree,WORD object,
    XEDITINFO *edit,const EVNT *event,LONG *error)
{
    LONG first,shift,selectedStart,selectedEnd,cursor;
    WORD oldRow,top,bottom,page=0;
    BOOL changed=FALSE;

    switch ((UWORD)event->key) {
    case 0x4800: if (event->kstate&4) page=-1; break;
    case 0x5000: if (event->kstate&4) page=1; break;
    case 0x4900: case 0x4838: page=-edit->rows; break;
    case 0x5100: case 0x5032: page=edit->rows; break;
    }
    if (page) {
        LONG target=edit->firstRow+page;
        if (scroll_edit(c,tree,object,edit,target<0 ? 0:target,-1)) return 1;
        *error=-1;
        return 0;
    }
    first=edit->first;
    shift=edit->shift;
    selectedStart=edit->selectedStart;
    selectedEnd=edit->selectedEnd;
    cursor=edit->cursor;
    oldRow=edit->cursorRow;
    *error=key_edit(edit,(UWORD)event->key,&changed);
    if (*error) return 0;
    if (!changed && cursor==edit->cursor && selectedStart==edit->selectedStart &&
            selectedEnd==edit->selectedEnd) return 1;
    reveal_cursor(edit,tree[object].ob_width);
    if (event->key!=0x4800 && event->key!=0x5000) edit->cursorGoal=edit->cursorX;
    top=oldRow<edit->cursorRow ? oldRow:edit->cursorRow;
    bottom=oldRow>edit->cursorRow ? oldRow:edit->cursorRow;
    if (changed) bottom=edit->rows-1;
    if (first!=edit->first || shift!=edit->shift || selectedStart!=edit->selectedStart ||
            selectedEnd!=edit->selectedEnd) {
        top=0;
        bottom=edit->rows-1;
    }
    if (redraw_rows(c,tree,object,top,bottom)) return 1;
    *error=-1;
    return 0;
}

static void place_cursor(XEDITINFO *edit,LONG at)
{
    WORD row=visible_row(edit,at);
    edit->cursor=at;
    edit->cursorRow=row;
    if (row>=0) {
        LONG start=edit->lines[row].start;
        edit->cursorX=edit->cursorGoal=text_width(edit->buffer+start,at-start);
    }
}

static LONG point_offset(const XEDITINFO *edit,const GRECT *bounds,WORD x,WORD y)
{
    WORD row;
    if (y<bounds->g_y) return edit->first;
    row=(y-bounds->g_y)/CELL;
    if (row>=edit->drawnRows) return edit->lines[edit->drawnRows-1].end;
    return position_at_x(edit,&edit->lines[row],(LONG)x-bounds->g_x+edit->shift);
}

static WORD row_near(const XEDITINFO *edit,LONG at)
{
    WORD row;
    for (row=0;row<edit->drawnRows-1;++row)
        if (at<edit->lines[row].next) return row;
    return row;
}

static WORD select_range(struct ExecAESContext *c,OBJECT *tree,WORD object,
    XEDITINFO *edit,LONG anchor,LONG at)
{
    LONG start=anchor<at ? anchor:at,end=anchor<at ? at:anchor;
    LONG lo,hi,oldStart=edit->selectedStart,oldEnd=edit->selectedEnd;
    if (oldStart==oldEnd) oldStart=oldEnd=edit->cursor;
    if (start==oldStart && end==oldEnd) {
        if (edit->cursor!=at) place_cursor(edit,at);
        return 1;
    }
    if (start==oldStart) {
        lo=end<oldEnd ? end:oldEnd;
        hi=end>oldEnd ? end:oldEnd;
    } else if (end==oldEnd) {
        lo=start<oldStart ? start:oldStart;
        hi=start>oldStart ? start:oldStart;
    } else {
        lo=start<oldStart ? start:oldStart;
        hi=end>oldEnd ? end:oldEnd;
    }
    edit->selectedStart=start;
    edit->selectedEnd=end;
    place_cursor(edit,at);
    return redraw_rows(c,tree,object,row_near(edit,lo),row_near(edit,hi));
}

static BOOL word_separator(char ch)
{
    return strchr(" !.+-*/:?[\\]{|}()~\366\367\370\371\372\t",ch)!=NULL;
}

static WORD select_word(struct ExecAESContext *c,OBJECT *tree,WORD object,
    XEDITINFO *edit,LONG at)
{
    WORD row=visible_row(edit,at);
    const struct EditLine *line=&edit->lines[row];
    LONG start=at,end=at;
    if (start==line->end && start>line->start) --start;
    while (start>line->start && word_separator(edit->buffer[start])) --start;
    while (start>line->start && !word_separator(edit->buffer[start-1])) --start;
    while (end<line->end && !word_separator(edit->buffer[end])) ++end;
    return select_range(c,tree,object,edit,start,end);
}

/* MagiC's timer accelerates as the pointer moves further outside the object.
 * A blocked edge waits for motion or release with no timer. */
static WORD drag_step(XEDITINFO *edit,const GRECT *bounds,WORD x,WORD y,
    LONG *top,LONG *left)
{
    WORD distance,vertical=0;
    *top=edit->firstRow;
    *left=edit->shift;
    document_metrics(edit);
    if (x<bounds->g_x && *left>0) {
        --*left;
        distance=bounds->g_x-x;
    } else if (x>=bounds->g_x+bounds->g_w &&
            *left<edit->maxWidth-bounds->g_w+1) {
        ++*left;
        distance=x-bounds->g_x-bounds->g_w+1;
    } else if (y<bounds->g_y && *top>0) {
        --*top;
        distance=bounds->g_y-y;
        vertical=1;
    } else if (y>=bounds->g_y+bounds->g_h &&
            *top<edit->lineCount-edit->rows) {
        ++*top;
        distance=y-bounds->g_y-bounds->g_h+1;
        vertical=1;
    } else return -1;
    if (distance>16) distance=16;
    return vertical ? (16-distance)*200/16+20:16-distance;
}

static WORD edit_button(struct ExecAESContext *c,OBJECT *tree,WORD object,
    XEDITINFO *edit,WORD window,const EVNT *event,const GRECT *bounds)
{
    LONG initialTop=edit->firstRow,initialLeft=edit->shift,initialCursor=edit->cursor;
    LONG initialStart=edit->selectedStart,initialEnd=edit->selectedEnd,initialGoal=edit->cursorGoal;
    LONG at=point_offset(edit,bounds,event->mx,event->my),anchor=at;
    ULONG epoch=c->view->epoch;
    WORD x,y,buttons,modifiers,clicks,key,ready,delay;
    UWORD status;
    MOBLK point={1,0,0,1,1};
    LONG top,left;

    if (event->mclicks==2) return select_word(c,tree,object,edit,at);
    if (event->kstate&3)
        anchor=initialStart!=initialEnd ? initialStart:initialCursor;
    if (!select_range(c,tree,object,edit,anchor,at)) return 0;
    if (!ExecAESMouseState(c,&x,&y,&buttons,&modifiers)) return 0;
    while (buttons&1) {
        delay=drag_step(edit,bounds,x,y,&top,&left);
        point.m_x=x;
        point.m_y=y;
        /* Every paint and copy retired its DISPLAY borrow before this wait. */
        ready=evnt_multi_moblk(MU_BUTTON|MU_M1|(delay>=0 ? MU_TIMER:0),1,1,0,
            &point,NULL,NULL,delay>=0 ? (UWORD)delay:0,0,&x,&y,&buttons,&modifiers,&key,&clicks);
        if (!ready) break;
        if (!ExecAESWindowEpoch(c,window,epoch) ||
                ((ready&(MU_BUTTON|MU_M1)) && c->eventWindow!=window)) {
            c->diagnostic=AES_INPUT_LOST;
            break;
        }
        if (ready&MU_BUTTON) return 1;
        if (drag_step(edit,bounds,x,y,&top,&left)>=0 &&
                !scroll_edit(c,tree,object,edit,top,left)) return 0;
        at=point_offset(edit,bounds,x,y);
        if (!select_range(c,tree,object,edit,anchor,at)) return 0;
    }
    if (buttons&1 || c->diagnostic!=AES_OK) {
        status=c->diagnostic;
        set_top(edit,initialTop);
        edit->shift=initialLeft;
        edit->selectedStart=initialStart;
        edit->selectedEnd=initialEnd;
        place_cursor(edit,initialCursor);
        edit->cursorGoal=initialGoal;
        if (ExecAESWindowEpoch(c,window,epoch)) redraw_rect(c,tree,object,bounds);
        c->diagnostic=status;
        return 0;
    }
    return 1;
}

WORD edit_evnt(OBJECT *tree,WORD object,WORD window,EVNT *event,LONG *error)
{
    XEDITINFO *edit=editor(&tree[object]);
    struct ExecAESContext *c;
    GRECT bounds;
    *error=0;
    if (!(event->mwhich&(MU_KEYBD|MU_BUTTON))) return 1;
    c=ExecAESContext();
    if (!edit->lines || !select_edit_window(c,window)) { *error=-1;return 0; }
    if (event->mwhich&MU_KEYBD) {
        event->mwhich&=~MU_KEYBD;
        if (!edit_key(c,tree,object,edit,event,error)) return 0;
    }
    if (!(event->mwhich&MU_BUTTON) || !(event->mbutton&1) ||
            c->eventWindow!=window) return 1;
    object_rect(tree,object,&bounds);
    if (event->mx<bounds.g_x || event->mx>=bounds.g_x+bounds.g_w ||
        event->my<bounds.g_y || event->my>=bounds.g_y+bounds.g_h) return 1;
    event->mwhich&=~MU_BUTTON;
    if (edit_button(c,tree,object,edit,window,event,&bounds)) return 1;
    *error=-1;
    return 0;
}

WORD edit_cursor(OBJECT *tree,WORD object,WORD window,WORD show)
{
    XEDITINFO *edit=editor(&tree[object]);
    WORD old=edit->cursorHides;
    struct ExecAESContext *c;
    if (show<0) return old;
    c=ExecAESContext();
    if (!edit->lines || !select_edit_window(c,window)) return -1;
    if (!show && old<32767) ++edit->cursorHides;
    else if (show==1 && old>0) --edit->cursorHides;
    if ((!old)!=(!edit->cursorHides) &&
        !redraw_rows(c,tree,object,edit->cursorRow,edit->cursorRow)) return -1;
    return edit->cursorHides;
}

static void draw_line(const char *text,LONG length,LONG x,WORD y,const GRECT *clip,WORD *glyphs)
{
    LONG offset=0;
    WORD right=clip->g_x+clip->g_w;
    while (length>0 && x+offset<right) {
        LONG first=offset;
        WORD count=0;
        if (*text=='\t') {
            offset=tab_stop(offset);
            ++text;
            --length;
            continue;
        }
        if (x+offset+CELL<=clip->g_x) {
            offset+=CELL;
            ++text;
            --length;
            continue;
        }
        do {
            glyphs[count++]=(UBYTE)*text++;
            offset+=CELL;
            --length;
        } while (length>0 && *text!='\t' && count<INTIN_SIZE && x+offset<right);
        WidgetText((WORD)(x+first),y,glyphs,count,MD_TRANS,BLACK);
    }
}

/* The object traversal already intersected work, visibility and caller clip. */
void ExecAESPaintMultiline(const OBJECT *object,WORD x,WORD y,const GRECT *clip,WORD *glyphs)
{
    const XEDITINFO *edit=editor(object);
    WORD row=(clip->g_y-y)/CELL;
    WORD bottom=clip->g_y+clip->g_h;
    LONG origin=(LONG)x-edit->shift;
    WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,WHITE,clip);
    for (;row<edit->drawnRows && y+row*CELL<bottom;++row) {
        const struct EditLine *line=&edit->lines[row];
        const char *text=edit->buffer+line->start;
        LONG left,right;
        GRECT rect;
        draw_line(text,line->end-line->start,origin,y+row*CELL,clip,glyphs);
        if (edit->selectedStart!=edit->selectedEnd) {
            if (edit->selectedEnd<=line->start || edit->selectedStart>=line->next) continue;
            left=origin;
            if (edit->selectedStart>line->start)
                left+=text_width(text,edit->selectedStart-line->start);
            right=(LONG)clip->g_x+clip->g_w;
            if (edit->selectedEnd<=line->end)
                right=origin+text_width(text,edit->selectedEnd-line->start);
        } else {
            if (row!=edit->cursorRow || edit->cursorHides) continue;
            left=origin+edit->cursorX;
            right=left+1;
        }
        if (left<clip->g_x) left=clip->g_x;
        if (right>clip->g_x+clip->g_w) right=clip->g_x+clip->g_w;
        if (left<right) {
            r_set(&rect,(WORD)left,y+row*CELL,(WORD)(right-left),CELL);
            WidgetFill(MD_XOR,FIS_SOLID,IP_SOLID,BLACK,&rect);
        }
    }
}
