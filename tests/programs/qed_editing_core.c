/* Actual editing/text-store routines with fixture notification sinks.
 * Application GUI behavior is checked separately through the loaded editor.
 */
#include "qed-runtime.h"
#include "global.h"
#include "memory.h"
#include "tasten.h"
#include <proto/dos.h>
#include <stdlib.h>
#include <string.h>

static unsigned short errors;
static short refuse;
static TEXT text;
bool overwrite;
long undo_y;
APTR EXEC_CALL QedFixtureAlloc(ULONG bytes,ULONG flags)
{return refuse?NULL:AllocMem(bytes,flags);}
WORD QedRecordAlert(WORD button,const char *message){++errors;return 0;}
short note(short def,short undo,short index){++errors;return 0;}
short inote(short def,short undo,short index,short value){++errors;return 0;}
void debug(char *format,...){}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
void end_play(void){}
void make_chg(short link,short kind,long row){}

static int body(int argc,char **argv)
{
    unsigned short i,before;
    LINEP old,extra;
    init_memory();
    if(!init_textring(&text.text))return 101;
    text.cursor_line=FIRST(&text.text);
    for(i=0;i<1023;i++)char_insert(&text,'a');
    if(text.cursor_line->len!=1023 || text.xpos!=1023)return 102;
    old=text.cursor_line;before=errors;text.moved=0;
    char_insert(&text,'b');
    if(text.cursor_line!=old || text.xpos!=1023 || text.moved || errors!=before+1)return 103;
    for(i=0;i<1023;i++)if(TEXT(old)[i]!='a')return 104;
    /* Actual upper-heap failure after exhausting donor-arena free blocks. */
    refuse=1;
    for(i=0;i<4096;i++){
        extra=new_col(TEXT(old),1023);
        if(!extra)break;
        col_append(&text.text,extra);
    }
    if(i==4096)return 105;
    /* Splitting needs smaller blocks; exhaust those residual fragments too. */
    for(i=0;i<16384;i++){
        extra=new_col("",0);
        if(!extra)break;
        col_append(&text.text,extra);
    }
    if(i==16384)return 108;
    before=errors;overwrite=TRUE;text.xpos=512;
    char_insert(&text,'b');
    if(text.cursor_line!=old || text.xpos!=512 || TEXT(old)[512]!='a' || text.moved || errors!=before+1)return 106;
    before=errors;char_cr(&text);
    if(text.cursor_line!=old || text.xpos!=512 || text.moved || errors!=before+1)return 107;
    refuse=0;kill_textring(&text.text);kill_memory();return -321;
}
int main(void){return QedRuntimeRun(body);}
