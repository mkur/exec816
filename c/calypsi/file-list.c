/* Bounded caller-owned snapshots with one temporary upper-memory batch. */
#include "file-list.h"
#include <proto/exec.h>
#include <exec/memory.h>
#include <string.h>
#define BATCH_BYTES (DIR_BATCH_HEADER_SIZE+FILE_SCAN_BATCH*DIR_ENTRY_SIZE)

void FileScanEnd(struct FileScan *s)
{
    if (s->lock) { UnLock(s->lock); s->lock=0; }
    if (s->batch) { FreeMem(s->batch,BATCH_BYTES); s->batch=NULL; }
    s->info=NULL; s->entries=NULL;
    s->buffered=s->next=s->currentFlags=0;
    s->terminal=s->currentSize=0;
}

WORD FileScanBegin(struct FileScan *s,const char *path,struct FileInfoBlock *info,
                   struct FileEntry *entries)
{
    s->error=0; s->lock=0; s->info=info; s->entries=entries;
    s->buffered=s->next=s->currentFlags=0; s->terminal=s->currentSize=0;
    s->batch=AllocMem(BATCH_BYTES,MEMF_UPPER);
    if (!s->batch) { s->error=ERROR_NO_FREE_STORE; FileScanEnd(s); return 0; }
    s->lock=Lock(path,SHARED_LOCK);
    if (!s->lock) { s->error=IoErr(); FileScanEnd(s); return 0; }
    if (!Examine(s->lock,info)) s->error=IoErr();
    else if (info->fib_DirEntryType<=0) s->error=ERROR_OBJECT_WRONG_TYPE;
    if (s->error) { FileScanEnd(s); return 0; }
    s->count=s->truncated=0;
    return 1;
}

/* Consume locally; only refills cross DOS. A final one-record probe detects
 * overflow without ever publishing entry 257 into the retained array. */
WORD FileScanNext(struct FileScan *s)
{
    struct FileEntry *e;
    struct DirEntry *record;
    if (!s->batch) return 0;
    if (s->next==s->buffered && !s->terminal) {
        UWORD remaining=FILE_LIST_LIMIT-s->count;
        s->batch->capacity=remaining>FILE_SCAN_BATCH ? FILE_SCAN_BATCH:remaining ? remaining:1;
        s->buffered=ExNextBatch(s->lock,s->info,s->batch);
        s->terminal=IoErr(); s->next=0;
        if (!s->buffered && !s->terminal) s->terminal=ERROR_BAD_NUMBER;
    }
    if (s->next<s->buffered) {
        if (s->count<FILE_LIST_LIMIT) {
            record=&s->batch->entries[s->next++];
            e=&s->entries[s->count++];
            strcpy(e->name,(const char *)record->name);
            e->kind=record->kind;
            s->currentSize=record->size; s->currentFlags=record->infoFlags;
            return 1;
        }
        if (!s->terminal || s->terminal==ERROR_NO_MORE_ENTRIES) s->truncated=1;
    }
    s->error=s->terminal==ERROR_NO_MORE_ENTRIES ? 0:s->terminal;
    if (s->error) s->count=0;
    FileScanEnd(s);
    return 0;
}

static char upper(char c)
{
    return c>='a' && c<='z' ? c-'a'+'A':c;
}

/* GEM's two-part 8.3 wildcard semantics, including empty trailing positions.
 * Reference: pinned GEM4XE src/sys/dos.c:dos_wildcmp (see binding inputs). */
WORD FileMatch(const char *pattern,const char *name)
{
    WORD part;
    for (part=0;part<2;++part) {
        for (;*name && *name!='.';++name) {
            if (*pattern=='*') continue;
            if (*pattern!='?' && upper(*pattern)!=upper(*name)) return 0;
            ++pattern;
        }
        while (*pattern=='*' || *pattern=='?') ++pattern;
        if (*pattern=='.') ++pattern;
        if (*name=='.') ++name;
    }
    return *pattern==*name;
}

WORD FileFilter(const struct FileEntry *entries,WORD count,const char *pattern,WORD *indices)
{
    WORD i,n=0;
    for (i=0;i<count;++i)
        if (entries[i].kind>0 || FileMatch(pattern,entries[i].name)) indices[n++]=i;
    return n;
}

WORD FileFirst(WORD first,WORD count,WORD visible)
{
    if (first>count-visible) first=count-visible;
    return first<0 ? 0:first;
}

WORD FileExpose(WORD first,WORD selected,WORD visible)
{
    if (selected<first) first=selected;
    if (selected>=first+visible) first=selected-visible+1;
    return first;
}

/* Capacity includes NUL; destination may alias directory, never leaf. */
WORD FileJoin(char *to,WORD capacity,const char *directory,const char *leaf)
{
    WORD n=strlen(directory),length=strlen(leaf),slash=n && directory[n-1]!=':' && directory[n-1]!='/';
    if (n+slash+length>=capacity) return 0;
    if (to!=directory) memmove(to,directory,n);
    if (slash) to[n++]='/';
    memcpy(to+n,leaf,length+1);
    return 1;
}

void FileParent(char *path)
{
    WORD n=strlen(path);
    if (n && path[n-1]=='/') --n;
    while (n && path[n-1]!=':' && path[n-1]!='/') --n;
    if (n && path[n-1]=='/') --n;
    path[n]=0;
}

/* Caller provides 128 bytes for each output. No GEMDOS drive translation. */
WORD FileSplit(const char *path,char *directory,char *mask)
{
    WORD n=0,split=0,colon=0,i;
    if (!*path) path="SYS:*.*";
    while (n<128 && path[n]) {
        if (path[n]=='\\') return 0;
        if (path[n]==':') { if (colon || !n) return 0; colon=1; split=n+1; }
        else if (path[n]=='/') { if (!colon) return 0; split=n+1; }
        ++n;
    }
    if (n==128 || !colon) return 0;
    for (i=0;i<split;++i) if (path[i]=='*' || path[i]=='?') return 0;
    if (n==split) strcpy(mask,"*.*"); else strcpy(mask,path+split);
    if (split && path[split-1]=='/') --split;
    memcpy(directory,path,split); directory[split]=0;
    /* Adding the default filter must also fit the public path buffer. */
    return split+strlen(mask)+(path[split-1]==':' ? 0:1)<128;
}

WORD FileLeaf(const char *name)
{
    WORD base=0,ext=0,dot=0;
    if (*name>='0' && *name<='9') return 0;
    for (;*name;++name) {
        char ch=*name;
        if (ch=='.') { if (dot || !base) return 0; dot=1; continue; }
        if (!((ch>='a' && ch<='z') || (ch>='A' && ch<='Z') ||
              (ch>='0' && ch<='9') || ch=='_' || ch=='@' || ch=='`')) return 0;
        if (dot) { if (++ext>3) return 0; }
        else if (++base>8) return 0;
    }
    return base && (!dot || ext);
}
