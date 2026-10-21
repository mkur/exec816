/* Actual reader/ring/Undo ownership. GUI dispatch has its own loaded cohort. */
#include "qed-runtime.h"
#include "qed-document.h"
#include "qed-files.h"
#include "memory.h"
#include "clipbrd.h"
#include "block.h"
#include "tasten.h"
#include "text.h"
#include "window.h"
#include <string.h>
static TEXT text,saved;
static WINDOW window;
static LOCOPT options;
static unsigned short allocation,line_failure,short_read,read_failure,close_failure,reads,closes;
volatile unsigned short QedDocumentFinished;
struct QedHeapStats QedDocumentHeap;
bool overwrite,clip_on_disk;
long undo_y;
void *QedDocAllocate(size_t bytes)
{
    if(allocation && --allocation==0)return NULL;
    return malloc(bytes);
}
LINEP QedDocLine(char *bytes,short length)
{
    if(line_failure && --line_failure==0)return NULL;
    return new_col(bytes,length);
}
LONG QedDocRead(WORD fd,LONG bytes,void *buffer)
{
    ++reads;
    if(read_failure && --read_failure==0){SetIoErr(ERROR_BREAK);return -1;}
    if(short_read && bytes>short_read)bytes=short_read;
    return Fread(fd,bytes,buffer);
}
LONG QedDocClose(WORD fd)
{
    LONG result=Fclose(fd);++closes;
    if(close_failure){close_failure=0;SetIoErr(ERROR_SEEK_ERROR);return -1;}
    return result;
}
void debug(char *format,...){}
short note(short def,short undo,short index){return 0;}
short inote(short def,short undo,short index,short value){return 0;}
WORD QedDocAlert(WORD button,const char *message){return 0;}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
void make_chg(short link,short kind,long row){}
void end_play(void){}
void cursor_visible(WINDOWP view,TEXTP document){}
WINDOWP get_window(short handle){return &window;}
void QedPointerCancel(void){}
void set_wtitle(WINDOWP view,char *name){}
void set_text_name(TEXTP document,char *name,bool unnamed)
{strcpy(document->filename,name);document->namenlos=unnamed;}
OBJECT *strings;
long get_obspec(OBJECT *objects,short id){return (long)(char *)"Untitled";}
static bool same(RINGP ring,const char *bytes)
{
    LINEP line=FIRST(ring);long row;short i;
    for(row=0;row<ring->lines;row++){
        if(line->prev->next!=line || line->next->prev!=line)return FALSE;
        for(i=0;i<line->len;i++)if(!*bytes || TEXT(line)[i]!=*bytes++)return FALSE;
        if(row+1<ring->lines && *bytes++!='\n')return FALSE;
        line=line->next;
    }
    return !*bytes && line==&ring->tail;
}
static short complete(void)
{
    unsigned short steps;short status=0;
    for(steps=0;steps<4096 && status==0;steps++)status=QedDocumentPoll();
    return status;
}
static bool unchanged(void)
{
    return !memcmp(&text,&saved,sizeof(text)) && same(&text.text,"keepx") &&
        same(&clip_text,"k") && any_undo() && window.doc.x==3 && window.doc.y==7;
}
static bool reject(const char *name)
{
    bool started=QedDocumentBegin(name);
    if(started && complete()!=-1)return FALSE;
    return QedDocumentRing()->lines==0 && QedFileCount()==0 && unchanged();
}
#define CHECK(test,code) do{if(!(test))return code;}while(0)
static int body(int argc,char **argv)
{
    RINGP ring;LINEP line;short i;struct QedHeapStats warm,after;
    int count;char **parsed;
    CHECK(!QedArguments("a b","qed",&count,&parsed) && IoErr()==ERROR_BAD_ARGUMENTS,100);
    CHECK(QedArguments("  \"SYS:SMALL.TXT\" ","qed",&count,&parsed) && count==2 &&
        !strcmp(parsed[1],"SYS:SMALL.TXT"),101);free(parsed);
    init_memory();CHECK(init_clipbrd() && init_textring(&text.text),102);
    kill_textring(&text.text);qed_ring_empty(&text.text);
    line=new_col("keep",4);CHECK(line!=NULL,103);col_append(&text.text,line);
    text.link=1;text.loc_opt=&options;text.cursor_line=line;text.cursor=TRUE;text.xpos=4;
    char_insert(&text,'x');CHECK(same(&text.text,"keepx") && any_undo(),104);
    text.xpos=0;blk_mark(&text,0);text.xpos=1;blk_mark(&text,1);blk_copy(&text);
    window.doc.x=3;window.doc.y=7;saved=text;
    CHECK(QedDocumentBegin("SYS:EMPTY.TXT") && complete()==1,105);
    CHECK(same(QedDocumentRing(),"") && QedDocumentRing()->ending==lns_unix && unchanged(),106);
    QedDocumentCancel();CHECK(unchanged(),107);
    CHECK(reject("NOLAST.TXT") && QedDocumentError()==ERROR_NO_DEFAULT_DIR,140);
    CHECK(QedDocumentBegin("SYS:NOLAST.TXT") && complete()==1 && same(QedDocumentRing(),"a\tb"),108);
    QedDocumentCancel();
    CHECK(QedDocumentBegin("SYS:SMALL.TXT") && complete()==1 && same(QedDocumentRing(),"alpha\tbeta\nsecond\n"),109);
    QedDocumentCancel();
    CHECK(QedDocumentBegin("SYS:CRLF.TXT") && complete()==1 && same(QedDocumentRing(),"one\nlast") &&
        QedDocumentRing()->ending==lns_tos,110);QedDocumentCancel();
    CHECK(QedDocumentBegin("SYS:BOUNDARY.TXT") && complete()==1,111);
    ring=QedDocumentRing();CHECK(ring->lines==5 && ring->ending==lns_tos,112);
    line=FIRST(ring);for(i=0;i<3;i++){CHECK(line->len==1023,113);line=line->next;}
    CHECK(line->len==1020 && !memcmp(TEXT(line),"bbbb",4) && line->next->len==4,114);QedDocumentCancel();
    CHECK(reject("SYS:NUL.TXT") && QedDocumentError()==ERROR_BAD_ARGUMENTS,115);
    CHECK(reject("SYS:MIXED.TXT") && reject("SYS:MIXED2.TXT"),116);
    CHECK(reject("SYS:CR.TXT") && reject("SYS:ENDCR.TXT") && reject("SYS:WIDE.TXT"),117);
    CHECK(reject("SYS:MISSING.TXT") && QedDocumentError()==ERROR_OBJECT_NOT_FOUND,118);
    allocation=1;CHECK(reject("SYS:SMALL.TXT") && QedDocumentError()==ERROR_NO_FREE_STORE,119);
    allocation=2;CHECK(reject("SYS:SMALL.TXT") && QedDocumentError()==ERROR_NO_FREE_STORE,120);
    line_failure=2;CHECK(reject("SYS:SMALL.TXT") && QedDocumentError()==ERROR_NO_FREE_STORE,121);
    reads=closes=0;read_failure=2;close_failure=1;
    CHECK(reject("SYS:BOUNDARY.TXT") && QedDocumentError()==ERROR_BREAK && reads==2 && closes==1,122);
    closes=0;close_failure=1;
    CHECK(reject("SYS:SMALL.TXT") && QedDocumentError()==ERROR_SEEK_ERROR && closes==1,123);
    short_read=137;reads=0;
    CHECK(QedDocumentBegin("SYS:BOUNDARY.TXT") && complete()==1 && reads>2 &&
        QedDocumentRing()->lines==5 && QedDocumentRing()->ending==lns_tos,124);
    QedDocumentCancel();short_read=0;
    CHECK(QedDocumentBegin("SYS:LONG.TXT") && QedDocumentPoll()==0,125);
    QedDocumentCancel();CHECK(unchanged() && QedFileCount()==0,126);
    qed_undo(&text);CHECK(same(&text.text,"keep"),127);qed_undo(&text);CHECK(same(&text.text,"keepx"),128);
    CHECK(QedDocumentBegin("SYS:LONG.TXT") && complete()==1,129);
    QedDocumentCommit(&text);
    CHECK(text.text.lines==81 && FIRST(&text.text)->len==1023 && LAST(&text.text)->len==0 &&
        !text.moved && !text.block && text.xpos==0 && text.ypos==0 && !any_undo() &&
        !window.doc.x && !window.doc.y && !strcmp(text.filename,"SYS:LONG.TXT") && same(&clip_text,"k"),130);
    CHECK(QedDocumentBegin("SYS:LONG.TXT") && complete()==1,131);
    QedHeapSnapshot(&QedDocumentHeap);QedDocumentCancel();
    CHECK(text.text.lines==81 && !text.moved && same(&clip_text,"k"),132);
    CHECK(QedDocumentBegin(NULL) && complete()==1,133);QedDocumentCommit(&text);
    CHECK(same(&text.text,"") && text.namenlos && !text.moved && text.text.ending==lns_unix,134);
    CHECK(QedDocumentBegin("SYS:SMALL.TXT") && complete()==1,135);QedDocumentCommit(&text);
    CHECK(QedDocumentBegin(NULL) && complete()==1,136);QedDocumentCommit(&text);
    QedHeapSnapshot(&warm);
    for(i=0;i<16;i++){
        CHECK(QedDocumentBegin("SYS:SMALL.TXT") && complete()==1,137);QedDocumentCommit(&text);
        CHECK(QedDocumentBegin(NULL) && complete()==1,138);QedDocumentCommit(&text);
    }
    QedHeapSnapshot(&after);CHECK(after.backing==warm.backing && QedFileCount()==0 && same(&clip_text,"k"),139);
    QedDocumentFinished=1;(void)AvailMem(MEMF_UPPER);
    clr_undo();kill_textring(&clip_text);kill_textring(&text.text);kill_memory();
    return -321;
}
int main(void){return QedRuntimeRun(body);}
