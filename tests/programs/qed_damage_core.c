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
void arrow_window(WINDOWP window,short direction,long amount)
{
    if(direction==WA_DNLINE)window->doc.y+=amount;
    else if(direction==WA_UPLINE)window->doc.y-=amount;
    else if(direction==WA_RTLINE)window->doc.x+=amount;
    else if(direction==WA_LFLINE)window->doc.x-=amount;
    redraw_window(window,&window->work);
}
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
    prepare(0,0,40);make_chg(1,BLK_CHANGE,1);make_chg(1,BLK_CHANGE,1);restore_edit();
    if(draws!=1 || drawn.g_y!=48 || drawn.g_h!=8)return 156;
    prepare(0,0,40);make_chg(1,BLK_CHANGE,3);make_chg(1,BLK_CHANGE,1);restore_edit();
    if(draws!=1 || drawn.g_y!=48 || drawn.g_h!=24)return 157;
    prepare(0,4,40);make_chg(1,BLK_CHANGE,0);make_chg(1,BLK_CHANGE,3);restore_edit();
    if(draws!=0)return 158;
    prepare(0,4,40);make_chg(1,BLK_CHANGE,3);make_chg(1,BLK_CHANGE,5);restore_edit();
    if(draws!=1 || drawn.g_y!=40 || drawn.g_h!=16)return 159;
    prepare(0,0,40);make_chg(1,BLK_CHANGE,1);restore_edit();
    if(draws!=1 || drawn.g_h!=32)return 160;
    prepare(0,0,40);text.ypos=9;make_chg(1,LINE_CHANGE,0);restore_edit();
    if(view.doc.y!=7 || draws!=1 || drawn.g_h!=32)return 161;
    prepare(0,0,40);text.cursor=TRUE;text.blink=FALSE;
    make_chg(1,LINE_CHANGE,0);restore_edit();
    if(draws!=2 || drawn.g_y!=48 || drawn.g_h!=8)return 162;
    prepare(0,0,40);text.cursor=TRUE;text.blink=FALSE;
    make_chg(1,LINE_CHANGE,1);restore_edit();
    if(draws!=1 || drawn.g_y!=48 || drawn.g_h!=8)return 163;
    prepare(0,0,40);text.cursor=TRUE;text.blink=TRUE;
    make_chg(1,LINE_CHANGE,0);restore_edit();
    if(draws!=1 || drawn.g_y!=40 || drawn.g_h!=8)return 164;
    return -321;
}
int main(void){return QedRuntimeRun(body);}
