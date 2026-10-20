/* SPDX-License-Identifier: GPL-3.0-only
 * Emitted drawing-argument probe for the actual adapted QED module. These
 * recording callbacks belong only to this fixture. Native pixels follow QS3.
 */
#include "global.h"
#include "ausgabe.h"
#include "memory.h"
#include <proto/dos.h>
#include <string.h>
short vdi_handle=2,font_wcell=8,font_hcell=8;
short fg_color=1,bg_color=0,fg_block_color=0,bg_block_color=1;
static struct { LINE header; char bytes[128]; } storage;
static TEXT document;
static WINDOW window;
static LOCOPT options;
static WORD points[4],textX,textY,bars,texts,fill,ink;
static char drawn[81];
void QedRecordBar(WORD h,const WORD *p)
{ unsigned i;for(i=0;i<4;i++)points[i]=p[i];++bars; }
WORD QedRecordFill(WORD h,WORD pen){fill=pen;return pen;}
WORD QedRecordInk(WORD h,WORD pen){ink=pen;return pen;}
void QedRecordText(WORD h,WORD x,WORD y,const char *text)
{ textX=x;textY=y;strcpy(drawn,text);++texts; }
#define CHECK(x) do { if(!(x))return __LINE__+100; } while(0)
int main(void)
{
    bool italic;
    document.cursor_line=&storage.header;document.loc_opt=&options;
    document.text.lines=1;document.ypos=0;storage.header.len=3;
    memcpy(TEXT(&storage.header),"QED",4);
    window.work.g_x=100;window.work.g_y=30;window.work.g_w=80;window.work.g_h=8;
    line_out(&window,&document,0);
    CHECK(bars==1 && texts==1 && !strcmp(drawn,"QED"));
    CHECK(points[0]==100 && points[1]==30 && points[2]==179 && points[3]==37 && fill==0);
    CHECK(textX==100 && textY==36 && ink==1);
    options.tab=TRUE;options.tabsize=4;
    memcpy(TEXT(&storage.header),"A\tB",4);
    line_out(&window,&document,0);CHECK(!strcmp(drawn,"A   B"));
    CHECK(cursor_xpos(&document,3,&italic)==40 && !italic);
    CHECK(bild_pos(2,&storage.header,TRUE,4)==4);
    window.doc.x=2;line_out(&window,&document,0);CHECK(!strcmp(drawn,"  B"));
    window.doc.x=0;window.work.g_w=16;
    line_out(&window,&document,0);CHECK(!strcmp(drawn,"A "));
    {
        WORD before=texts;
        line_out(&window,&document,1);CHECK(texts==before && points[1]==38);
        storage.header.len=0;line_out(&window,&document,0);CHECK(texts==before);
    }
    SetIoErr(0);return -321;
}
