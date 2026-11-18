/* SPDX-License-Identifier: GPL-3.0-only */
/* Multiline layout, key handling and drawing adapted from Andreas Kromke's EDITOB.C. */
#include "aes-private.h"
#include "aes-paint-private.h"
#include "application-hosted.h"
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
    LONG cursorX;
    WORD cursorRow, cursorHides, dirty;
};

static XEDITINFO *editor(const OBJECT *object)
{
    return (XEDITINFO *)(ULONG)object->ob_spec;
}

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
    edit->selectedStart=edit->selectedEnd=0;
    edit->cursorX=0;
    edit->cursorRow=0;
    layout(edit);
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

static void line_at(const XEDITINFO *edit,LONG start,LONG at,struct EditLine *line)
{
    read_line(edit,start,line);
    while (at>=line->next && line->end!=edit->length)
        read_line(edit,line->next,line);
}

/* Only move the viewport when the caret leaves the retained visible rows. */
static void reveal_cursor(XEDITINFO *edit,WORD width)
{
    WORD row=visible_row(edit,edit->cursor);
    if (row<0) {
        struct EditLine last,first,at;
        line_at(edit,edit->cursor<edit->first ? 0:edit->first,edit->cursor,&at);
        if (edit->cursor>at.end) edit->cursor=at.next;
        if (edit->cursor<edit->first) {
            edit->first=at.start;
        } else {
            last=edit->lines[edit->drawnRows-1];
            read_line(edit,edit->first,&first);
            while (edit->cursor>last.end && last.end<edit->length) {
                read_line(edit,last.next,&last);
                read_line(edit,first.next,&first);
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
    if (first<=edit->first) {
        struct EditLine line;
        line_at(edit,0,first,&line);
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

static WORD redraw_rows(struct ExecAESContext *c,OBJECT *tree,WORD object,WORD first,WORD last)
{
    WORD x,y;
    objc_offset(tree,object,&x,&y);
    return ExecAESDraw(c,tree,object,0,x,y+first*CELL,tree[object].ob_width,(last-first+1)*CELL);
}

WORD edit_evnt(OBJECT *tree,WORD object,WORD window,EVNT *event,LONG *error)
{
    XEDITINFO *edit=editor(&tree[object]);
    struct ExecAESContext *c;
    LONG first,shift,selectedStart,selectedEnd,cursor;
    WORD oldRow,top,bottom;
    BOOL changed=FALSE;
    *error=0;
    if (!(event->mwhich&MU_KEYBD)) return 1;
    event->mwhich&=~MU_KEYBD;
    c=ExecAESContext();
    if (!edit->lines || !select_edit_window(c,window)) { *error=-1;return 0; }
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
