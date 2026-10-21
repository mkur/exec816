/* Actual donor ring/clipboard/Undo code; GUI delivery has a separate cohort. */
#include "qed-runtime.h"
#include "global.h"
#include "memory.h"
#include "block.h"
#include "clipbrd.h"
#include "tasten.h"
#include <string.h>
static TEXT text;
static WINDOW window;
static LOCOPT options;
static unsigned short errors,fail_line;
static short damage_kind;
volatile unsigned short QedClipboardFinished;
struct QedHeapStats QedClipboardHeap;
bool overwrite,clip_on_disk;
long undo_y;
LINEP QedCoreNewCol(char *bytes,short length)
{
    if(fail_line && --fail_line==0)return NULL;
    return new_col(bytes,length);
}
WORD QedRecordAlert(WORD button,const char *message){++errors;return 0;}
short note(short def,short undo,short index){++errors;return 0;}
short inote(short def,short undo,short index,short value){++errors;return 0;}
void debug(char *format,...){}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
void end_play(void){}
void make_chg(short link,short kind,long row){if(kind!=POS_CHANGE)damage_kind=kind;}
void cursor_visible(WINDOWP view,TEXTP document){}
WINDOWP get_window(short handle){return &window;}
static bool equals(RINGP ring,const char *expected)
{
    LINEP line=FIRST(ring);long row;short i;
    for(row=0;row<ring->lines;row++){
        if(line->prev->next!=line || line->next->prev!=line)return FALSE;
        for(i=0;i<line->len;i++)if(!*expected || TEXT(line)[i]!=*expected++)return FALSE;
        if(row+1<ring->lines && *expected++!='\n')return FALSE;
        line=line->next;
    }
    return *expected==0 && line==&ring->tail;
}
static bool document(const char *bytes)
{
    const char *start=bytes;LINEP line;
    clr_undo();kill_textring(&text.text);memset(&text,0,sizeof(text));
    qed_ring_empty(&text.text);
    for(;;bytes++)if(*bytes=='\n' || !*bytes){
        line=new_col((char *)start,(short)(bytes-start));if(!line)return FALSE;
        col_append(&text.text,line);if(!*bytes)break;start=bytes+1;
    }
    text.cursor_line=FIRST(&text.text);text.cursor=TRUE;text.loc_opt=&options;text.link=1;
    return TRUE;
}
static void select_range(long y1,short x1,long y2,short x2)
{
    text.ypos=y1;text.xpos=x1;text.cursor_line=get_line(&text.text,y1);blk_mark(&text,0);
    text.ypos=y2;text.xpos=x2;text.cursor_line=get_line(&text.text,y2);blk_mark(&text,1);
}
static bool wide_lines(RINGP ring,unsigned short count)
{
    LINEP line=FIRST(ring);unsigned short row,i;
    if(ring->lines!=count)return FALSE;
    for(row=0;row<count;row++){
        if(line->len!=1023)return FALSE;
        for(i=0;i<1023;i++)if(TEXT(line)[i]!='a')return FALSE;
        line=line->next;
    }
    return line==&ring->tail;
}
#define CHECK(test,code) do{if(!(test))return code;}while(0)
static int body(int argc,char **argv)
{
    unsigned short before,i;LINEP saved;static char wide[1024],joined[2048];
    struct QedHeapStats warm,after;
    init_memory();CHECK(init_clipbrd(),100);
    CHECK(document("ab\tcd\n\nefgh"),101);select_range(0,1,2,2);blk_copy(&text);
    CHECK(equals(&clip_text,"b\tcd\n\nef") && !text.moved && text.block,102);
    blk_demark(&text);blk_copy(&text);CHECK(equals(&clip_text,"b\tcd\n\nef"),103);
    select_range(0,1,2,2);blk_cut(&text);
    CHECK(equals(&text.text,"agh") && equals(&clip_text,"b\tcd\n\nef") && text.xpos==1 && any_undo(),104);
    fail_line=1;qed_undo(&text);
    CHECK(equals(&text.text,"ab\tcd\n\nefgh") && text.block && text.ypos==2 && text.xpos==2 && fail_line==1,105);
    qed_undo(&text);CHECK(equals(&text.text,"agh") && !text.block && fail_line==1,106);fail_line=0;
    blk_paste(&text,&clip_text);CHECK(equals(&text.text,"ab\tcd\n\nefgh") && text.xpos==2 && text.ypos==2,107);
    qed_undo(&text);CHECK(equals(&text.text,"agh"),108);qed_undo(&text);
    select_range(0,5,1,0);blk_copy(&text);CHECK(equals(&clip_text,"\n"),109);
    blk_delete(&text);CHECK(equals(&text.text,"ab\tcd\nefgh"),110);
    blk_paste(&text,&clip_text);CHECK(equals(&text.text,"ab\tcd\n\nefgh"),111);
    /* Every clipboard and replacement allocation boundary preserves all owners. */
    select_range(0,1,2,2);blk_copy(&text);qed_undo(&text);qed_undo(&text);
    select_range(0,1,2,2);before=errors;saved=text.cursor_line;
    fail_line=2;blk_copy(&text);
    CHECK(errors==before+1 && equals(&clip_text,"b\tcd\n\nef") && text.cursor_line==saved && text.block,112);
    before=errors;fail_line=4;blk_cut(&text);
    CHECK(errors==before+1 && equals(&text.text,"ab\tcd\n\nefgh") && equals(&clip_text,"b\tcd\n\nef") && text.block,113);
    before=errors;fail_line=2;blk_paste(&text,&clip_text);
    CHECK(errors==before+1 && equals(&text.text,"ab\tcd\n\nefgh") && text.cursor_line==saved && text.block,114);
    fail_line=0;qed_undo(&text);CHECK(equals(&text.text,"ab\tcd\nefgh"),115);
    /* Typing coalesces on one line; an edit after Undo starts a fresh group. */
    CHECK(document(""),116);char_insert(&text,'a');char_insert(&text,'b');char_insert(&text,'c');
    CHECK(damage_kind==LINE_CHANGE,141);
    qed_undo(&text);CHECK(equals(&text.text,""),117);qed_undo(&text);CHECK(equals(&text.text,"abc"),118);
    qed_undo(&text);char_insert(&text,'x');qed_undo(&text);CHECK(equals(&text.text,""),119);
    char_cr(&text);CHECK(equals(&text.text,"\n") && damage_kind==TOTAL_CHANGE,120);
    qed_undo(&text);CHECK(equals(&text.text,"") && damage_kind==TOTAL_CHANGE,121);
    /* Selected replacement is one operation group, including line joins. */
    CHECK(document("one\ntwo\nthree"),122);select_range(0,1,2,2);
    CHECK(edit_key(&text,&window,0,'X'),123);CHECK(equals(&text.text,"oXree"),124);
    qed_undo(&text);CHECK(equals(&text.text,"one\ntwo\nthree") && text.block,125);
    /* A boundary overflow retains both the previous Undo and clipboard. */
    memset(wide,'a',1023);wide[1023]=0;CHECK(document(wide),126);
    select_range(0,0,0,1023);blk_copy(&text);blk_demark(&text);text.xpos=0;
    before=errors;blk_paste(&text,&clip_text);
    CHECK(errors==before+1 && equals(&text.text,wide) && equals(&clip_text,wide) && !text.moved,127);
    memcpy(joined,wide,1023);joined[1023]='\n';memcpy(joined+1024,wide,1024);
    CHECK(document(joined),131);text.xpos=1023;before=errors;
    CHECK(edit_key(&text,&window,0,0x5300),132);
    CHECK(errors==before+1 && equals(&text.text,joined) && text.xpos==1023 && !text.moved,133);
    CHECK(document("repeat"),128);select_range(0,0,0,6);blk_copy(&text);blk_cut(&text);blk_paste(&text,&clip_text);
    QedHeapSnapshot(&warm);
    for(i=0;i<32;i++){
        select_range(0,0,0,6);blk_cut(&text);blk_paste(&text,&clip_text);qed_undo(&text);qed_undo(&text);
        CHECK(equals(&text.text,"repeat"),129);
    }
    QedHeapSnapshot(&after);CHECK(after.backing==warm.backing,130);
    /* The three owners span multiple 64 KiB banks; Undo still allocates nothing. */
    CHECK(document(""),134);kill_textring(&text.text);qed_ring_empty(&text.text);
    for(i=0;i<80;i++){
        saved=new_col(wide,1023);CHECK(saved!=NULL,135);col_append(&text.text,saved);
    }
    text.cursor_line=FIRST(&text.text);select_range(0,0,79,1023);blk_copy(&text);
    CHECK(wide_lines(&clip_text,80),136);blk_cut(&text);
    CHECK(equals(&text.text,"") && wide_lines(&clip_text,80),137);
    text.text.ending=lns_tos;blk_paste(&text,&clip_text);
    CHECK(wide_lines(&text.text,80) && text.text.ending==lns_tos && clip_text.ending==lns_unix,138);
    fail_line=1;qed_undo(&text);CHECK(equals(&text.text,"") && fail_line==1,139);
    qed_undo(&text);CHECK(wide_lines(&text.text,80) && fail_line==1,140);fail_line=0;
    QedHeapSnapshot(&QedClipboardHeap);QedClipboardFinished=1;
    (void)AvailMem(MEMF_UPPER);
    clr_undo();kill_textring(&clip_text);kill_textring(&text.text);kill_memory();return -321;
}
int main(void){return QedRuntimeRun(body);}
