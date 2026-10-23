/* Consistent fixed MyDOS root exhaustion, before any staging file exists. */
#include "qed-operational-support.inc"
static int body(int argc,char **argv)
{
    short result;init_memory();qed_ring_empty(&ring);
    CHECK(make(1,3,lns_unix) && prepare("D1:DEST.TXT"),551);
    result=finish_save();
    CHECK(result==QED_SAVE_FAILED &&
        (saving->cause==ERROR_DISK_FULL || saving->cause==ERROR_NO_MORE_ENTRIES) &&
        !saving->stage.created && !QedOperationalRenames && !QedOperationalDeletes &&
        !QedOperationalCloses && !QedFileCount(),552);
    CHECK(same("D1:DEST.TXT","old",3) && same("D1:DEST.BAK","older",5),553);
    release();kill_textring(&ring);QedOperationalCases=1;QedHeapSnapshot(&QedSavingHeap);
    QedSavingFinished=1;(void)AvailMem(MEMF_UPPER);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
