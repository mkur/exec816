/* SPDX-License-Identifier: MIT */
#include "terminal.h"
#include <exec816/vdi.h>

static void text(struct Terminal *app,WORD row)
{
    struct TerminalSession *session=&app->sessions[app->selected];
    WORD i,control[12]={8,1,0,0,0,0,0,0,0,0,0,0},points[2];
    VDIPB pb={control,app->glyphs,points,NULL,NULL};
    for (i=0;i<session->width;++i)
        app->glyphs[i]=(session->mode&0x40 ? EXEC_VDI_ATASCII_BASE:0)|session->cells[row*session->width+i];
    points[0]=app->work[0];points[1]=app->work[1]+TERM_CONTROLS+row*8+6;
    control[3]=session->width;control[6]=app->vdi;vdi_call(&pb);
}

WORD TerminalPaint(struct Terminal *app,const WORD *damage)
{
    WORD x,y,w,h,l,t,r,b,clip[4]={0,0,0,0},area[4],row,okay=1,painted=0;
    WORD partial=damage!=NULL,full=partial || (app->dirty&1);
    struct TerminalSession *session=app->selected<0 ? NULL:&app->sessions[app->selected];
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=wind_get(app->window,WF_WORKXYWH,app->work,app->work+1,app->work+2,app->work+3);
    if (!damage) damage=app->work;
    if (okay) okay=wind_get(app->window,WF_FIRSTXYWH,&x,&y,&w,&h);
    while (okay && w>0 && h>0) {
        l=x>damage[0] ? x:damage[0];t=y>damage[1] ? y:damage[1];
        r=x+w<damage[0]+damage[2] ? x+w:damage[0]+damage[2];
        b=y+h<damage[1]+damage[3] ? y+h:damage[1]+damage[3];
        if (l<app->work[0]) l=app->work[0];if (t<app->work[1]) t=app->work[1];
        if (r>app->work[0]+app->work[2]) r=app->work[0]+app->work[2];
        if (b>app->work[1]+app->work[3]) b=app->work[1]+app->work[3];
        if (l<r && t<b) {
            clip[0]=l;clip[1]=t;clip[2]=r-1;clip[3]=b-1;
            painted=1;
            vst_color(app->vdi,1);vswr_mode(app->vdi,1);
            if (full) {
                vs_clip(app->vdi,1,clip);vsf_color(app->vdi,0);v_bar(app->vdi,clip);
                for (row=0;row<EXEC_CONSOLE_VIEW_SLOTS;++row) {
                    const char *label=app->sessions[row].view ? (row==app->selected ? (app->sessions[row].identity ? "[Shell]":"[Output]"):(app->sessions[row].identity ? " Shell ":" Output ")):" Empty ";
                    v_gtext(app->vdi,app->work[0]+row*96+8,app->work[1]+11,label);
                }
                v_gtext(app->vdi,app->work[0]+EXEC_CONSOLE_VIEW_SLOTS*96+8,app->work[1]+11,"+ New");
            }
            if (session && session->view) {
                for (row=0;row<session->height;++row) if (full || (session->damageRows&(1UL<<row))) {
                    WORD top=app->work[1]+TERM_CONTROLS+row*8,bottom=top+8;
                    if (top<t) top=t;if (bottom>b) bottom=b;
                    if (top>=bottom) continue;
                    area[0]=l;area[1]=top;area[2]=r-1;area[3]=bottom-1;
                    vs_clip(app->vdi,1,area);
                    if (!full) { vsf_color(app->vdi,0);v_bar(app->vdi,area); }
                    text(app,row);
                    if (app->focused && !(session->mode&32) && session->column<session->width && session->row==row) {
                        area[0]=app->work[0]+session->column*8;area[1]=app->work[1]+TERM_CONTROLS+row*8+7;
                        /* Compute endpoints from the origin: Calypsi 5.18's
                         * documented local-array addition defect reads the destination. */
                        area[2]=app->work[0]+(session->column+1)*8-1;
                        area[3]=area[1];vsf_color(app->vdi,1);v_bar(app->vdi,area);
                    }
                }
            }
        }
        okay=wind_get(app->window,WF_NEXTXYWH,&x,&y,&w,&h);
    }
    vs_clip(app->vdi,0,clip);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay && painted && !partial && session && session->view) {
        session->damageRows=0;
        if (session->coherent) {
            ExecConsoleViewAcknowledge(session->view,session->revision);
            session->coherent=0;
        }
    }
    if (okay) { app->dirty=0;++app->paints; }
    return okay;
}
