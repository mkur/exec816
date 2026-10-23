/* Preauthorized core intents. These hooks do not establish GUI consent. */
#define body QedUnusedStageBody
#define checked_body QedUnusedCheckedBody
#define main QedUnusedStageMain
#include "qed_stage.c"
#undef body
#undef checked_body
#undef main
#include "qed-save.h"
static struct QedSave *saving;
static unsigned rename_calls,delete_calls,fail_mask,unknown_mask,fail_delete,escrow_exhaust;
static LONG rename_error=ERROR_OBJECT_IN_USE;
volatile unsigned short QedTransactionCases;
LONG EXEC_CALL QedTxnRename(CONST_STRPTR before,CONST_STRPTR after)
{
    unsigned bit;++rename_calls;
    bit=rename_calls<=16 ? 1U<<(rename_calls-1):0;
    if(escrow_exhaust && strstr(after,".OLD")){SetIoErr(ERROR_OBJECT_EXISTS);return 0;}
    if((fail_mask|unknown_mask)&bit){SetIoErr(unknown_mask&bit ? ERROR_SEEK_ERROR:rename_error);return 0;}
    return Rename(before,after);
}
LONG EXEC_CALL QedTxnDelete(CONST_STRPTR name)
{
    ++delete_calls;
    if(fail_delete){SetIoErr(fail_delete==2 ? ERROR_SEEK_ERROR:ERROR_OBJECT_IN_USE);return 0;}
    return DeleteFile(name);
}
static void reset(void)
{
    rename_calls=delete_calls=fail_mask=unknown_mask=fail_delete=escrow_exhaust=0;
    rename_error=ERROR_OBJECT_IN_USE;mode=exhaust=0;
}
static short finish(void)
{
    unsigned steps;short result=0;
    for(steps=0;steps<8192 && !result;steps++)result=QedSavePoll(saving);
    return result;
}
static int absent(const char *path)
{
    BPTR lock=Lock(path,SHARED_LOCK);
    if(lock){UnLock(lock);return 0;}
    return IoErr()==ERROR_OBJECT_NOT_FOUND;
}
/* Explicit fixture/operator cleanup after assertions. Production never uses it. */
static void discard_artifacts(void)
{
    if(saving->stage.name[0])DeleteFile(saving->stage.name);
    if(saving->escrow[0])DeleteFile(saving->escrow);
    DeleteFile(saving->target.name);DeleteFile(saving->backup);
    QedSaveDispose(saving);saving=NULL;
}
static int setup(const char *target,const char *backup,int old_target,int old_backup)
{
    reset();
    if(old_target && !store(target,"old"))return 0;
    if(old_backup && !store(backup,"older"))return 0;
    saving=QedSavePrepare(target);return saving!=NULL;
}
static int expected_new(void)
{return same(saving->target.name,"\t\x80\n\t\xff",5);}
static int transaction_cases(const char *target,const char *backup)
{
    unsigned i,calls;short result;char escrow[256];struct QedHeapStats warm,after;
    CHECK(make(2,2,lns_unix),301);
    CHECK(setup(target,backup,0,1) && !saving->backup_exists,302);
    CHECK(QedSaveStart(saving,&ring,0,0) && finish()==QED_SAVE_SAVED && expected_new() &&
        same(backup,"older",5) && rename_calls==1 && !delete_calls,303);
    discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,0),304);
    CHECK(!QedSaveStart(saving,&ring,0,0) && saving->result==QED_SAVE_CANCELLED &&
        !rename_calls && same(target,"old",3),305);discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,1),306);
    CHECK(!QedSaveStart(saving,&ring,1,0) && saving->result==QED_SAVE_CANCELLED &&
        same(target,"old",3) && same(backup,"older",5),307);discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,0) && QedSaveStart(saving,&ring,1,1),308);
    CHECK(finish()==QED_SAVE_SAVED && expected_new() && same(backup,"old",3) &&
        rename_calls==2 && !delete_calls,309);discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),310);
    CHECK(finish()==QED_SAVE_SAVED && expected_new() && same(backup,"old",3) &&
        rename_calls==3 && delete_calls==1 && absent(saving->escrow),311);
    QedSaveDispose(saving);saving=NULL;
    /* Repeated saving retains exactly one previous version, with warm backing. */
    QedHeapSnapshot(&warm);
    for(i=0;i<12;i++){
        saving=QedSavePrepare(target);CHECK(saving && QedSaveStart(saving,&ring,1,1),312);
        CHECK(finish()==QED_SAVE_SAVED && expected_new() && same(backup,"\t\x80\n\t\xff",5),313);
        QedSaveDispose(saving);saving=NULL;
    }
    QedHeapSnapshot(&after);CHECK(after.backing==warm.backing && !QedFileCount(),314);
    CHECK(DeleteFile(target) && DeleteFile(backup),315);QedTransactionCases++;
    /* Every forward rename, both reversals and post-publication deletion. */
    for(i=0;i<8;i++){
        CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),316);
        if(i<3)fail_mask=1U<<i;
        else if(i==3)fail_mask=4|8;
        else if(i==4)fail_mask=4|16;
        else if(i==5){fail_mask=4;rename_error=ERROR_OBJECT_EXISTS;mode=7;}
        else fail_delete=i==6 ? 1:2;
        result=finish();CHECK(result==(i==7 ? QED_SAVE_UNCERTAIN:QED_SAVE_FAILED),317);
        CHECK(saving->cause==(i==5 ? ERROR_OBJECT_EXISTS:(i==7 ? ERROR_SEEK_ERROR:ERROR_OBJECT_IN_USE)),318);
        if(i<3){CHECK(same(target,"old",3) && same(backup,"older",5) && !saving->stage.owned,319);}
        else if(i==3){
            CHECK(absent(target) && same(backup,"old",3) && same(saving->escrow,"older",5) &&
                saving->stage.owned && rename_calls==4 && saving->cleanup==ERROR_OBJECT_IN_USE,320);
        }else if(i==4){
            CHECK(same(target,"old",3) && absent(backup) && same(saving->escrow,"older",5) &&
                saving->stage.owned && rename_calls==5 && saving->cleanup==ERROR_OBJECT_IN_USE,321);
        }else if(i==5){
            CHECK(same(target,"old",3) && same(backup,"older",5) && saving->stage.owned &&
                saving->cleanup==ERROR_OBJECT_IN_USE,322);
        }else{
            CHECK(saving->published && expected_new() && same(backup,"old",3) &&
                same(saving->escrow,"older",5) && !saving->stage.owned,323);
        }
        calls=rename_calls;QedSavePoll(saving);QedSavePoll(saving);CHECK(calls==rename_calls,324);
        discard_artifacts();QedTransactionCases++;
    }
    /* Unknown injected outcomes retain names and never attempt reversal/deletion. */
    for(i=0;i<3;i++){
        CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),325);
        unknown_mask=1U<<i;CHECK(finish()==QED_SAVE_UNCERTAIN && rename_calls==i+1 &&
            !delete_calls && saving->stage.owned && saving->cause==ERROR_SEEK_ERROR,326);
        discard_artifacts();QedTransactionCases++;
    }
    CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),327);
    escrow_exhaust=1;CHECK(finish()==QED_SAVE_FAILED && saving->attempts==256 &&
        same(target,"old",3) && same(backup,"older",5) && !saving->stage.owned,328);
    discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),329);
    QedSaveCancel(saving);CHECK(finish()==QED_SAVE_CANCELLED && !rename_calls &&
        same(target,"old",3) && same(backup,"older",5),330);discard_artifacts();QedTransactionCases++;
    CHECK(setup(target,backup,1,1) && QedSaveStart(saving,&ring,1,1),331);
    mode=6;CHECK(finish()==QED_SAVE_UNCERTAIN && !rename_calls && saving->stage.created &&
        saving->stage.close_done && !saving->stage.close_ok,332);mode=0;discard_artifacts();QedTransactionCases++;
    return 0;
}
static int body(int argc,char **argv)
{
    int result;BPTR lock;unsigned calls;
    init_memory();qed_ring_empty(&ring);CHECK(make(2,2,lns_unix),333);
    /* First real E collision is claimed by Rename, without an empty placeholder. */
    CHECK(store("RAM:Q0000002.OLD","foreign") && setup("RAM:REAL.TXT","RAM:REAL.BAK",1,1),334);
    CHECK(QedSaveStart(saving,&ring,1,1) && finish()==QED_SAVE_SAVED && saving->attempts==2 &&
        same("RAM:Q0000002.OLD","foreign",7),335);
    discard_artifacts();CHECK(DeleteFile("RAM:Q0000002.OLD"),336);QedTransactionCases++;
    result=transaction_cases("RAM:DEST.TXT","RAM:DEST.BAK");if(result)return result;
    result=transaction_cases("D1:DEST.TXT","D1:DEST.BAK");if(result)return result;
    CHECK(setup("RAM:DATA.BAK","RAM:DATA.BKP",1,1) && !strcmp(saving->backup,"RAM:DATA.BKP") &&
        QedSaveStart(saving,&ring,1,1) && finish()==QED_SAVE_SAVED && same("RAM:DATA.BKP","old",3),337);
    discard_artifacts();QedTransactionCases++;
    lock=CreateDir("RAM:DIR.TXT");CHECK(lock,338);UnLock(lock);
    CHECK(!QedSavePrepare("RAM:DIR.TXT") && IoErr()==ERROR_OBJECT_WRONG_TYPE && DeleteFile("RAM:DIR.TXT"),339);
    /* Keep a successful D/B pair for independent closed-ATR bytes/allocation audit. */
    DeleteFile("D1:AUDIT.TXT");DeleteFile("D1:AUDIT.BAK");
    CHECK(setup("D1:AUDIT.TXT","D1:AUDIT.BAK",1,1) && QedSaveStart(saving,&ring,1,1) &&
        finish()==QED_SAVE_SAVED && expected_new() && same("D1:AUDIT.BAK","old",3),340);
    QedSaveDispose(saving);saving=NULL;QedTransactionCases++;
    QedHeapSnapshot(&QedSavingHeap);QedSavingFinished=1;(void)AvailMem(MEMF_UPPER);
    kill_textring(&ring);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
