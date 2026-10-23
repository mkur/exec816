/* Focused CR/LF buffer split and literal ATASCII, using the real stager. */
#define body QedUnusedStageBody
#define checked_body QedUnusedCheckedBody
#define main QedUnusedStageMain
#include "qed_stage.c"
#undef body
#undef checked_body
#undef main
static int edge(const char *target)
{
    LINEP line;BPTR file;unsigned i,steps;short status=0;int split=0;
    CHECK(QedPathPrepare(&path,target,1) && make(3,1023,lns_tos),201);
    memset(line_bytes,'z',1020);line=new_col(line_bytes,1020);CHECK(line,202);col_append(&ring,line);
    line=new_col("",0);CHECK(line,203);col_append(&ring,line);
    CHECK(QedStageBegin(&stage,&ring,&path),204);
    for(steps=0;steps<1024 && !status;steps++){
        status=QedStagePoll(&stage);
        if(stage.confirmed==4096 && stage.separator==1)split=1;
        CHECK(stage.produced<=4096 && stage.visits<=256,205);
    }
    CHECK(status==QED_STAGE_READY && split && stage.expected==4097 && verify(),206);
    file=Open(stage.name,MODE_OLDFILE);CHECK(file && Seek(file,4094,OFFSET_BEGINNING)>=0,207);
    CHECK(Read(file,read_bytes,3)==3 && !memcmp(read_bytes,"z\r\n",3) && Close(file),208);
    CHECK(dispose(),209);
    kill_textring(&ring);qed_ring_empty(&ring);ring.ending=lns_unix;
    line=new_col("\x80\x9b\xff\t",4);CHECK(line,210);col_append(&ring,line);
    CHECK(QedStageBegin(&stage,&ring,&path) && complete()==QED_STAGE_READY && stage.expected==4,211);
    CHECK(same(stage.name,"\x80\x9b\xff\t",4) && dispose(),212);
    QedPathRelease(&path);return 0;
}
static int body(int argc,char **argv)
{
    int result;init_memory();qed_ring_empty(&ring);
    result=edge("RAM:EDGE.TXT");if(result)return result;
    result=edge("D1:EDGE.TXT");if(result)return result;
    QedHeapSnapshot(&QedSavingHeap);QedSavingFinished=1;(void)AvailMem(MEMF_UPPER);
    kill_textring(&ring);kill_memory();return -321;
}
static int checked_body(int argc,char **argv)
{int result=body(argc,argv);QedProbeReturned=result;return result;}
int main(void){return QedRuntimeRun(checked_body);}
