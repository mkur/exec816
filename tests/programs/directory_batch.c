#include <proto/dos.h>
#include <string.h>

/* The result array crosses a bank boundary; the runner owns its guard bytes. */
static struct DirBatch *batch=(struct DirBatch *)0x2dfff0;
static struct FileInfoBlock cursor,ordinary,saved;
static char path[32];
WORD abiOnly;
WORD filesystem;
LONG completed;

static LONG compare(BPTR lock,UWORD capacity)
{
    LONG n,error,total=0;
    UWORD i;
    if (!Examine(lock,&cursor) || !Examine(lock,&ordinary)) return 10;
    memcpy(&saved,&cursor,sizeof(cursor));
    batch->capacity=capacity;
    do {
        n=ExNextBatch(lock,&cursor,batch); error=IoErr();
        if (n<0 || n>capacity || (error && error!=ERROR_NO_MORE_ENTRIES)) return 11;
        if (n<capacity && error!=ERROR_NO_MORE_ENTRIES) return 12;
        for (i=0;i<n;++i) {
            struct DirEntry *entry=&batch->entries[i];
            if (!ExNext(lock,&ordinary)) return 13;
            if (strcmp((char *)ordinary.fib_FileName,(char *)entry->name) ||
                entry->kind!=ordinary.fib_DirEntryType || entry->size!=ordinary.fib_Size ||
                entry->infoFlags!=(ordinary.fib_InfoFlags&(FIB_SIZE_EXACT|FIB_SIZE_BOUND))) return 14;
            /* Independently known directory contents, including successive folders. */
            if (entry->kind>0) {
                if (strcmp((char *)entry->name,"ALPHA") && strcmp((char *)entry->name,"BETA")) return 15;
                if (entry->size) return 16;
            } else if (entry->name[0]!='F' || entry->name[1]<'0' || entry->name[1]>'1') return 17;
            ++total;
        }
        /* Batch only changes DiskKey and the existing private cookie (228..249). */
        if (memcmp((char *)&cursor+4,(char *)&saved+4,224) ||
            memcmp((char *)&cursor+250,(char *)&saved+250,10)) return 18;
    } while (!error);
    if (total!=20 || ExNext(lock,&ordinary) || IoErr()!=ERROR_NO_MORE_ENTRIES) return 19;
    if (ExNextBatch(lock,&cursor,batch) || IoErr()!=ERROR_NO_MORE_ENTRIES) return 20;
    completed+=total;
    return 0;
}

LONG main(void)
{
    BPTR lock,created;
    LONG result,n;
    UWORD i;
    if (filesystem==3) {
        created=CreateDir("RAM:DATA"); if (!created) return 1; UnLock(created);
        created=CreateDir("RAM:DATA/ALPHA"); if (!created) return 2; UnLock(created);
        created=CreateDir("RAM:DATA/BETA"); if (!created) return 3; UnLock(created);
        strcpy(path,"RAM:DATA/F00");
        for (i=0;i<18;++i) {
            path[10]='0'+i/10; path[11]='0'+i%10;
            created=Open(path,MODE_NEWFILE); if (!created || !Close(created)) return 4;
        }
    }
    lock=Lock(filesystem==3 ? "RAM:DATA":"D1:DATA",SHARED_LOCK);
    if (!lock || !Examine(lock,&cursor)) return 5;
    memcpy(&saved,&cursor,sizeof(cursor));
    memset(batch,0xa5,DIR_BATCH_HEADER_SIZE+16*DIR_ENTRY_SIZE);
    for (i=0;i<2;++i) {
        batch->capacity=i ? 17:0;
        if (ExNextBatch(lock,&cursor,batch) || IoErr()!=ERROR_BAD_ARGUMENTS ||
            memcmp(&saved,&cursor,sizeof(cursor)) || batch->entries[0].name[0]!=0xa5) return 6;
    }
    if (abiOnly) {
        batch->capacity=16;
        if (ExNextBatch(lock,&cursor,batch)!=16 || IoErr()) return 7;
        if (ExNextBatch(lock,&cursor,batch)!=4 || IoErr()!=ERROR_NO_MORE_ENTRIES) return 8;
    } else {
        result=compare(lock,1); if (result) return result;
        result=compare(lock,8); if (result) return result;
        result=compare(lock,16); if (result) return result;
        /* A shared cursor can alternate both operations without repeats or gaps. */
        if (!Examine(lock,&cursor) || !Examine(lock,&ordinary) || !ExNext(lock,&cursor) ||
            !ExNext(lock,&ordinary)) return 21;
        batch->capacity=8;
        if (ExNextBatch(lock,&cursor,batch)!=8 || IoErr()) return 22;
        for (i=0;i<8;++i) if (!ExNext(lock,&ordinary) ||
            strcmp((char *)ordinary.fib_FileName,(char *)batch->entries[i].name)) return 23;
        if (!ExNext(lock,&cursor) || !ExNext(lock,&ordinary) ||
            strcmp((char *)ordinary.fib_FileName,(char *)cursor.fib_FileName)) return 24;
        if (filesystem==3) {
            created=CreateDir("RAM:DATA/NEW"); if (!created) return 25; UnLock(created);
            if (ExNextBatch(lock,&cursor,batch) || IoErr()!=ERROR_OBJECT_IN_USE) return 26;
            if (!DeleteFile("RAM:DATA/NEW")) return 27;
        }
    }
    UnLock(lock);
    /* Empty and exact-multiple directories require an observed terminal call. */
    lock=Lock(filesystem==3 ? "RAM:DATA/ALPHA":"D1:EMPTY",SHARED_LOCK);
    if (!lock || !Examine(lock,&cursor)) return 28;
    batch->capacity=8;
    if (ExNextBatch(lock,&cursor,batch) || IoErr()!=ERROR_NO_MORE_ENTRIES) return 29;
    UnLock(lock);
    if (filesystem!=3) {
        lock=Lock("D1:EIGHT",SHARED_LOCK);
        if (!lock || !Examine(lock,&cursor)) return 30;
        if (ExNextBatch(lock,&cursor,batch)!=8 || IoErr()) return 31;
        if (ExNextBatch(lock,&cursor,batch) || IoErr()!=ERROR_NO_MORE_ENTRIES) return 32;
        UnLock(lock);
    }
    return 0;
}
