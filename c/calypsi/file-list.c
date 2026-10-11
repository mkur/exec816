/* Bounded caller-owned directory snapshots; no GUI or allocation policy. */
#include "file-list.h"
#include <string.h>

void FileScanEnd(struct FileScan *s)
{
    if (s->lock) { UnLock(s->lock); s->lock=0; }
}

WORD FileScanBegin(struct FileScan *s,const char *path,struct FileInfoBlock *info,
                   struct FileEntry *entries)
{
    s->error=0; s->info=info; s->entries=entries;
    s->lock=Lock(path,SHARED_LOCK);
    if (!s->lock) { s->error=IoErr(); return 0; }
    if (!Examine(s->lock,info)) s->error=IoErr();
    else if (info->fib_DirEntryType<=0) s->error=ERROR_OBJECT_WRONG_TYPE;
    if (s->error) { FileScanEnd(s); return 0; }
    s->count=s->truncated=0;
    return 1;
}

/* One entry per call; a final extra read detects capacity overflow. */
WORD FileScanNext(struct FileScan *s)
{
    struct FileEntry *e;
    if (ExNext(s->lock,s->info)) {
        if (s->count<FILE_LIST_LIMIT) {
            e=&s->entries[s->count++];
            strcpy(e->name,(const char *)s->info->fib_FileName);
            e->kind=s->info->fib_DirEntryType;
            return 1;
        }
        s->truncated=1;
    } else {
        s->error=IoErr();
        if (s->error==ERROR_NO_MORE_ENTRIES) s->error=0;
        else s->count=0;
    }
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
