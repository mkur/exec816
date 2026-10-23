/* Actual source operational closure; no alternate serializer or transaction. */
#define body QedUnusedStageBody
#define checked_body QedUnusedCheckedBody
#define main QedUnusedStageMain
#include "qed_stage.c"
#undef body
#undef checked_body
#undef main
#include "qed-save.h"
#include <exec816/runtime.h>
#include <stdio.h>
volatile UWORD QedOperationalMode,QedOperationalPoint,QedOperationalGate,QedFilesystemMode;
volatile UWORD QedOperationalWrites,QedOperationalCloses,QedOperationalRenames,QedOperationalDeletes;
volatile UWORD QedOperationalCases;
ULONG QedOperationalResult[12],QedOperationalMemory[8];
static struct QedSave *saving;
static UWORD late_cancel;

LONG QedOperationalWrite(WORD fd,LONG bytes,const void *data)
{
    ++QedOperationalWrites;
    if(QedOperationalMode==1 || (QedOperationalMode==2 &&
       QedOperationalWrites==(QedOperationalPoint==2 ? 2:1))){
        QedOperationalGate=0;QedOperationalPoint=1;
        while(!QedOperationalGate)ExecYield();
    }
    return Fwrite(fd,bytes,data);
}
LONG EXEC_CALL QedOperationalClose(BPTR file)
{++QedOperationalCloses;return Close(file);}
LONG EXEC_CALL QedOperationalRename(CONST_STRPTR before,CONST_STRPTR after)
{++QedOperationalRenames;return Rename(before,after);}
LONG EXEC_CALL QedOperationalDelete(CONST_STRPTR name)
{
    ++QedOperationalDeletes;
    if(late_cancel && saving && saving->published){QedSaveCancel(saving);late_cancel=0;}
    return DeleteFile(name);
}
static short finish_save(void)
{
    unsigned steps;short result=0;ULONG available;
    for(steps=0;steps<8192 && !result;steps++){
        result=QedSavePoll(saving);available=AvailMem(MEMF_UPPER);
        if(!QedOperationalMemory[3] || available<QedOperationalMemory[3])QedOperationalMemory[3]=available;
    }
    return result;
}
static int large_store(const char *name,LONG bytes,int fill_to_full)
{
    BPTR file;char *buffer;LONG count,total=0,cause=0;unsigned visits=0;int closed;
    buffer=malloc(4096);if(!buffer)return 0;memset(buffer,0x59,4096);
    file=Open(name,MODE_CREATE_EXCLUSIVE);if(!file){free(buffer);return 0;}
    while(total<bytes && visits++<1024){
        count=bytes-total;if(count>4096)count=4096;
        count=Write(file,buffer,count);cause=IoErr();
        if(count>0)total+=count;
        if(count<=0 || cause)break;
    }
    closed=Close(file)!=0;free(buffer);
    return closed && (fill_to_full ? cause==ERROR_DISK_FULL:(!cause && total==bytes));
}
static int exact_large(const char *name)
{
    LONG count;unsigned line,column;
    short fd=(short)Fopen(name,0);if(fd<0)return 0;
    for(line=0;line<80;line++){
        count=Fread(fd,1024,read_bytes);if(count!=1024 || IoErr())return 0;
        for(column=0;column<1024;column++){
            unsigned char wanted=column==0 ? 9:(column==1023 ? 10:
                (column==1022 ? (line%2 ? 255:128):'a'+line%26));
            if((unsigned char)read_bytes[column]!=wanted)return 0;
        }
    }
    count=Fread(fd,1,read_bytes);return count==0 && !IoErr() && Fclose(fd)==0;
}
static int prepare(const char *name)
{
    saving=QedSavePrepare(name);
    return saving && QedSaveStart(saving,&ring,1,1);
}
static void release(void){QedSaveDispose(saving);saving=NULL;}
static int normal_cases(void)
{
    UWORD i,files;char name[32];struct QedHeapStats warm,after;
    CHECK(make(80,1023,lns_unix),501);
    {LINEP empty=new_col("",0);CHECK(empty,502);col_append(&ring,empty);}
    QedOperationalMemory[0]=AvailMem(MEMF_UPPER);
    CHECK(large_store("RAM:LARGE.TXT",81920,0) && large_store("RAM:LARGE.BAK",81920,0),503);
    QedOperationalMemory[1]=AvailMem(MEMF_UPPER);
    CHECK(prepare("RAM:LARGE.TXT"),504);QedOperationalMemory[2]=AvailMem(MEMF_UPPER);
    CHECK(finish_save()==QED_SAVE_SAVED && exact_large("RAM:LARGE.TXT"),505);release();
    QedOperationalMemory[4]=AvailMem(MEMF_UPPER);
    CHECK(DeleteFile("RAM:LARGE.TXT") && DeleteFile("RAM:LARGE.BAK"),506);
    QedOperationalMemory[5]=AvailMem(MEMF_UPPER);QedOperationalCases++;
    CHECK(make(4,1023,lns_unix),507);{LINEP empty=new_col("",0);CHECK(empty,530);col_append(&ring,empty);}
    DeleteFile("D1:AUDIT.TXT");DeleteFile("D1:AUDIT.BAK");
    CHECK(store("D1:AUDIT.TXT","old") && store("D1:AUDIT.BAK","older"),508);
    CHECK(prepare("D1:AUDIT.TXT"),509);
    while(!saving->stage.created)CHECK(!QedSavePoll(saving),510);
    CHECK(large_store("D1:FILL.BIN",1048576,1),511);
    CHECK(finish_save()==QED_SAVE_FAILED && saving->cause==ERROR_DISK_FULL &&
        !saving->moved_target && !saving->moved_backup && saving->stage.close_ok && !QedFileCount(),512);
    CHECK(same("D1:AUDIT.TXT","old",3) && same("D1:AUDIT.BAK","older",5),513);release();
    CHECK(DeleteFile("D1:FILL.BIN"),514);QedOperationalCases++;
    if(QedFilesystemMode==1){
        files=0;
        for(i=0;i<64;i++){
            BPTR file;sprintf(name,"D1:FULL%02u.TXT",i);file=Open(name,MODE_CREATE_EXCLUSIVE);
            if(!file)break;CHECK(Close(file),515);files++;
        }
        CHECK(files>0 && files<64 && prepare("D1:AUDIT.TXT"),516);
        CHECK(finish_save()==QED_SAVE_FAILED && !saving->stage.created && !saving->moved_target,517);release();
        for(i=0;i<files;i++){sprintf(name,"D1:FULL%02u.TXT",i);CHECK(DeleteFile(name),518);}
        QedOperationalCases++;
    }
    CHECK(prepare("D1:AUDIT.TXT") && finish_save()==QED_SAVE_SAVED,519);release();
    QedHeapSnapshot(&warm);
    for(i=0;i<12;i++){
        CHECK(prepare("D1:AUDIT.TXT") && finish_save()==QED_SAVE_SAVED,520);release();
        QedHeapSnapshot(&after);CHECK(after.blocks==warm.blocks && after.backing==warm.backing,521);
    }
    QedOperationalCases++;
    CHECK(DeleteFile("D1:AUDIT.BAK") && large_store("D1:AUDIT.BAK",65536,0),522);
    CHECK(prepare("D1:AUDIT.TXT"),523);late_cancel=1;
    CHECK(finish_save()==QED_SAVE_SAVED && !late_cancel && !saving->stage.owned && !saving->moved_backup,524);
    release();QedOperationalCases++;
    return 0;
}
static int interrupted_case(void)
{
    short result;
    CHECK(make(8,1023,lns_unix),531);{LINEP empty=new_col("",0);CHECK(empty,530);col_append(&ring,empty);}
    CHECK(prepare("D1:DEST.TXT"),532);result=finish_save();
    QedOperationalResult[0]=result;QedOperationalResult[1]=saving->cause;
    QedOperationalResult[2]=saving->cleanup;QedOperationalResult[3]=saving->stage.confirmed;
    QedOperationalResult[4]=saving->stage.close_done;QedOperationalResult[5]=saving->stage.close_ok;
    QedOperationalResult[6]=saving->stage.owned;QedOperationalResult[7]=saving->published;
    QedOperationalResult[8]=QedOperationalRenames;QedOperationalResult[9]=QedOperationalDeletes;
    QedOperationalResult[10]=QedOperationalCloses;
    CHECK(result==QED_SAVE_UNCERTAIN && saving->cause && !saving->published &&
        !QedOperationalRenames && !QedOperationalDeletes && !QedFileCount() && saving->stage.close_done,533);
    if(QedOperationalMode==2)CHECK(saving->cause==ERROR_BREAK,534);
    release();QedOperationalCases++;return 0;
}
static int body(int argc,char **argv)
{
    int result;init_memory();qed_ring_empty(&ring);
    result=QedOperationalMode ? interrupted_case():normal_cases();if(result)return result;
    kill_textring(&ring);QedHeapSnapshot(&QedSavingHeap);QedSavingFinished=1;
    (void)AvailMem(MEMF_UPPER);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
