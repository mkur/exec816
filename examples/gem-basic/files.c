/* SPDX-License-Identifier: MIT */
#include "files.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>

static ULONG serial;
static void cause(struct BasicFileJob *j,LONG error)
{ if (!j->error) j->error=error ? error:ERROR_DISK_NOT_VALIDATED; }

static WORD release(struct BasicFileJob *j)
{
    WORD okay=1;
    BPTR handle=j->handle;j->handle=0;
    if (handle && !Close(handle)) { cause(j,IoErr());okay=0; }
    BasicDocumentDispose(&j->candidate);
    if (j->snapshot) { FreeMem(j->snapshot,j->save==2 ? j->bytes:BASIC_BYTES);j->snapshot=0; }
    j->phase=0;
    return okay;
}

void BasicFileCancel(struct BasicFileJob *j)
{
    WORD partial=j->save && !j->complete;
    if (j->phase) cause(j,ERROR_BREAK);
    WORD closed=release(j);
    /* A failed Close may leave uncertain media. Keep the reported path and
     * avoid mutation after uncertainty; completed copies are always retained. */
    if (partial && closed && j->temporary[0] && j->error==ERROR_BREAK) {
        if (DeleteFile(j->temporary)) j->temporary[0]=0;
    }
}

static WORD start(struct BasicFileJob *j,const char *path)
{
    memset(j,0,sizeof(*j));
    if (!path || !*path || strlen(path)>127) { j->error=ERROR_BAD_STREAM_NAME;return 0; }
    strcpy(j->named.path,path);j->phase=1;return 1;
}

WORD BasicLoadBegin(struct BasicFileJob *j,const char *path)
{
    if (!start(j,path)) return 0;
    if (BasicDocumentInit(&j->candidate)) {
        j->error=ERROR_NO_FREE_STORE;j->phase=0;return 0;
    }
    return 1;
}

WORD BasicSaveBegin(struct BasicFileJob *j,const struct BasicDocument *d,
                    const struct BasicFile *named,const char *path)
{
    if (!start(j,path)) return 0;
    j->save=1;j->named.eol=named->eol;
    j->snapshot=AllocMem(BASIC_BYTES,MEMF_UPPER);
    if (!j->snapshot) { j->error=ERROR_NO_FREE_STORE;j->phase=0;return 0; }
    j->bytes=d->bytes;j->generation=d->generation;
    BasicCopy(d,0,j->snapshot,d->bytes);
    return 1;
}

WORD BasicSaveBufferBegin(struct BasicFileJob *j,UBYTE *bytes,ULONG length,const char *path)
{
    if (!bytes || !length) { j->error=ERROR_BAD_NUMBER;return 0; }
    if (!start(j,path)) return 0;
    j->snapshot=bytes;j->bytes=length;j->save=2;return 1;
}

static void delimiter(struct BasicFileJob *j,UWORD style)
{
    if (!j->seen) j->named.eol=style;
    j->seen|=1U<<style;
}

static WORD append(struct BasicFileJob *j,UWORD n)
{
    WORD result=BasicReplace(&j->candidate,j->candidate.bytes,0,j->buffer,n);
    if (result) {
        j->error=result==BASIC_CHARACTER ? ERROR_BAD_STREAM_NAME:ERROR_OBJECT_TOO_LARGE;
        return 0;
    }
    /* A candidate has no user edits and cannot be observed before publication. */
    j->candidate.used=j->candidate.cursor=j->candidate.serial=j->candidate.generation=0;
    return 1;
}

static WORD load_step(struct BasicFileJob *j,struct BasicDocument *d,struct BasicFile *named)
{
    UBYTE c;LONG got,error;UWORD i,n=0;BPTR handle;
    if (j->phase==1) {
        j->handle=Open(j->named.path,MODE_OLDFILE);
        if (!j->handle) { cause(j,IoErr());return -1; }
        j->phase=2;return 0;
    }
    if (j->phase==2) {
        got=Read(j->handle,j->input,sizeof(j->input));error=IoErr();
        if (got<0 || error) { cause(j,error);return -1; }
        for (i=0;i<(UWORD)got;++i) {
            c=j->input[i];
            if (j->cr) {
                j->buffer[n++]=10;j->cr=0;delimiter(j,c==10 ? BASIC_EOL_CRLF:BASIC_EOL_CR);
                if (c==10) continue;
            }
            if (c==13) j->cr=1;
            else if (c==10 || c==155) {
                delimiter(j,c==10 ? BASIC_EOL_LF:BASIC_EOL_ATASCII);j->buffer[n++]=10;
            } else j->buffer[n++]=c;
        }
        if (!got && j->cr) { j->buffer[n++]=10;j->cr=0;delimiter(j,BASIC_EOL_CR); }
        if (n && !append(j,n)) return -1;
        if (!got) j->phase=3;
        return 0;
    }
    handle=j->handle;j->handle=0;
    if (!Close(handle)) { cause(j,IoErr());return -1; }
    if (j->seen && (j->seen&(j->seen-1))) j->candidate.generation=j->candidate.serial=1;
    BasicDocumentDispose(d);*d=j->candidate;memset(&j->candidate,0,sizeof(j->candidate));
    *named=j->named;j->phase=0;return 1;
}

/* All names stay in the target's directory and within the 127-byte bound.
 * Short paths use 8.3 names; deep paths use shorter native names. Collisions
 * are resolved by exclusive Open/no-replace Rename, never a check-then-open. */
static WORD unique_name(struct BasicFileJob *j,char *out,UBYTE kind)
{
    static const char hex[]="0123456789ABCDEF";
    static const char single[]="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    UWORD i,prefix=0,available,n;ULONG value;
    for (i=0;j->named.path[i];++i)
        if (j->named.path[i]==':' || j->named.path[i]=='/') prefix=i+1;
    available=127-prefix;
    if (!available || ++j->attempts>256 || (available==1 && j->attempts>36)) return 0;
    memcpy(out,j->named.path,prefix);
    value=++serial;
    if (available==1) { out[prefix]=single[value%36];out[prefix+1]=0;return 1; }
    n=available<8 ? available:8;
    out[prefix]=kind;
    for (i=1;i<n;++i) { out[prefix+n-i]=hex[value&15];value>>=4; }
    out[prefix+n]=0;
    if (available>=12) strcpy(out+prefix+n,kind=='B' ? ".TMP":".BAK");
    return 1;
}

static WORD save_step(struct BasicFileJob *j,struct BasicDocument *d,struct BasicFile *named)
{
    UWORD n=0;UBYTE c;LONG written,error;BPTR handle;
    if (j->phase==1) {
        if (!unique_name(j,j->temporary,'B')) { cause(j,ERROR_OBJECT_EXISTS);return -1; }
        j->handle=Open(j->temporary,MODE_CREATE_EXCLUSIVE);
        if (!j->handle) {
            error=IoErr();
            if (error==ERROR_OBJECT_EXISTS) { j->temporary[0]=0;return 0; }
            j->temporary[0]=0;cause(j,error);return -1;
        }
        j->phase=2;return 0;
    }
    if (j->phase==2) {
        if (j->offset==j->pending) {
            j->offset=j->pending=0;
            if (j->save==2) {
                n=j->bytes-j->at>sizeof(j->buffer) ? sizeof(j->buffer):j->bytes-j->at;
                memcpy(j->buffer,j->snapshot+j->at,n);j->at+=n;
            }
            while (j->save==1 && j->at<j->bytes && n<sizeof(j->buffer)) {
                c=j->snapshot[j->at];
                if (c==10 && j->named.eol==BASIC_EOL_CRLF) {
                    if (n+2>sizeof(j->buffer)) break;
                    j->buffer[n++]=13;j->buffer[n++]=10;
                } else j->buffer[n++]=c!=10 ? c:j->named.eol==BASIC_EOL_ATASCII ? 155:
                    j->named.eol==BASIC_EOL_CR ? 13:10;
                ++j->at;
            }
            j->pending=n;
        }
        if (!j->pending) { j->phase=3;return 0; }
        written=Write(j->handle,j->buffer+j->offset,j->pending-j->offset);error=IoErr();
        if (written<=0 || error) { cause(j,error ? error:ERROR_DISK_FULL);return -1; }
        j->offset+=(UWORD)written;return 0;
    }
    if (j->phase==3) {
        handle=j->handle;j->handle=0;
        if (!Close(handle)) { cause(j,IoErr());return -1; }
        j->complete=1;j->phase=4;return 0;
    }
    if (j->phase==4) {
        if (Rename(j->temporary,j->named.path)) { j->temporary[0]=0;j->phase=7;return 0; }
        error=IoErr();if (error!=ERROR_OBJECT_EXISTS) { cause(j,error);return -1; }
        j->attempts=0;j->phase=5;return 0;
    }
    if (j->phase==5) {
        if (!unique_name(j,j->backup,'R')) { cause(j,ERROR_OBJECT_EXISTS);return -1; }
        if (!Rename(j->named.path,j->backup)) {
            error=IoErr();j->backup[0]=0;
            if (error==ERROR_OBJECT_EXISTS) return 0;
            cause(j,error);return -1;
        }
        j->moved=1;j->phase=6;return 0;
    }
    if (j->phase==6) {
        if (!Rename(j->temporary,j->named.path)) { cause(j,IoErr());return -1; }
        j->temporary[0]=0;j->phase=7;return 0;
    }
    if (named) *named=j->named;
    if (j->save==1) d->saved=j->generation;
    if (j->moved && !DeleteFile(j->backup)) j->warning=IoErr();
    else j->backup[0]=0;
    release(j);return 1;
}

WORD BasicFileStep(struct BasicFileJob *j,struct BasicDocument *d,struct BasicFile *named)
{
    WORD result;
    if (!j->phase) return j->error ? -1:1;
    result=j->save ? save_step(j,d,named):load_step(j,d,named);
    if (result<0) release(j);
    return result;
}
