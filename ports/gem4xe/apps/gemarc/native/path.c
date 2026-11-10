/* SPDX-License-Identifier: MIT. Native streaming enumeration, without a DTA. */
#include "platform.h"
#include "file-list.h"

int GemArcJoin(char *to,const char *directory,const char *leaf)
{
    if (FileJoin(to,GEM_PATH_MAX,directory,leaf)) return 1;
    GemArcFailure(ERROR_BAD_ARGUMENTS);return 0;
}
static int same(const char *a,const char *b)
{
    while (*a && *b) {
        char x=*a++,y=*b++;
        if (x>='a' && x<='z') x-=32;
        if (y>='a' && y<='z') y-=32;
        if (x!=y) return 0;
    }
    return *a==*b;
}
static int reserved(const char *name)
{
    unsigned int i;
    if (name[0]!='G' || strlen(name)!=12 || name[8]!='.') return 0;
    for (i=1;i<8;++i)
        if (!((name[i]>='0' && name[i]<='9') || (name[i]>='A' && name[i]<='F'))) return 0;
    return same(name+9,"TMP") || same(name+9,"OLD");
}

int GemArcCollect(const char *directory,const char *pattern,char (*names)[ARC_NAMELEN],
                  unsigned int capacity,const char *archive)
{
    struct FileInfoBlock *info=NULL;
    struct DirBatch *batch=NULL;
    BPTR lock=0,archive_lock=0;
    char physical_archive[256],candidate[256];
    LONG terminal=0;
    unsigned int count=0,index,received;
    int result=0;
    pf_reset();physical_archive[0]=0;
    info=malloc(sizeof(*info));
    batch=malloc(DIR_BATCH_HEADER_SIZE+8*DIR_ENTRY_SIZE);
    if (!info || !batch) { terminal=ERROR_NO_FREE_STORE;goto done; }
    archive_lock=Lock(archive,SHARED_LOCK);
    if (archive_lock) {
        if (!NameFromLock(archive_lock,physical_archive,sizeof physical_archive)) {
            terminal=IoErr();goto done;
        }
        UnLock(archive_lock);archive_lock=0;
    }
    lock=Lock(directory,SHARED_LOCK);
    if (!lock || !Examine(lock,info)) { terminal=IoErr();goto done; }
    if (info->fib_DirEntryType<=0) { terminal=ERROR_OBJECT_WRONG_TYPE;goto done; }
    for (;;) {
        if (GemArcPoll()) { result=-ARC_E_CANCEL;goto done; }
        batch->capacity=8;
        received=ExNextBatch(lock,info,batch);terminal=IoErr();
        if (!received && !terminal) { terminal=ERROR_BAD_NUMBER;break; }
        for (index=0;index<received;++index) {
            const struct DirEntry *entry=&batch->entries[index];
            const char *name=(const char *)entry->name;
            if (entry->kind>=0 || !FileMatch(pattern,name) || reserved(name)) continue;
            if (!GemArcJoin(candidate,directory,name)) { terminal=IoErr();goto done; }
            /* Compare canonical names, including a SYS:/D1: alias pair. */
            if (*physical_archive) {
                BPTR candidate_lock=Lock(candidate,SHARED_LOCK);
                if (!candidate_lock) { terminal=IoErr();goto done; }
                if (!NameFromLock(candidate_lock,candidate,sizeof candidate)) terminal=IoErr();
                UnLock(candidate_lock);
                if (terminal && terminal!=ERROR_NO_MORE_ENTRIES) goto done;
                if (same(candidate,physical_archive)) continue;
            }
            if (count==capacity) { result=-ARC_E_FULL;goto done; }
            strncpy(names[count],name,ARC_NAMELEN-1);names[count][ARC_NAMELEN-1]=0;
            ++count;
        }
        if (terminal) break;
    }
    if (terminal==ERROR_NO_MORE_ENTRIES) { terminal=0;result=count; }
done:
    if (archive_lock) UnLock(archive_lock);
    if (lock) UnLock(lock);
    free(batch);free(info);
    /* EOF can accompany a valid final prefix which reaches the batch limit. */
    if (terminal==ERROR_NO_MORE_ENTRIES) terminal=0;
    if (terminal) { GemArcFailure(terminal);return -ARC_E_READ; }
    return result;
}
