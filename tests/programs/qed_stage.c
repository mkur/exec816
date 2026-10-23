/* Production serializer/stager; injections surround its actual adapter calls. */
#include "qed-stage.h"
#include "qed-files.h"
#include "memory.h"
#include "clipbrd.h"
#include <string.h>
#include <stdlib.h>
static RING ring;
static struct QedPath path;
static struct QedStage stage;
static char line_bytes[1023],read_bytes[1024];
static unsigned short mode,closes,deletes,writes,exhaust,allocation_failure;
volatile unsigned short QedSavingFinished,QedProbeCheck;
volatile short QedProbeReturned;
struct QedHeapStats QedSavingHeap;
void debug(char *format,...){}
short note(short def,short undo,short index){return 0;}
short inote(short def,short undo,short index,short value){return 0;}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
void *QedStageAllocate(size_t bytes)
{
    if(allocation_failure){allocation_failure=0;SetIoErr(ERROR_NO_FREE_STORE);return NULL;}
    return malloc(bytes);
}
LONG QedStageExclusive(const char *name)
{
    if(exhaust){SetIoErr(ERROR_OBJECT_EXISTS);return -36;}
    return QedFileExclusive(name);
}
LONG EXEC_CALL QedStageNativeWrite(BPTR file,const void *data,LONG bytes)
{
    LONG result;++writes;
    if(mode==3){SetIoErr(0);return 0;}
    if(mode==4){SetIoErr(ERROR_DISK_FULL);return -1;}
    if((mode==1 || mode==2 || mode==8) && bytes>137)bytes=137;
    result=Write(file,data,bytes);
    if(mode==2 || mode==5 || mode==8)SetIoErr(ERROR_DISK_FULL);
    return result;
}
LONG EXEC_CALL QedStageNativeClose(BPTR file)
{
    LONG result=Close(file);++closes;
    if(mode==6 || mode==8){SetIoErr(mode==6 ? ERROR_SEEK_ERROR:ERROR_BREAK);return 0;}
    return result;
}
LONG EXEC_CALL QedStageDelete(CONST_STRPTR name)
{
    ++deletes;
    if(mode==7){SetIoErr(ERROR_OBJECT_IN_USE);return 0;}
    return DeleteFile(name);
}
#define CHECK(x,n) do { QedProbeCheck=n;if(!(x))return n; } while(0)
static int make(unsigned lines,unsigned length,short ending)
{
    unsigned i;LINEP line;
    kill_textring(&ring);qed_ring_empty(&ring);ring.ending=ending;
    for(i=0;i<lines;i++){
        memset(line_bytes,'a'+i%26,length);
        if(length){line_bytes[0]='\t';line_bytes[length-1]=(char)(i%2 ? 255:128);}
        line=new_col(line_bytes,(short)length);if(!line)return 0;
        col_append(&ring,line);
    }
    return 1;
}
static short complete(void)
{
    unsigned short steps;short status=0;
    for(steps=0;steps<8192 && !status;steps++){
        status=QedStagePoll(&stage);
        if(stage.produced>4096 || stage.visits>256)return -1;
    }
    return status;
}
static int same(const char *name,const char *bytes,LONG length)
{
    BPTR file=Open(name,MODE_OLDFILE);LONG count;
    if(!file)return 0;
    count=Read(file,read_bytes,length);
    if(count!=length || memcmp(read_bytes,bytes,(unsigned)length)){Close(file);return 0;}
    count=Read(file,read_bytes,1);return Close(file) && !count;
}
static int verify(void)
{
    BPTR file=Open(stage.name,MODE_OLDFILE);LINEP line=FIRST(&ring);
    LONG total=0,count;unsigned i,offset=0,cr=0;unsigned char expected;
    if(!file)return 0;
    while((count=Read(file,read_bytes,sizeof(read_bytes)))>0){
        if(IoErr()){Close(file);return 0;}
        for(i=0;i<(unsigned)count;i++){
            if(IS_TAIL(line)){Close(file);return 0;}
            if(offset<(unsigned)line->len)expected=TEXT(line)[offset++];
            else{
                if(IS_TAIL(line->next)){Close(file);return 0;}
                if(ring.ending==lns_tos && !cr){expected=13;cr=1;}
                else{expected=10;cr=0;line=line->next;offset=0;}
            }
            if((unsigned char)read_bytes[i]!=expected){Close(file);return 0;}
        }
        total+=count;
    }
    if(count<0 || cr || (!IS_TAIL(line) &&
        (offset!=(unsigned)line->len || !IS_TAIL(line->next)))){Close(file);return 0;}
    return Close(file) && total==stage.expected && total==stage.confirmed;
}
static int dispose(void)
{
    QedStageCancel(&stage);
    if(complete()!=QED_STAGE_CANCELLED)return 0;
    QedStageDispose(&stage);return !QedFileCount();
}
static int store(const char *name,const char *bytes)
{
    BPTR file=Open(name,MODE_CREATE_EXCLUSIVE);
    return file && Write(file,bytes,(LONG)strlen(bytes))==(LONG)strlen(bytes) && Close(file);
}
static int exercise(const char *target,const char *backup)
{
    unsigned i;short status,slots[4];
    CHECK(QedPathPrepare(&path,target,1),101);
    CHECK(store(target,"original") && store(backup,"backup"),102);
    CHECK(make(1,0,lns_unix) && QedStageBegin(&stage,&ring,&path),103);
    CHECK(complete()==QED_STAGE_READY && stage.expected==0 && verify() && dispose(),104);
    CHECK(make(5,1023,lns_unix) && QedStageBegin(&stage,&ring,&path),105);
    CHECK(complete()==QED_STAGE_READY && verify() && dispose(),106);
    CHECK(make(5,1023,lns_tos) && QedStageBegin(&stage,&ring,&path),107);
    CHECK(complete()==QED_STAGE_READY && verify() && dispose(),108);
    CHECK(make(700,0,lns_tos) && QedStageBegin(&stage,&ring,&path),109);
    CHECK(complete()==QED_STAGE_READY && stage.expected==1398 && verify() && dispose(),110);
    CHECK(make(3,1023,lns_unix),111);
    for(i=1;i<=8;i++){
        if(i==7)continue;
        mode=i;closes=writes=deletes=0;
        CHECK(QedStageBegin(&stage,&ring,&path),112);status=complete();
        if(i==1){CHECK(status==QED_STAGE_READY && writes>3 && verify() && dispose(),113);}
        else if(i==6 || i==8){
            CHECK(status==QED_STAGE_UNCERTAIN && stage.cause==(i==6 ? ERROR_SEEK_ERROR:ERROR_DISK_FULL) &&
                stage.owned && !deletes && closes==1 && !QedFileCount(),114);
            if(i==8)CHECK(stage.cleanup==ERROR_BREAK && stage.confirmed==137,135);
            CHECK(DeleteFile(stage.name),115);QedStageDispose(&stage);
        }else{
            CHECK(status==QED_STAGE_FAILED && stage.cause==ERROR_DISK_FULL && !stage.owned &&
                writes==1 && closes==1 && !QedFileCount(),116);
            if(i==2)CHECK(stage.confirmed==137,117);
            if(i==5)CHECK(stage.confirmed==3071,118);
            QedStageDispose(&stage);
        }
        mode=0;
    }
    CHECK(QedStageBegin(&stage,&ring,&path),136);stage.expected=2147483647L;
    CHECK(complete()==QED_STAGE_FAILED && stage.cause==ERROR_BAD_NUMBER && !stage.owned,137);
    QedStageDispose(&stage);
    for(i=0;i<4;i++){slots[i]=(short)Fopen(target,0);CHECK(slots[i]>=3,140);}
    CHECK(QedStageBegin(&stage,&ring,&path),141);
    CHECK(complete()==QED_STAGE_FAILED && stage.cause==ERROR_NO_MORE_ENTRIES && !stage.owned,142);
    CHECK(!Lock(stage.name,SHARED_LOCK) && IoErr()==ERROR_OBJECT_NOT_FOUND,143);
    QedStageDispose(&stage);for(i=0;i<4;i++)CHECK(Fclose(slots[i])==0,144);
    allocation_failure=1;
    CHECK(!QedStageBegin(&stage,&ring,&path) && complete()==QED_STAGE_FAILED &&
        !stage.owned && !QedFileCount(),119);QedStageDispose(&stage);
    exhaust=1;CHECK(QedStageBegin(&stage,&ring,&path),120);
    CHECK(complete()==QED_STAGE_FAILED && stage.attempts==256 && !stage.owned,121);
    QedStageDispose(&stage);exhaust=0;
    CHECK(QedStageBegin(&stage,&ring,&path),122);
    while(!stage.owned)CHECK(QedStagePoll(&stage)==QED_STAGE_PENDING,123);
    QedStageCancel(&stage);CHECK(complete()==QED_STAGE_CANCELLED && !stage.owned && !QedFileCount(),124);
    QedStageDispose(&stage);
    CHECK(QedStageBegin(&stage,&ring,&path),125);
    while(!stage.owned)CHECK(QedStagePoll(&stage)==QED_STAGE_PENDING,126);
    mode=7;QedStageCancel(&stage);
    CHECK(complete()==QED_STAGE_FAILED && stage.cleanup==ERROR_OBJECT_IN_USE && stage.owned,127);
    mode=0;CHECK(DeleteFile(stage.name),128);QedStageDispose(&stage);
    CHECK(same(target,"original",8) && same(backup,"backup",6),129);
    CHECK(DeleteFile(target) && DeleteFile(backup),130);QedPathRelease(&path);
    return 0;
}
static int body(int argc,char **argv)
{
    int result;LINEP empty;struct QedHeapStats warm,after;
    init_memory();qed_ring_empty(&ring);
    CHECK(store("RAM:Q0000001.TMP","collision"),138);
    result=exercise("RAM:DEST.TXT","RAM:DEST.BAK");if(result)return result;
    CHECK(same("RAM:Q0000001.TMP","collision",9) && DeleteFile("RAM:Q0000001.TMP"),139);
    result=exercise("D1:DEST.TXT","D1:DEST.BAK");if(result)return result;
    CHECK(make(80,1023,lns_unix),131);empty=new_col("",0);CHECK(empty,132);col_append(&ring,empty);
    CHECK(QedPathPrepare(&path,"D1:DEST.TXT",1) && QedStageBegin(&stage,&ring,&path),133);
    CHECK(complete()==QED_STAGE_READY && stage.expected==81920L && verify(),134);
    /* Closed disk T remains an explicit staging artifact for host byte/allocation audit. */
    QedStageDispose(&stage);QedPathRelease(&path);
    QedHeapSnapshot(&QedSavingHeap);QedSavingFinished=1;(void)AvailMem(MEMF_UPPER);
    kill_textring(&ring);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
