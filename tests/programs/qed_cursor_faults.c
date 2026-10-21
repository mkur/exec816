/* Observe actual caret VDI requests; every request forwards unchanged. */
#define cursor QedCursorOrdinary
#include "qed_saving_faults.c"
#undef cursor
#include "options.h"
volatile UWORD QedCursorWideDraws,QedCursorBars,QedCursorGlyphs;
static short active,left,top,width,height;

void cursor(WINDOWP window,TEXTP text)
{
    left=window->work.g_x+cursor_xpos(text,text->xpos,NULL)-window->doc.x*font_wcell;
    top=window->work.g_y+(text->ypos-window->doc.y)*font_hcell;
    width=overwrite?font_wcell:2;height=font_hcell;
    active=1;QedCursorOrdinary(window,text);active=0;
}

void QedCursorBar(WORD handle,const WORD *xy)
{
    if(active){
        ++QedCursorBars;
        if(xy[0]<left || xy[1]<top || xy[2]>=left+width || xy[3]>=top+height)
            ++QedCursorWideDraws;
    }
    v_bar(handle,xy);
}

void QedCursorText(WORD handle,WORD x,WORD y,const char *text)
{
    if(active){++QedCursorGlyphs;if(strlen(text)>1)++QedCursorWideDraws;}
    v_gtext(handle,x,y,text);
}
