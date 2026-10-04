/* Hosted GSX boundary. The presenter owns clip, pointer scope and hardware. */
#include "widgets.h"
GRECT gl_clip;
WORD gl_wchar=8,gl_hchar=8,intin[INTIN_SIZE];
static WORD mode=MD_REPLACE,textColour,lineColour,fillColour;

void gsx_moff(void) { }
void gsx_mon(void) { }
void gsx_attr(WORD text,WORD value,WORD colour)
{
    mode=value;
    if (text) textColour=colour; else lineColour=colour;
}
void gsx_fcolor(WORD colour) { fillColour=colour; }
WORD gsx_chkclip(const GRECT *p)
{
    return p->g_x+p->g_w>gl_clip.g_x && p->g_y+p->g_h>gl_clip.g_y &&
        p->g_x<gl_clip.g_x+gl_clip.g_w && p->g_y<gl_clip.g_y+gl_clip.g_h;
}
void bb_fill(WORD m,WORD style,WORD pattern,WORD x,WORD y,WORD w,WORD h)
{
    GRECT rect;
    r_set(&rect,x,y,w,h);
    WidgetFill(m,style,pattern,fillColour,&rect);
}
void gsx_box(const GRECT *p)
{
    GRECT edge;
    r_set(&edge,p->g_x,p->g_y,p->g_w,1);
    WidgetFill(mode,FIS_SOLID,0,lineColour,&edge);
    edge.g_y=p->g_y+p->g_h-1;
    if (p->g_h>1) WidgetFill(mode,FIS_SOLID,0,lineColour,&edge);
    if (p->g_h>2) {
        r_set(&edge,p->g_x,p->g_y+1,1,p->g_h-2);
        WidgetFill(mode,FIS_SOLID,0,lineColour,&edge);
        edge.g_x=p->g_x+p->g_w-1;
        if (p->g_w>1) WidgetFill(mode,FIS_SOLID,0,lineColour,&edge);
    }
}
void gsx_tblt(WORD font,WORD x,WORD y,WORD count)
{
    (void)font;
    WidgetText(x,y,intin,count,mode,textColour);
}
