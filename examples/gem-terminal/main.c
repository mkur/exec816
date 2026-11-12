/* SPDX-License-Identifier: MIT */
#include "terminal.h"
#include <exec816/aes.h>
#include <string.h>

struct Terminal *GEMTerminal;

int main(void)
{
    struct Terminal *app=AllocMem(sizeof(*app),MEMF_PUBLIC|MEMF_CLEAR);
    WORD i,cw,ch,bw,bh,result=1,done=0;
    if (!app) return 1;
    GEMTerminal=app;
    app->selected=-1;app->window=-1;
    app->id=appl_init();
    if (app->id<0) goto finish;
    app->vdi=graf_handle(&cw,&ch,&bw,&bh);
    for (i=0;i<10;++i) app->input[i]=1;
    app->input[10]=2;v_opnvwk(app->input,&app->vdi,app->output);
    if (!app->vdi || !TerminalPlatformOpen(app)) goto finish;
    app->window=wind_create(NAME|CLOSER|MOVER,112,40,528,192);
    if (app->window<0 || !wind_set_str(app->window,WF_NAME,"Terminal")) goto finish;
    if (!wind_set(app->window,WF_EXEC_FOCUS,1,0,0,0) ||
        !wind_open(app->window,112,40,528,192)) goto finish;
    app->opened=1;app->dirty=1;result=0;
    while (!done) {
        WORD events;
        if (!TerminalPlatformRefresh(app)) break;
        if (app->dirty && !TerminalPaint(app,NULL)) { result=2;break; }
        events=TerminalPlatformWait(app);
        if (!events && !app->wait.received) { result=2;break; }
        if ((events&MU_MESAG) && app->wait.message[3]==app->window) {
            WORD *message=app->wait.message;
            switch (message[0]) {
            case WM_REDRAW: if (!TerminalPaint(app,message+4)) result=2;break;
            case WM_ONTOP: case WM_UNTOPPED:
                app->focused=message[0]==WM_ONTOP;
                if (app->selected>=0) {
                    struct TerminalSession *s=&app->sessions[app->selected];
                    if (s->row<TERM_HEIGHT) s->damageRows|=1UL<<s->row;
                    app->dirty|=2;
                }
                break;
            case WM_TOPPED: wind_set(app->window,WF_TOP,0,0,0,0);break;
            case WM_MOVED: wind_set(app->window,WF_CURRXYWH,message[4],message[5],message[6],message[7]);break;
            case WM_CLOSED:
                if (!TerminalPlatformRefresh(app)) { done=1;break; }
                if (app->selected>=0) {
                    struct TerminalSession *s=&app->sessions[app->selected];
                    WORD choice;
                    ExecConsoleViewUnbindWindow(app->window);
                    choice=form_alert(1,"[2][Close this session or stop its job?][Cancel|Close]");
                    app->dirty=1;
                    if (choice==2) {
                        if (s->identity) TerminalPlatformAction(app,SESSION_CLOSE,s->identity);
                        else {
                            struct ExecConsoleViewInput *input=&app->inputPacket;
                            memset(input,0,sizeof(*input));input->kind=EXEC_CONSOLE_VIEW_INPUT_CANCEL;input->route=s->route;
                            ExecConsoleViewInput(s->view,input);
                        }
                    }
                    if (!TerminalPlatformRefresh(app)) { done=1;break; }
                    if (app->selected>=0)
                        ExecConsoleViewBindWindow(app->sessions[app->selected].view,app->window);
                }
                break;
            }
        }
        if ((events&MU_BUTTON) && ExecAESInputWindow(MU_BUTTON)==app->window &&
            app->wait.mouseY>=app->work[1] && app->wait.mouseY<app->work[1]+TERM_CONTROLS) {
            WORD x=app->wait.mouseX-app->work[0];
            if (x>=0 && x<EXEC_CONSOLE_VIEW_SLOTS*96) {
                i=x/96;
                if (app->sessions[i].view) {
                    if (app->sessions[i].identity) TerminalPlatformAction(app,SESSION_SELECT,app->sessions[i].identity);
                    TerminalPlatformSelect(app,i);
                }
            } else if (x>=EXEC_CONSOLE_VIEW_SLOTS*96 && x<EXEC_CONSOLE_VIEW_SLOTS*96+64)
                TerminalPlatformAction(app,SESSION_CREATE,0);
            /* Wait for release through ordinary AES; no hardware polling. */
            evnt_button(1,1,0,&cw,&ch,&bw,&bh);
        }
        if (result) break;
    }
finish:
    TerminalPlatformClose(app);
    if (app->opened) wind_close(app->window);
    if (app->window>0) wind_delete(app->window);
    if (app->vdi) v_clsvwk(app->vdi);
    if (app->id>0 && !appl_exit()) result=3;
    GEMTerminal=NULL;FreeMem(app,sizeof(*app));return result;
}
