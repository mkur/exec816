/* SPDX-License-Identifier: GPL-3.0-only */
/* Multiline layout and tab drawing adapted from Andreas Kromke's EDITOB.C. */
#include "aes-private.h"
#include "aes-paint-private.h"
#include "application-hosted.h"
#include <proto/exec.h>

enum { CELL = 8, DEFAULT_TAB = 64 };

struct EditLine {
    LONG start, length;
};

struct XEDITINFO {
    XEDITINFO *next;
    char *buffer;
    LONG capacity, length;
    struct EditLine *lines;
    WORD rows, drawnRows;
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

static void layout(XEDITINFO *edit)
{
    LONG start=0,end=0;
    WORD row;
    for (row=0;row<edit->rows;++row) {
        while (end<edit->length && !line_break(edit->buffer[end])) ++end;
        edit->lines[row].start=start;
        edit->lines[row].length=end-start;
        if (end==edit->length) { ++row;break; }
        ++end;
        if (end<edit->length && line_break(edit->buffer[end]) &&
                edit->buffer[end]!=edit->buffer[end-1]) ++end;
        start=end;
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

static void draw_line(const char *text,LONG length,WORD x,WORD y,WORD right,WORD *glyphs)
{
    WORD offset=0;
    while (length>0 && x+offset<right) {
        WORD first=offset,count=0;
        if (*text=='\t') {
            offset=(offset/DEFAULT_TAB+1)*DEFAULT_TAB;
            ++text;
            --length;
            continue;
        }
        do {
            glyphs[count++]=(UBYTE)*text++;
            offset+=CELL;
            --length;
        } while (length>0 && *text!='\t' && count<INTIN_SIZE && x+offset<right);
        WidgetText(x+first,y,glyphs,count,MD_TRANS,BLACK);
    }
}

/* The object traversal already intersected work, visibility and caller clip. */
void ExecAESPaintMultiline(const OBJECT *object,WORD x,WORD y,const GRECT *clip,WORD *glyphs)
{
    const XEDITINFO *edit=editor(object);
    WORD row=(clip->g_y-y)/CELL;
    WORD right=clip->g_x+clip->g_w,bottom=clip->g_y+clip->g_h;
    WidgetFill(MD_REPLACE,FIS_SOLID,IP_SOLID,WHITE,clip);
    for (;row<edit->drawnRows && y+row*CELL<bottom;++row) {
        const struct EditLine *line=&edit->lines[row];
        draw_line(edit->buffer+line->start,line->length,x,y+row*CELL,right,glyphs);
    }
}
