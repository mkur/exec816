/* SPDX-License-Identifier: MIT */
#include "document.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>

void TextDispose(struct TextDocument *d)
{
    if (d->data) FreeMem(d->data,TEXT_BYTES);
    if (d->line) FreeMem(d->line,TEXT_INDEX_BYTES);
    memset(d,0,sizeof(*d));
}

void TextCancel(struct TextLoad *l)
{
    if (l->file) {
        LONG okay=Close(l->file);
        l->file=0;
        if (!okay && !l->error) l->error=IoErr();
    }
    TextDispose(&l->candidate);
    l->phase=0;
}

void TextBegin(struct TextLoad *l,const char *path)
{
    l->error=0;l->start=1;l->cr=0;l->phase=1;
    strcpy(l->candidate.path,path);
}

static WORD failed(struct TextLoad *l,LONG error)
{
    l->error=error;TextCancel(l);return -1;
}

static WORD index_bytes(struct TextLoad *l,ULONG end)
{
    struct TextDocument *d=&l->candidate;
    ULONG at=d->bytes;
    while (at<end) {
        UBYTE ch=d->data[at];
        if (l->cr && ch==10) { l->cr=0;++at;continue; }
        l->cr=0;
        if (l->start) {
            if (d->lines==TEXT_LINES) return 0;
            d->line[d->lines++]=at;l->start=0;
        }
        if (ch==13 || ch==10 || ch==0x9b) {
            l->start=1;l->cr=ch==13;
        }
        ++at;
    }
    d->bytes=end;d->line[d->lines]=end;
    return 1;
}

WORD TextStep(struct TextLoad *l,struct TextDocument *current)
{
    struct TextDocument *d=&l->candidate;
    LONG count,error;
    BPTR lock;
    if (l->phase==1) {
        lock=Lock(d->path,SHARED_LOCK);
        if (!lock) return failed(l,IoErr());
        count=Examine(lock,&l->info);error=IoErr();UnLock(lock);
        if (!count) return failed(l,error);
        if (l->info.fib_DirEntryType>=0) return failed(l,ERROR_OBJECT_WRONG_TYPE);
        if (l->info.fib_Size>TEXT_BYTES) return failed(l,ERROR_OBJECT_TOO_LARGE);
        d->data=AllocMem(TEXT_BYTES,MEMF_UPPER);
        d->line=AllocMem(TEXT_INDEX_BYTES,MEMF_UPPER);
        if (!d->data || !d->line) return failed(l,ERROR_NO_FREE_STORE);
        d->line[0]=0;l->phase=2;
    } else if (l->phase==2) {
        l->file=Open(d->path,MODE_OLDFILE);
        if (!l->file) return failed(l,IoErr());
        l->phase=3;
    } else if (l->phase==3) {
        ULONG left=TEXT_BYTES-d->bytes;
        count=Read(l->file,left ? d->data+d->bytes:&l->probe,
                   left ? (left>1024 ? 1024:(LONG)left):1);
        error=IoErr();
        if (count<0 || error) return failed(l,error ? error:ERROR_BAD_STREAM_NAME);
        if (!left && count) return failed(l,ERROR_OBJECT_TOO_LARGE);
        if (count && !index_bytes(l,d->bytes+count)) return failed(l,TEXT_LINE_LIMIT);
        if (!count) l->phase=4;
    } else if (l->phase==4) {
        count=Close(l->file);error=IoErr();l->file=0;
        if (!count) return failed(l,error);
        TextDispose(current);*current=*d;memset(d,0,sizeof(*d));
        l->phase=0;return 1;
    }
    return 0;
}

void TextRow(const struct TextDocument *d,UWORD row,char *out,WORD width)
{
    WORD column=0;
    if (row<d->lines) {
        ULONG at=d->line[row],end=d->line[row+1];
        while (column<width && at<end) {
            UBYTE ch=d->data[at++];
            if (ch==10 || ch==13 || ch==0x9b) break;
            if (ch==9) {
                do { out[column++]=' '; } while (column<width && (column&7));
            } else out[column++]=ch>=32 && ch<=126 ? ch:'.';
        }
    }
    while (column<width) out[column++]=' ';
    out[column]=0;
}

WORD TextArgument(const char *args,char *path)
{
    WORD n=0,quoted;
    if (!args) { path[0]=0;return 1; }
    while (*args==' ' || *args=='\t') ++args;
    quoted=*args=='"';if (quoted) ++args;
    while (*args && (quoted ? *args!='"':*args!=' ' && *args!='\t')) {
        if (n==127 || *args=='"') return 0;
        path[n++]=*args++;
    }
    if (quoted) { if (*args!='"' || !n) return 0;++args; }
    while (*args==' ' || *args=='\t') ++args;
    if (*args) return 0;
    path[n]=0;return 1;
}
