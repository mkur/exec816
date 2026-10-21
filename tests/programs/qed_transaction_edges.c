/* Preflight admission, in-use/protected objects and ordinary metadata. */
#include "qed-transaction-support.inc"
static unsigned fail_prepare;
static struct FileInfoBlock before_info,after_info;
static char previous_bytes[8];
void *QedTxnAllocate(size_t count,size_t bytes)
{
    if(fail_prepare){fail_prepare=0;SetIoErr(ERROR_NO_FREE_STORE);return NULL;}
    return calloc(count,bytes);
}
static int body(int argc,char **argv)
{
    LONG previous_length;BPTR file,lock;struct QedHeapStats warm,after;unsigned i;const char *target,*backup;
    init_memory();qed_ring_empty(&ring);CHECK(make(2,2,lns_unix),401);QedHeapSnapshot(&warm);
    fail_prepare=1;CHECK(!QedSavePrepare("RAM:TARGET.TXT") && IoErr()==ERROR_NO_FREE_STORE,402);
    allocation_failure=1;CHECK(!QedSavePrepare("RAM:TARGET.TXT") && IoErr()==ERROR_NO_FREE_STORE,403);
    QedHeapSnapshot(&after);CHECK(warm.backing==after.backing && !QedFileCount(),404);
    for(i=0;i<2;i++){
        target=i ? "D1:BUSY.TXT":"RAM:BUSY.TXT";backup=i ? "D1:BUSY.BAK":"RAM:BUSY.BAK";
        CHECK(store(target,"old") && store(backup,"older"),405);
        file=Open(target,MODE_UPDATE_EXISTING);CHECK(file,406);
        CHECK(!QedSavePrepare(target) && IoErr()==ERROR_OBJECT_IN_USE && Close(file),407);
        file=Open(backup,MODE_UPDATE_EXISTING);CHECK(file,408);
        CHECK(!QedSavePrepare(target) && IoErr()==ERROR_OBJECT_IN_USE && Close(file),409);
        CHECK(same(target,"old",3) && same(backup,"older",5),410);
        CHECK(DeleteFile(target) && DeleteFile(backup),411);
    }
    CHECK(store("RAM:DIRB.TXT","old"),412);lock=CreateDir("RAM:DIRB.BAK");CHECK(lock,413);UnLock(lock);
    CHECK(!QedSavePrepare("RAM:DIRB.TXT") && IoErr()==ERROR_OBJECT_WRONG_TYPE,414);
    CHECK(DeleteFile("RAM:DIRB.TXT") && DeleteFile("RAM:DIRB.BAK"),415);
    CHECK(!QedSavePrepare("D1:PROTECT.TXT") && IoErr()==ERROR_DELETE_PROTECTED,416);
    CHECK(!QedSavePrepare("D1:BACKPROT.TXT") && IoErr()==ERROR_DELETE_PROTECTED,417);
    CHECK(same("D1:PROTECT.TXT","protected",9) && same("D1:BACKPROT.TXT","old",3) &&
        same("D1:BACKPROT.BAK","protected",9),418);
    CHECK(QedPathInfo("D1:META.TXT",&before_info)==1,419);
    file=Open("D1:META.TXT",MODE_OLDFILE);CHECK(file,423);
    previous_length=Read(file,previous_bytes,sizeof(previous_bytes));CHECK(previous_length>0 && Close(file),424);
    saving=QedSavePrepare("D1:META.TXT");CHECK(saving && QedSaveStart(saving,&ring,1,1) && finish()==QED_SAVE_SAVED,420);
    CHECK(QedPathInfo("D1:META.BAK",&after_info)==1 &&
        after_info.fib_Protection==before_info.fib_Protection &&
        !memcmp(&after_info.fib_Date,&before_info.fib_Date,sizeof(struct DateStamp)) &&
        same("D1:META.BAK",previous_bytes,previous_length),421);
    CHECK(QedPathInfo("D1:META.TXT",&after_info)==1 &&
        !(after_info.fib_Protection&(FIBF_ARCHIVE|FIBF_HIDDEN)) && expected_new(),422);
    QedSaveDispose(saving);saving=NULL;
    QedHeapSnapshot(&QedSavingHeap);QedSavingFinished=1;(void)AvailMem(MEMF_UPPER);
    kill_textring(&ring);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
