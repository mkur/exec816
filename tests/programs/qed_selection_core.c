/* Actual navigation/block routines. Notification/geometry sinks claim no GUI. */
#include "qed-runtime.h"
#include "global.h"
#include "memory.h"
#include "tasten.h"
#include "block.h"
#include <string.h>
static TEXT text;
static WINDOW window;
static LOCOPT options;
static unsigned short errors;
bool overwrite,clip_on_disk;
long undo_y;
WORD QedRecordAlert(WORD button,const char *message){++errors;return 0;}
short note(short def,short undo,short index){++errors;return 0;}
short inote(short def,short undo,short index,short value){++errors;return 0;}
void debug(char *format,...){}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
void end_play(void){}
void make_chg(short link,short kind,long row){}
void cursor_visible(WINDOWP view,TEXTP document){}
WINDOWP get_window(short handle){return &window;}
static bool range(long first,short x,long last,short end)
{return text.block && text.z1==first && text.x1==x && text.z2==last && text.x2==end;}
static void key(short qualifiers,unsigned short scan)
{if(!edit_key(&text,&window,qualifiers,(short)(scan<<8)))++errors;}
static int body(int argc,char **argv)
{
    LINEP first,last;
    init_memory();if(!init_textring(&text.text))return 101;
    first=new_col("ab\tcd",5);last=new_col("efgh",4);
    if(!first || !last)return 102;
    col_insert(&text.text,&text.text.head,first);++text.text.lines;
    col_append(&text.text,last);
    options.tab=TRUE;options.tabsize=8;text.loc_opt=&options;
    text.cursor_line=first;text.xpos=1;text.link=1;window.w_height=2;
    key(K_LSHIFT,0x4d);if(!range(0,1,0,2) || text.xpos!=2)return 103;
    key(K_LSHIFT,0x4d);if(!range(0,1,0,3) || text.xpos!=3)return 104;
    key(K_LSHIFT,0x4b);if(!range(0,1,0,2))return 105;
    key(K_LSHIFT,0x4b);if(text.block || text.xpos!=1)return 106;
    key(K_LSHIFT,0x4b);if(!range(0,0,0,1) || !text.block_dir)return 107;
    key(K_LSHIFT,0x50);if(!range(0,1,1,0) || text.ypos!=1)return 108;
    key(0,0x48);if(text.block || text.xpos!=1 || text.ypos)return 109;
    key(K_LSHIFT,0x4f);if(!range(0,1,0,5))return 110;
    key(0,0x4d);if(text.block || text.xpos!=5)return 111;
    key(K_LSHIFT|K_CTRL,0x47);if(!range(0,0,0,5) || text.xpos)return 112;
    key(K_CTRL,0x4f);if(text.block)return 113;
    if(text.ypos!=2)return 120+(short)text.ypos;
    if(text.xpos!=4)return 130+text.xpos;
    key(K_LSHIFT,0x49);if(!range(0,2,2,4) || text.ypos)return 114;
    key(K_LSHIFT,0x51);if(text.block || text.ypos!=2 || text.xpos!=4)return 115;
    if(errors || text.moved || text.text.lines!=3 || memcmp(TEXT(first),"ab\tcd",5) ||
       memcmp(TEXT(last),"efgh",4))return 116;
    kill_textring(&text.text);kill_memory();return -321;
}
int main(void){return QedRuntimeRun(body);}
