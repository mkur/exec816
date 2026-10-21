/* Execute restore_edit's real damage policy; observe its drawing boundary. */
#include "qed-runtime.h"
#include "global.h"
#include "window.h"
#include "text.h"
#include "ausgabe.h"
#include "edit.h"
#include <string.h>

static WINDOW view;
static TEXT text;
static short longest,draws;
static GRECT drawn;
short font_wcell=8,font_hcell=8;
WINDOWP get_window(short handle){return &view;}
TEXTP get_text(short handle){return &text;}
short get_longestline(TEXTP document){return longest;}
long cursor_xpos(TEXTP document,short position,bool *italic){return (long)position*8;}
void set_sliders(WINDOWP window,short which,short mode){}
void head_out(WINDOWP window,TEXTP document){}
void change_window(WINDOWP window,char *name,bool changed){}
short QedPointerState(void){return 0;}
void redraw_window(WINDOWP window,GRECT *area){drawn=*area;++draws;}
void arrow_window(WINDOWP window,short direction,long amount){}
short inote(short def,short undo,short index,short value){return 0;}

static void prepare(long x,long y,short width)
{
    memset(&view,0,sizeof(view));memset(&text,0,sizeof(text));
    view.doc.x=x;view.doc.y=y;view.w_width=10;view.w_height=4;
    view.work.g_x=8;view.work.g_y=40;view.work.g_w=80;view.work.g_h=32;
    text.text.lines=20;text.ypos=y+1;text.xpos=(short)x+1;
    longest=width;draws=0;
}
static int body(int argc,char **argv)
{
    prepare(0,0,40);make_chg(1,LINE_CHANGE,1);restore_edit();
    if(draws!=1 || drawn.g_y!=48 || drawn.g_h!=8)return 151;
    prepare(16,4,20);make_chg(1,LINE_CHANGE,5);restore_edit();
    if(view.doc.x!=10 || draws!=1 || drawn.g_y!=40 || drawn.g_h!=32)return 152;
    prepare(16,4,40);make_chg(1,LINE_CHANGE,5);restore_edit();
    if(view.doc.x!=16 || draws!=1 || drawn.g_y!=48 || drawn.g_h!=8)return 153;
    prepare(0,18,40);text.text.lines=20;text.ypos=17;
    make_chg(1,LINE_CHANGE,17);restore_edit();
    if(view.doc.y!=16 || draws!=1 || drawn.g_y!=40 || drawn.g_h!=32)return 154;
    prepare(0,0,40);make_chg(1,TOTAL_CHANGE,0);restore_edit();
    if(draws!=1 || drawn.g_h!=32)return 155;
    return -321;
}
int main(void){return QedRuntimeRun(body);}
