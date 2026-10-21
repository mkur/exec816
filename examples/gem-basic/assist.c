/* SPDX-License-Identifier: MIT */
#include "assist.h"
#include <proto/exec.h>
#include <exec816/runtime.h>
#include <exec/memory.h>
#include <string.h>
static UBYTE upper(UBYTE c) { return c>='a' && c<='z' ? c-32:c; }
static WORD same(UBYTE a,UBYTE b,WORD fold) { return fold ? upper(a)==upper(b):a==b; }
static WORD identifier(UBYTE c)
{ return (upper(c)>='A' && upper(c)<='Z') || (c>='0' && c<='9') || c=='_' || c=='$' || c=='%'; }

WORD BasicFindBegin(struct BasicFind *f,const struct BasicDocument *d,const UBYTE *needle,UWORD length,ULONG at,WORD fold)
{
    UWORD i,j=0;
    memset(f,0,sizeof(*f));
    if (!length || length>BASIC_FIND_BYTES || at>d->bytes) return BASIC_POSITION;
    memcpy(f->needle,needle,length);f->length=length;f->fold=fold;f->at=f->start=at;
    f->limit=d->bytes;f->generation=d->generation;
    for (i=1;i<length;++i) {
        while (j && !same(needle[i],needle[j],fold)) j=f->prefix[j-1];
        if (same(needle[i],needle[j],fold)) ++j;
        f->prefix[i]=j;
    }
    return BASIC_OK;
}
WORD BasicFindStep(struct BasicFind *f,const struct BasicDocument *d)
{
    UWORD budget=1024;
    if (f->generation!=d->generation || f->done) return -1;
    while (budget-- && f->at<f->limit) {
        if (same(BasicByte(d,f->at),f->needle[f->index],f->fold)) {
            ++f->at;
            if (++f->index==f->length) { f->result=f->at-f->length;f->done=1;return 1; }
        } else if (f->index) f->index=f->prefix[f->index-1];
        else ++f->at;
    }
    if (f->at==f->limit) { f->done=1;return -1; }
    return 0;
}

void BasicReplaceCancel(struct BasicReplaceJob *j)
{
    if (j->buffer) FreeMem(j->buffer,j->bytes ? j->bytes:1);
    j->buffer=0;j->phase=0;
}
WORD BasicReplaceBegin(struct BasicReplaceJob *j,const struct BasicDocument *d,const UBYTE *needle,UWORD length,
    const UBYTE *replacement,UWORD size,WORD fold)
{
    memset(j,0,sizeof(*j));
    if (size>BASIC_FIND_BYTES || (size && !replacement)) return j->error=BASIC_POSITION;
    j->error=BasicFindBegin(&j->find,d,needle,length,0,fold);if (j->error) return j->error;
    if (size) memcpy(j->replacement,replacement,size);
    j->size=size;j->phase=1;return BASIC_OK;
}
WORD BasicReplaceStep(struct BasicReplaceJob *j,struct BasicDocument *d)
{
    WORD step;ULONG n;
    /* Calypsi 5.18 can reuse the destination's old value when a spilled huge
     * pointer assigns arithmetic from another field. Stage the scalar before
     * publishing it; the volatile local preserves that load/store boundary. */
    volatile ULONG computed;
    if (!j->phase) return j->error ? -1:1;
    if (d->generation!=j->find.generation) { j->error=BASIC_GENERATION;goto fail; }
    if (j->phase==1) {
        step=BasicFindStep(&j->find,d);if (!step) return 0;
        if (step==1) {
            if (!j->count) j->first=j->find.result;
            computed=j->find.result;computed+=j->find.length;j->last=computed;++j->count;
            j->find.at=j->last;j->find.index=j->find.done=0;return 0;
        }
        if (!j->count) { j->phase=0;return 1; }
        computed=j->last;computed-=j->first;j->span=computed;
        if (j->size>j->find.length && j->count*(j->size-j->find.length)>BASIC_BYTES-d->bytes) {
            j->error=BASIC_CAPACITY;goto fail;
        }
        computed=j->span;
        if (j->size>=j->find.length) computed+=j->count*(j->size-j->find.length);
        else computed-=j->count*(j->find.length-j->size);
        j->bytes=computed;
        if (j->span+j->bytes+20>BASIC_UNDO_BYTES) { j->error=BASIC_UNDO_CAPACITY;goto fail; }
        j->buffer=AllocMem(j->bytes ? j->bytes:1,MEMF_UPPER);
        if (!j->buffer) { j->error=BASIC_MEMORY;goto fail; }
        j->at=j->find.at=j->first;j->find.index=j->find.done=0;j->phase=2;return 0;
    }
    if (j->phase==2) {
        step=BasicFindStep(&j->find,d);if (!step) return 0;
        if (step<0) { j->error=BASIC_GENERATION;goto fail; }
        j->copyEnd=j->find.result;j->phase=3;return 0;
    }
    if (j->phase==3) {
        n=j->copyEnd-j->at;if (n>1024) n=1024;
        if (n) { BasicCopy(d,j->at,j->buffer+j->out,n);j->at+=n;j->out+=n; }
        if (j->at==j->copyEnd) j->phase=4;
        return 0;
    }
    if (j->phase==4) {
        if (j->size) memcpy(j->buffer+j->out,j->replacement,j->size);
        j->out+=j->size;computed=j->find.result;computed+=j->find.length;j->at=computed;
        j->find.at=j->at;j->find.index=j->find.done=0;
        j->phase=j->at==j->last ? 5:2;return 0;
    }
    j->error=BasicReplace(d,j->first,j->span,j->buffer,j->bytes);
    BasicReplaceCancel(j);return j->error ? -1:1;
fail:
    BasicReplaceCancel(j);return -1;
}
WORD BasicReplaceMatches(struct BasicDocument *d,const UBYTE *needle,UWORD length,
    const UBYTE *replacement,UWORD size,WORD fold,ULONG *count)
{
    struct BasicReplaceJob *job;WORD step,result;
    *count=0;job=AllocMem(sizeof(*job),MEMF_UPPER);if (!job) return BASIC_MEMORY;
    result=BasicReplaceBegin(job,d,needle,length,replacement,size,fold);
    if (!result) {
        do { step=BasicReplaceStep(job,d);if (!step) ExecYield(); } while (!step);
        if (step==1) *count=job->count;
        result=job->error;
    }
    BasicReplaceCancel(job);FreeMem(job,sizeof(*job));return result;
}
WORD BasicIndent(struct BasicDocument *d,ULONG at,ULONG removed,ULONG *caret,UBYTE *text)
{
    ULONG start=d->line[BasicLine(d,at)];UWORD n=1;WORD result;
    text[0]=10;
    while (start<at && n<BASIC_COLUMNS+1 && (BasicByte(d,start)==32 || BasicByte(d,start)==9)) text[n++]=BasicByte(d,start++);
    result=BasicReplace(d,at,removed,text,n);if (!result) *caret=at+n;return result;
}

static WORD word(const struct BasicDocument *d,ULONG at,UWORD n,const char *value)
{
    UWORD i;if (strlen(value)!=n) return 0;
    for (i=0;i<n;++i) if (upper(BasicByte(d,at+i))!=(UBYTE)value[i]) return 0;
    return 1;
}
void BasicLexLine(const struct BasicDocument *d,UWORD line,UBYTE *colors)
{
    static const char keywords[]=" AND BYTE DATA DIM DO ELSE ELSEIF END ENDIF ENDPROC EXEC EXIT FOR IF INPUT INT NEXT NOT OR PAUSE PEEK POKE PRINT PROC PUT RAND REPEAT RETURN STEP THEN TIME TO UNTIL VAL WEND WHILE XOR ";
    ULONG at,end,start;UWORD i=0,n,j;UBYTE c;WORD found;
    if (line>=d->lines) return;
    at=d->line[line];end=d->line[line+1];
    while (at<end && i<BASIC_COLUMNS) {
        c=BasicByte(d,at);
        if (c==10) break;
        if (c=='\'') { while (at++<end && i<BASIC_COLUMNS) colors[i++]=BASIC_LEX_COMMENT;break; }
        if (c=='"') {
            colors[i++]=BASIC_LEX_STRING;++at;
            while (at<end && i<BASIC_COLUMNS) {
                c=BasicByte(d,at++);colors[i++]=BASIC_LEX_STRING;if (c=='"') break;
            }
        } else if (identifier(c)) {
            start=at;while (at<end && identifier(BasicByte(d,at))) ++at;
            n=at-start;found=0;
            if (word(d,start,n,"REM")) {
                while (i<BASIC_COLUMNS && start++<end) colors[i++]=BASIC_LEX_COMMENT;break;
            }
            for (j=1;keywords[j];) {
                UWORD first=j;while (keywords[j] && keywords[j]!=' ') ++j;
                if (j-first==n) {
                    UWORD k;for (k=0;k<n && upper(BasicByte(d,start+k))==(UBYTE)keywords[first+k];++k) {}
                    if (k==n) found=1;
                }
                if (keywords[j]) ++j;
            }
            while (n-- && i<BASIC_COLUMNS) colors[i++]=found ? BASIC_LEX_KEYWORD:BASIC_LEX_TEXT;
        } else { colors[i++]=BASIC_LEX_TEXT;++at; }
    }
}
void BasicAssistBegin(struct BasicAssist *a,const struct BasicDocument *d)
{ memset(a,0,sizeof(*a));a->generation=d->generation;a->open=0xffff; }
WORD BasicAssistStep(struct BasicAssist *a,const struct BasicDocument *d)
{
    UWORD units=4,line,n;ULONG at,end,start;
    if (a->generation!=d->generation) BasicAssistBegin(a,d);
    while (a->scan<d->lines && units--) {
        line=a->scan++;at=d->line[line];end=d->line[line+1];
        while (at<end && (BasicByte(d,at)==32 || BasicByte(d,at)==9)) ++at;
        start=at;while (at<end && identifier(BasicByte(d,at))) ++at;
        if (word(d,start,at-start,"PROC")) {
            while (at<end && (BasicByte(d,at)==32 || BasicByte(d,at)==9)) ++at;
            start=at;while (at<end && identifier(BasicByte(d,at))) ++at;n=at-start;
            if (n && n<32) {
                if (a->count==BASIC_PROCEDURES) { a->overflow=1;continue; }
                a->open=a->count++;a->procedures[a->open].first=a->procedures[a->open].last=line;
                BasicCopy(d,start,(UBYTE *)a->procedures[a->open].name,n);a->procedures[a->open].name[n]=0;
            }
        } else if (word(d,start,at-start,"ENDPROC") && a->open!=0xffff) {
            a->procedures[a->open].last=line;a->open=0xffff;
        }
    }
    return a->scan==d->lines;
}
WORD BasicProcedureNamed(const struct BasicAssist *a,const char *name)
{
    UWORD i,j;
    for (i=0;i<a->count;++i) {
        for (j=0;name[j] && upper(name[j])==upper(a->procedures[i].name[j]);++j) {}
        if (!name[j] && !a->procedures[i].name[j]) return i;
    }
    return -1;
}
WORD BasicHidden(const struct BasicAssist *a,UWORD line)
{ return line<BASIC_LINES ? (a->hidden[line>>3]>>(line&7))&1:0; }
WORD BasicFold(struct BasicAssist *a,UWORD index)
{
    UWORD line;WORD hidden;struct BasicProcedure *p;
    if (index>=a->count) return 0;p=&a->procedures[index];
    if (p->first==p->last) return 0;
    hidden=!BasicHidden(a,p->first+1);
    for (line=p->first+1;line<=p->last;++line) {
        if (hidden) a->hidden[line>>3]|=1U<<(line&7);else a->hidden[line>>3]&=~(1U<<(line&7));
    }
    return 1;
}
void BasicUnfold(struct BasicAssist *a,UWORD target)
{
    UWORD i,line;
    for (i=0;i<a->count;++i) if (a->procedures[i].first<target && a->procedures[i].last>=target)
        for (line=a->procedures[i].first+1;line<=a->procedures[i].last;++line) a->hidden[line>>3]&=~(1U<<(line&7));
}
UWORD BasicVisible(const struct BasicAssist *a,UWORD first,UWORD rows)
{
    while (rows-- && first<BASIC_LINES) {
        do { ++first; } while (first<BASIC_LINES && BasicHidden(a,first));
    }
    return first;
}
