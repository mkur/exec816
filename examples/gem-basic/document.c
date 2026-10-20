/* SPDX-License-Identifier: MIT */
#include "document.h"
#include <proto/exec.h>
#include <exec816/runtime.h>
#include <exec/memory.h>
#include <string.h>

struct Edit { ULONG at,oldBytes,newBytes,before,after; };

WORD BasicDocumentInit(struct BasicDocument *d)
{
    memset(d,0,sizeof(*d));
    d->data=AllocMem(BASIC_BYTES,MEMF_UPPER);
    d->line=AllocMem(BASIC_INDEX_BYTES,MEMF_UPPER);
    d->undo=AllocMem(BASIC_UNDO_BYTES,MEMF_UPPER);
    if (!d->data || !d->line || !d->undo) {
        BasicDocumentDispose(d);return BASIC_MEMORY;
    }
    d->end=BASIC_BYTES;d->lines=1;d->line[0]=d->line[1]=0;
    return BASIC_OK;
}

void BasicDocumentDispose(struct BasicDocument *d)
{
    if (d->data) FreeMem(d->data,BASIC_BYTES);
    if (d->line) FreeMem(d->line,BASIC_INDEX_BYTES);
    if (d->undo) FreeMem(d->undo,BASIC_UNDO_BYTES);
    memset(d,0,sizeof(*d));
}

UBYTE BasicByte(const struct BasicDocument *d,ULONG at)
{ return d->data[at<d->gap ? at:at+d->end-d->gap]; }

void BasicCopy(const struct BasicDocument *d,ULONG at,UBYTE *out,ULONG bytes)
{
    ULONG n;
    while (bytes) {
        n=at<d->gap ? d->gap-at:bytes;
        if (n>bytes) n=bytes;
        if (n>1024) n=1024;
        memcpy(out,d->data+(at<d->gap ? at:at+d->end-d->gap),n);
        out+=n;at+=n;bytes-=n;
    }
}

static ULONG record_bytes(const struct Edit *e)
{ return sizeof(*e)+e->oldBytes+e->newBytes; }

/* Each movement unit preserves the logical document, including when another
 * Task runs. The editor owns mutation; callbacks never observe a partial edit. */
static void move_gap(struct BasicDocument *d,ULONG at)
{
    ULONG n;
    while (d->gap!=at) {
        if (at<d->gap) {
            n=d->gap-at;if (n>1024) n=1024;
            memmove(d->data+d->end-n,d->data+d->gap-n,n);
            d->gap-=n;d->end-=n;
        } else {
            n=at-d->gap;if (n>1024) n=1024;
            memmove(d->data+d->gap,d->data+d->end,n);
            d->gap+=n;d->end+=n;
        }
        ExecYield();
    }
}

/* Validate the proposed concatenation before moving the gap or undo cursor. */
static WORD admit(const struct BasicDocument *d,ULONG at,ULONG old,
                  const UBYTE *text,ULONG bytes)
{
    ULONG i,suffix;UWORD first,last,lines,column;UBYTE c;
    if (at>d->bytes || old>d->bytes-at || (bytes && !text)) return BASIC_POSITION;
    if (bytes>BASIC_BYTES-(d->bytes-old)) return BASIC_CAPACITY;
    first=BasicLine(d,at);last=BasicLine(d,at+old);
    lines=d->lines-(last-first);column=(UWORD)(at-d->line[first]);
    suffix=(last+1<d->lines ? d->line[last+1]-1:d->bytes)-(at+old);
    for (i=0;i<bytes;++i) {
        c=text[i];
        if (c==10) {
            if (++lines>BASIC_LINES) return BASIC_LINE_CAPACITY;
            column=0;
        } else {
            if (c!=9 && (c<32 || c>126)) return BASIC_CHARACTER;
            if (++column>BASIC_COLUMNS) return BASIC_LINE_LENGTH;
        }
    }
    if (suffix>BASIC_COLUMNS-column) return BASIC_LINE_LENGTH;
    return BASIC_OK;
}

static void apply(struct BasicDocument *d,ULONG at,ULONG old,const UBYTE *text,ULONG bytes)
{
    UWORD first=BasicLine(d,at),last=BasicLine(d,at+old),added=0,line;
    ULONG i;
    for (i=0;i<bytes;++i) if (text[i]==10) ++added;
    move_gap(d,at);d->end+=old;
    if (bytes) memcpy(d->data+d->gap,text,bytes);
    d->gap+=bytes;d->bytes=d->bytes-old+bytes;
    memmove(d->line+first+1+added,d->line+last+1,(ULONG)(d->lines-last)*sizeof(ULONG));
    d->lines=d->lines-(last-first)+added;
    for (line=first+1+added;line<=d->lines;++line) d->line[line]=d->line[line]-old+bytes;
    line=first;
    for (i=0;i<bytes;++i) if (text[i]==10) d->line[++line]=at+i+1;
}

WORD BasicReplace(struct BasicDocument *d,ULONG at,ULONG old,const UBYTE *text,ULONG bytes)
{
    struct Edit e,first;ULONG size;WORD result;
    result=admit(d,at,old,text,bytes);
    if (result) return result;
    if (!old && !bytes) return BASIC_OK;
    if (old>BASIC_UNDO_BYTES-sizeof(e) || bytes>BASIC_UNDO_BYTES-sizeof(e)-old)
        return BASIC_UNDO_CAPACITY;
    if (d->serial==0xffffffffUL) return BASIC_GENERATION;
    e.at=at;e.oldBytes=old;e.newBytes=bytes;e.before=d->generation;e.after=d->serial+1;
    size=record_bytes(&e);
    d->used=d->cursor; /* A new accepted edit invalidates redo. */
    while (size>BASIC_UNDO_BYTES-d->used) {
        memcpy(&first,d->undo,sizeof(first));
        d->used-=record_bytes(&first);
        memmove(d->undo,d->undo+record_bytes(&first),d->used);
    }
    memcpy(d->undo+d->used,&e,sizeof(e));
    BasicCopy(d,at,d->undo+d->used+sizeof(e),old);
    if (bytes) memcpy(d->undo+d->used+sizeof(e)+old,text,bytes);
    /* The log owns the insertion bytes, so input may safely alias old text. */
    apply(d,at,old,d->undo+d->used+sizeof(e)+old,bytes);
    d->used+=size;d->cursor=d->used;d->generation=d->serial=e.after;
    return BASIC_OK;
}

WORD BasicUndo(struct BasicDocument *d)
{
    struct Edit e;ULONG at=0,last=0;
    if (!d->cursor) return 0;
    while (at<d->cursor) { last=at;memcpy(&e,d->undo+at,sizeof(e));at+=record_bytes(&e); }
    memcpy(&e,d->undo+last,sizeof(e));
    apply(d,e.at,e.newBytes,d->undo+last+sizeof(e),e.oldBytes);
    d->cursor=last;d->generation=e.before;return 1;
}

WORD BasicRedo(struct BasicDocument *d)
{
    struct Edit e;
    if (d->cursor==d->used) return 0;
    memcpy(&e,d->undo+d->cursor,sizeof(e));
    apply(d,e.at,e.oldBytes,d->undo+d->cursor+sizeof(e)+e.oldBytes,e.newBytes);
    d->cursor+=record_bytes(&e);d->generation=e.after;return 1;
}

WORD BasicDirty(const struct BasicDocument *d) { return d->generation!=d->saved; }

UWORD BasicLine(const struct BasicDocument *d,ULONG at)
{
    UWORD low=0,high=d->lines,mid;
    while (low+1<high) { mid=low+(high-low)/2;if (d->line[mid]<=at) low=mid;else high=mid; }
    return low;
}

ULONG BasicColumn(const struct BasicDocument *d,ULONG at)
{
    ULONG i=d->line[BasicLine(d,at)],column=0;
    while (i<at) { column=BasicByte(d,i++)==9 ? (column+8)&~7UL:column+1; }
    return column;
}
