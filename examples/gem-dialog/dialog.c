/* SPDX-License-Identifier: MIT */
#include "dialog.h"
#include <exec816/aes.h>
#include <exec816/program.h>
#include <string.h>

static const OBJECT home[]={
    {-1,1,9,G_BOX,0,0,0x1170,0,0,304,144},
    {2,-1,-1,G_STRING,0,0,(ULONG)"Edit / Alert / Open / Save / Quit",8,8,288,8},
    {3,-1,-1,G_STRING,0,0,0,8,32,288,8},
    {4,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT,0,(ULONG)"Edit",8,120,48,16},
    {5,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Alert",68,120,48,16},
    {6,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Quit",248,120,48,16},
    {7,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Open",128,120,48,16},
    {8,-1,-1,G_BUTTON,SELECTABLE|EXIT,0,(ULONG)"Save",188,120,48,16},
    {9,-1,-1,G_STRING,0,0,0,8,56,288,8},
    {0,-1,-1,G_STRING,LASTOB,0,0,8,80,288,8}
};
static const OBJECT edit[]={
    {-1,1,3,G_BOX,0,0,0x00011170,0,0,288,104},
    {2,-1,-1,G_BOXTEXT,EDITABLE,0,0,16,24,256,16},
    {3,-1,-1,G_BUTTON,SELECTABLE|EXIT|DEFAULT,0,(ULONG)"Apply",16,72,112,16},
    {0,-1,-1,G_BUTTON,SELECTABLE|EXIT|LASTOB,0,(ULONG)"Done",160,72,112,16}
};
static const OBJECT menu[]={
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,16},
    {1,3,3,G_IBOX,0,0,0,8,0,424,16},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Dialog",0,0,64,16},
    {0,5,5,G_IBOX,0,0,0,0,16,640,224},
    {4,6,10,G_BOX,0,0,0x1100,8,0,112,80},
    {7,-1,-1,G_STRING,0,0,(ULONG)"Edit",0,0,112,16},
    {8,-1,-1,G_STRING,0,0,(ULONG)"Alert",0,16,112,16},
    {9,-1,-1,G_STRING,0,0,(ULONG)"Quit",0,32,112,16},
    {10,-1,-1,G_STRING,0,0,(ULONG)"Open",0,48,112,16},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Save",0,64,112,16}
};

static WORD paint(struct DialogApp *a)
{
    WORD i,okay;
    if (!wind_get(a->window,WF_WXYWH,&a->work[0],&a->work[1],&a->work[2],&a->work[3])) return 0;
    /* Reconstruct every work-area pixel, including margins exposed by a form. */
    a->home[0].ob_x=a->work[0]; a->home[0].ob_y=a->work[1];
    a->home[0].ob_width=a->work[2]; a->home[0].ob_height=a->work[3];
    for (i=1;i<10;++i) {
        a->home[i].ob_x=home[i].ob_x+(a->work[2]-304)/2;
        a->home[i].ob_y=home[i].ob_y+(a->work[3]-144)/2;
    }
    if (!wind_update(BEG_UPDATE)) return 0;
    okay=objc_draw(a->home,0,MAX_DEPTH,a->work[0],a->work[1],a->work[2],a->work[3]);
    if (!wind_update(END_UPDATE)) okay=0;
    if (okay) ++a->paints;
    return okay;
}

static WORD edit_name(struct DialogApp *a)
{
    WORD x,y,w,h,result;
    UWORD status=AES_OK;
    if (!form_center(a->edit,&x,&y,&w,&h) ||
        !form_dial(FMD_START,0,0,0,0,x,y,w,h)) return 0;
    a->phase=2;
    for (;;) {
        result=form_do(a->edit,1);
        /* Application policy can interrupt. Always branch before indexing. */
        if (result<0) { status=ExecAESDiagnostic(); break; }
        a->edit[result].ob_state&=~SELECTED;
        ++a->accepted;
        if (result==3) break;
    }
    if (!form_dial(FMD_FINISH,0,0,0,0,x,y,w,h)) return 0;
    if (status==AES_PENDING) ++a->interruptions;
    a->phase=1;
    /* Resume the event loop: its retained message precedes the content repair. */
    return status==AES_OK || status==AES_PENDING;
}

static WORD choose(struct DialogApp *a,WORD save)
{
    WORD i;
    a->phase=save ? 5:4;
    a->fileResult=save ? fsel_exinput(a->path,a->file,&a->fileButton,"Save as (selection only)"):
        fsel_input(a->path,a->file,&a->fileButton);
    a->phase=1;
    if (!a->fileResult) {
        if (ExecAESDiagnostic()!=AES_PENDING) return 0;
        ++a->interruptions;
        return 1; /* The event loop receives policy before work-area repair. */
    }
    for (i=0;i<35 && a->path[i];++i) a->directory[i]=a->path[i];
    a->directory[i]=0;
    if (a->fileButton==FSEL_OK) {
        strcpy(a->selection,save ? "Save: ":"Open: ");strcat(a->selection,a->file);
    } else strcpy(a->selection,save ? "Save cancelled":"Open cancelled");
    return 1;
}

WORD DialogRun(struct DialogApp *a)
{
    WORD i,result=20,quit=0,events,mx,my,buttons,mod,key,clicks,action,next;
    TEDINFO *ted=&a->ted;
    a->id=appl_init(); a->window=-1;
    if (a->id<0) return result;
    strcpy(a->path,"SYS:*.TXT");strcpy(a->file,"STORY.TXT");
    a->phase=3;
    if (!form_alert(1,"[1][Standard GEM dialogs|Other apps keep running.][Continue]")) {
        result=ExecAESDiagnostic()==AES_OK ? 0:20; goto finish;
    }
    /* Optional startup exercise: use the temporary host before our own window. */
    if (!strcmp(ExecGetArgStr(),"SELECT") && !choose(a,0)) goto finish;
    memcpy(a->home,home,sizeof(home)); memcpy(a->edit,edit,sizeof(edit));
    memcpy(a->menu,menu,sizeof(menu)); strcpy(a->text,"Exec816");
    a->home[2].ob_spec=(ULONG)a->text;
    a->home[8].ob_spec=(ULONG)a->directory;a->home[9].ob_spec=(ULONG)a->selection;
    ted->te_ptext=(ULONG)a->text; ted->te_ptmplt=(ULONG)""; ted->te_pvalid=(ULONG)"X";
    ted->te_font=IBM; ted->te_color=0x1180; ted->te_thickness=-1; ted->te_txtlen=32;
    a->edit[1].ob_spec=(ULONG)ted;
    for (i=0;i<10;++i) a->input[i]=1;
    a->input[10]=2; a->vdi=1; v_opnvwk(a->input,&a->vdi,a->output);
    if (!a->vdi) goto finish;
    a->window=wind_create(NAME|CLOSER|MOVER,40,48,352,176);
    if (a->window<0 || !wind_set_str(a->window,WF_NAME,"Dialog example") ||
        !wind_open(a->window,40,48,352,176)) goto finish;
    a->opened=1;
    if (!menu_bar(a->menu,1) || !paint(a)) goto finish;
    a->ready=1; a->phase=1; a->armed=NIL;
    result=0;
    while (!quit && !result) {
        events=evnt_multi(MU_KEYBD|MU_BUTTON|MU_MESAG,1,1,a->down ? 0:1,
            0,0,0,0,0,0,0,0,0,0,a->message,0,0,&mx,&my,&buttons,&mod,&key,&clicks);
        if (!events) {
            if (ExecAESDiagnostic()==AES_INPUT_LOST) { a->armed=NIL; a->down=1; continue; }
            result=20; break;
        }
        action=0;
        if (events&MU_MESAG) {
            if (a->message[0]==MN_SELECTED) {
                action=a->message[4]-3;
                if (!menu_tnormal(a->menu,a->message[3],1)) result=20;
            } else if (a->message[3]==a->window) {
                switch (a->message[0]) {
                case WM_CLOSED: quit=1; break;
                case WM_TOPPED:
                    if (!wind_set(a->window,WF_TOP,0,0,0,0)) result=20;
                    break;
                case WM_MOVED:
                    if (!wind_set(a->window,WF_CURRXYWH,a->message[4],a->message[5],
                                  a->message[6],a->message[7])) result=20;
                    break;
                case WM_REDRAW: if (!paint(a)) result=20; break;
                }
            }
        }
        if (quit || result) break;
        if (events&MU_KEYBD) {
            switch (key&255) {
            case 'e': case 'E': case 13: action=3; break;
            case 'a': case 'A': action=4; break;
            case 'q': case 'Q': action=5; break;
            case 'o': case 'O': action=6; break;
            case 's': case 'S': action=7; break;
            }
        }
        if (events&MU_BUTTON) {
            i=objc_find(a->home,0,MAX_DEPTH,mx,my);
            if (buttons&1) { a->armed=i>=3 && i<=7 ? i:NIL; a->down=1; }
            else {
                if (i==a->armed && i>=3 && i<=7) { form_button(a->home,i,1,&next); action=i; }
                a->armed=NIL; a->down=0;
            }
        }
        if (action>=3 && action<=7) a->home[action].ob_state&=~SELECTED;
        if (action==3) { if (!edit_name(a)) result=20; }
        else if (action==4) {
            a->phase=3;
            if (!form_alert(1,"[2][Keep this name?][Keep|Back]") && ExecAESDiagnostic()!=AES_PENDING) result=20;
            else if (ExecAESDiagnostic()==AES_PENDING) ++a->interruptions;
            a->phase=1;
        } else if (action==5) quit=1;
        else if (action==6 || action==7) { if (!choose(a,action==7)) result=20; }
    }
finish:
    a->ready=0; a->phase=0;
    if (!appl_exit()) result=20;
    return result;
}
