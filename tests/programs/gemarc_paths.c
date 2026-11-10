/* SPDX-License-Identifier: MIT. Native enumeration and metadata edges. */
#include "platform.h"
#include "internal.h"
#include <stdio.h>
#include <errno.h>
static unsigned int failure,allocations,batches;
static char names[64][ARC_NAMELEN],path[48];
void *GemArcPathMalloc(size_t bytes)
{
    if (++allocations==failure) { errno=ENOMEM;return NULL; }
    return malloc(bytes);
}
LONG EXEC_CALL GemArcPathNext(BPTR lock,struct FileInfoBlock *info,struct DirBatch *batch)
{
    if (failure==3 && ++batches==2) { SetIoErr(0x0000c219L);return 0; }
    return ExNextBatch(lock,info,batch);
}
int GemArcPoll(void) { ExecYield();return 0; }
#define CHECK(test,n) do { if (!(test)) return n; } while (0)
int main(void)
{
    struct ExecCRuntimeHeapStats before,after;
    struct DateStamp stamp={16860,1439,2900};
    struct FileInfoBlock info;
    uint16_t date,time;
    BPTR lock;
    unsigned int i;
    char directory[24];
    snprintf(directory,sizeof directory,"RAM:D%06lX",(ULONG)FindTask(NULL)&0xffffffUL);
    lock=CreateDir(directory);CHECK(lock,101);UnLock(lock);
    for (i=0;i<65;++i) {
        FILE *file;
        snprintf(path,sizeof path,"%s/F%07u.DAT",directory,i);
        file=fopen(path,"wbx");CHECK(file,102);CHECK(fclose(file)==0,103);
    }
    GemArcIOBegin();
    ExecCRuntimeHeapSnapshot(&before);
    CHECK(GemArcCollect(directory,"*.DAT",names,64,"SYS:CORPUS.ARC")==-ARC_E_FULL,104);
    for (failure=1;failure<=3;++failure) {
        allocations=batches=0;
        CHECK(GemArcCollect(directory,"*.DAT",names,64,"SYS:CORPUS.ARC")==-ARC_E_READ,105);
        CHECK(GemArcCause()==(failure==3 ? 0x0000c219L:ERROR_NO_FREE_STORE),106);
        ExecCRuntimeHeapSnapshot(&after);
        CHECK(after.blocks==before.blocks && after.payload==before.payload,107);
    }
    failure=0;
    CHECK(GemArcCollect(directory,"F000000?.DAT",names,64,"SYS:CORPUS.ARC")==10,108);
    CHECK(GemArcCollect(directory,"*.NO",names,64,"SYS:CORPUS.ARC")==0,109);
    snprintf(path,sizeof path,"%s/F0000000.DAT",directory);
    CHECK(SetFileDate(path,&stamp),110);
    pf_stamp(path,&date,&time);
    CHECK(date==((2024-1980)<<9|2<<5|29) && time==(23<<11|59<<5|29),111);
    stamp.ds_Days=0;stamp.ds_Minute=stamp.ds_Tick=0;
    CHECK(SetFileDate(path,&stamp),112);
    CHECK(pf_setstamp(path,date,time)==0,113);
    lock=Lock(path,SHARED_LOCK);CHECK(lock,114);
    CHECK(ExamineExact(lock,&info),115);UnLock(lock);
    CHECK(info.fib_Date.ds_Days==16860 && info.fib_Date.ds_Minute==1439 && info.fib_Date.ds_Tick==2900,116);
    for (i=0;i<65;++i) {
        snprintf(path,sizeof path,"%s/F%07u.DAT",directory,i);CHECK(DeleteFile(path),117);
    }
    CHECK(DeleteFile(directory),118);
    /* SYS is physically mounted read-only in this fixture. */
    CHECK(pf_create("SYS:NOFILE.DAT")<0 && GemArcCause()==ERROR_DISK_WRITE_PROTECTED,119);
    SetIoErr(0);return -321;
}
