/* SPDX-License-Identifier: GPL-3.0-only
 * One event-owned save. Native forms and DOS calls run without caller locks.
 */
#include "qed-saving.h"
#include "qed-save.h"
#include "qed-commands.h"
#include "qed.h"
#include "rsc.h"
#include "clipbrd.h"
#include "edit.h"
#include "memory.h"
#include "text.h"
#include "window.h"
#include "event.h"
#include <exec816/aes.h>
#include <stdio.h>
#include <string.h>
enum { SAVE_IDLE,SAVE_FORM,SAVE_PREPARE,SAVE_TARGET,SAVE_BACKUP,SAVE_STREAM,
       SAVE_REPORT,SAVE_DRAIN,SAVE_REVIEW };
static short saving_kind,next_kind,last_events,last_result,operation_result;
static bool waiting,exit_pending,reviewing;
static TEXTP save_text;
static struct QedSave *active_save,*recovery;
static char save_path[256],presentation[512];
static LONG save_error;
static unsigned report_role,path_offset;

bool QedSavingBusy(void){return saving_kind!=SAVE_IDLE;}
bool QedSavingAttention(void){return recovery!=NULL;}
void QedSavingObserved(short events){last_events=events;}
short QedSavingTakeResult(void){short result=last_result;last_result=0;return result;}
bool QedSavingExitPending(void)
{bool pending=exit_pending && !QedSavingBusy();if(pending)exit_pending=FALSE;return pending;}
void QedSavingForget(void){QedSaveDispose(recovery);recovery=NULL;}
static bool needs_recovery(const struct QedSave *s)
{
    return s && s->result!=QED_SAVE_SAVED && (s->result==QED_SAVE_UNCERTAIN || s->published ||
        s->stage.owned || s->moved_target || s->moved_backup);
}
static void drain(short result)
{operation_result=result;saving_kind=SAVE_DRAIN;waiting=FALSE;}
static void status(const char *text)
{
    WINDOWP w=get_window(save_text->link);
    if(w)wind_set_str(w->handle,WF_INFO,text);
}
void QedSavingStart(TEXTP text,bool save_as)
{
    if(!text || QedSavingBusy())return;
    save_text=text;last_result=operation_result=0;save_error=0;waiting=reviewing=FALSE;
    path_offset=report_role=0;QedPointerCancel();
    next_kind=save_as || text->namenlos ? SAVE_FORM:SAVE_PREPARE;
    if(next_kind==SAVE_PREPARE)strcpy(save_path,text->filename);
    else save_path[0]=0;
    saving_kind=recovery ? SAVE_REVIEW:next_kind;
}
bool QedSavingMessage(short *message)
{
    if(!QedSavingBusy())return FALSE;
    if(message[0]==WM_CLOSED || message[0]==AP_TERM ||
       (message[0]==MN_SELECTED && (message[4]==MQUIT || message[4]==MCLOSE))){
        if(message[0]==MN_SELECTED)menu_tnormal(menu,message[3],TRUE);
        exit_pending=TRUE;
        if(active_save && active_save->result==QED_SAVE_PENDING){
            if(QedSaveCanCancel(active_save)){
                QedSaveCancel(active_save);
                if(active_save->result==QED_SAVE_CANCELLED)drain(QED_SAVE_CANCELLED);
                else saving_kind=SAVE_STREAM;
            }
        }else if(saving_kind!=SAVE_REPORT && saving_kind!=SAVE_DRAIN)drain(QED_SAVE_CANCELLED);
        waiting=FALSE;return TRUE;
    }
    switch(message[0]){
    case WM_REDRAW:case WM_MOVED:case WM_SIZED:case WM_FULLED:case WM_ARROWED:
    case WM_HSLID:case WM_VSLID:case WM_TOPPED:case WM_NEWTOP:case WM_ONTOP:
        waiting=FALSE;return FALSE;
    default:return TRUE;
    }
}
void QedSavingKey(short state,short key)
{
    unsigned ch=(unsigned)key&255;
    if((state&K_CTRL) && (ch=='q' || ch=='Q' || ch==17 || ch=='u' || ch=='U' || ch==21)){
        short message[8]={WM_CLOSED,0,0,0,0,0,0,0};QedSavingMessage(message);return;
    }
    if(ch!=27 || saving_kind==SAVE_DRAIN)return;
    if(saving_kind==SAVE_REPORT || saving_kind==SAVE_REVIEW){waiting=FALSE;return;}
    if(active_save && active_save->result==QED_SAVE_PENDING){
        if(QedSaveCanCancel(active_save))QedSaveCancel(active_save);
    }else drain(QED_SAVE_CANCELLED);
}
/* At most four 40-character lines per page. Every path byte remains available. */
static short path_page(const char *heading,const char *path,const char *footer,const char *buttons)
{
    unsigned at=0,i=0,lines=footer ? 3:4,length=(unsigned)strlen(path),part;
    char *out=presentation;
    out+=sprintf(out,"[2][%s",heading);
    while(at<lines && path_offset+i<length){
        *out++='|';part=length-path_offset-i;if(part>40)part=40;
        memcpy(out,path+path_offset+i,part);out+=part;i+=part;at++;
    }
    if(!length){strcpy(out,"|<not created>");out+=strlen(out);}
    if(footer){*out++='|';strcpy(out,footer);out+=strlen(out);}
    strcpy(out,"][");out+=2;
    strcpy(out,path_offset+i<length ? "Next|Cancel":buttons);out+=strlen(out);strcpy(out,"]");
    return form_alert(2,presentation);
}
static const char *error_name(LONG cause)
{
    switch(cause){
    case 0:return "None";
    case ERROR_DISK_FULL:return "Disk full";
    case ERROR_NO_FREE_STORE:return "Out of memory";
    case ERROR_OBJECT_EXISTS:return "Name exists";
    case ERROR_OBJECT_IN_USE:return "Object in use";
    case ERROR_WRITE_PROTECTED:case ERROR_DELETE_PROTECTED:return "Write protected";
    case ERROR_DISK_WRITE_PROTECTED:return "Disk protected";
    case ERROR_BREAK:return "Interrupted";
    default:return "Native DOS error";
    }
}
static const char *phase_name(unsigned phase)
{
    static const char *names[]={"Prepare","Stage","Older backup","Old destination","Publish",
        "Cleanup","Restore target","Restore backup","Remove temporary","Done"};
    return phase<10 ? names[phase]:"Unknown";
}
static const char *stage_name(unsigned phase)
{
    static const char *names[]={"Count","Create","Write","Close","Cleanup","Done","Ready"};
    return phase<7 ? names[phase]:"Unknown";
}
static void report_start(void)
{
    WINDOWP w;
    operation_result=active_save ? active_save->result:QED_SAVE_FAILED;
    save_error=active_save ? active_save->cause:save_error;
    if(active_save && (active_save->published || active_save->result==QED_SAVE_UNCERTAIN)){
        save_text->moved=1;w=get_window(save_text->link);w->flags|=WI_CHANGED;
        set_wtitle(w,save_text->filename);make_chg(save_text->link,TOTAL_CHANGE,0);
    }
    saving_kind=SAVE_REPORT;report_role=0;path_offset=0;waiting=FALSE;reviewing=FALSE;
}
static void report_done(void)
{
    if(reviewing){saving_kind=SAVE_REVIEW;reviewing=FALSE;return;}
    drain(operation_result);
}
static void report_step(void)
{
    struct QedSave *s=reviewing ? recovery:active_save;
    const char *name,*heading;short answer;unsigned length;
    if(report_role==0){
        snprintf(presentation,sizeof(presentation),
            "[1][%s|%s (%ld)|Cleanup: %s (%ld)|%s / %s|T Close confirmed: %u][Details|Keep editing]",
            s && s->published ? "New file published; cleanup failed.":
                (s && s->result==QED_SAVE_UNCERTAIN ? "Save outcome uncertain.":"Save failed."),
            error_name(s ? s->cause:save_error),s ? s->cause:save_error,
            error_name(s ? s->cleanup:0),s ? s->cleanup:0L,
            phase_name(s ? s->cause_phase:0),stage_name(s ? s->stage.cause_phase:0),s ? s->stage.close_ok:0);
        answer=form_alert(2,presentation);
        if(!answer && ExecAESDiagnostic()!=AES_OK){waiting=TRUE;status("Save details unavailable; Esc retries.");return;}
        if(answer!=1){report_done();return;}
        report_role=1;path_offset=0;return;
    }
    if(!s){name=save_path;heading="Requested destination";}
    else switch(report_role){
    case 1:name=s->target.name;heading=s->published ? "D - published destination":"D - destination";break;
    case 2:name=s->stage.name;heading=s->stage.created ? "T - staging sibling":"T - possible staging sibling";break;
    case 3:name=s->backup;heading=s->target_exists ? "B - previous-target / backup path":"B - independent; not queried";break;
    default:name=s->escrow;heading="E - older-backup path";break;
    }
    answer=path_page(heading,name,NULL,"Next|Keep editing");
    if(!answer && ExecAESDiagnostic()!=AES_OK){waiting=TRUE;status("Save details unavailable; Esc retries.");return;}
    if(answer!=1){report_done();return;}
    length=(unsigned)strlen(name);path_offset+=160;
    if(path_offset>=length){path_offset=0;report_role++;}
    if(report_role>(s ? 4:1))report_done();
}
void QedSavingStep(void)
{
    short answer,result;unsigned length;WINDOWP window;
    if(saving_kind==SAVE_IDLE || waiting)return;
    if(saving_kind==SAVE_REVIEW){
        answer=form_alert(3,"[2][Previous save details are retained.|Files will be left for manual recovery.][Details|Forget|Cancel]");
        if(!answer && ExecAESDiagnostic()!=AES_OK){waiting=TRUE;return;}
        if(answer==1){reviewing=TRUE;report_role=0;path_offset=0;saving_kind=SAVE_REPORT;return;}
        if(answer==2){QedSavingForget();saving_kind=next_kind;return;}
        drain(QED_SAVE_CANCELLED);return;
    }
    if(saving_kind==SAVE_FORM){
        answer=QedChooseFile(save_text->namenlos ? NULL:save_text->filename,save_path,"Save text document as");
        if(answer==QED_DIALOG_ACCEPTED)saving_kind=SAVE_PREPARE;
        else if(answer==QED_DIALOG_FAILED){save_error=IoErr();report_start();}
        else drain(QED_SAVE_CANCELLED);
        return;
    }
    if(saving_kind==SAVE_PREPARE){
        active_save=QedSavePrepare(save_path);
        if(!active_save){save_error=IoErr();report_start();return;}
        path_offset=0;
        if(active_save->target_exists)saving_kind=SAVE_TARGET;
        else{QedSaveStart(active_save,&save_text->text,0,0);saving_kind=SAVE_STREAM;}
        return;
    }
    if(saving_kind==SAVE_TARGET || saving_kind==SAVE_BACKUP){
        bool backup=saving_kind==SAVE_BACKUP;
        const char *path=backup ? active_save->backup:active_save->target.name;
        answer=path_page(backup ? "Remove this older backup?":"Replace this file?",path,
            backup ? "Current destination becomes the backup.":
                (active_save->target_flags&(FIBF_HIDDEN|FIBF_ARCHIVE) ?
                    "New file loses Hidden/Archive flags.":"New file uses default attributes."),
            backup ? "Remove|Cancel":"Replace|Cancel");
        if(!answer && ExecAESDiagnostic()==AES_PENDING){waiting=TRUE;return;}
        if(answer!=1){QedSaveCancel(active_save);drain(QED_SAVE_CANCELLED);return;}
        length=(unsigned)strlen(path);path_offset+=120;
        if(path_offset<length)return;
        path_offset=0;
        if(!backup && active_save->backup_exists)saving_kind=SAVE_BACKUP;
        else{QedSaveStart(active_save,&save_text->text,1,1);saving_kind=SAVE_STREAM;}
        return;
    }
    if(saving_kind==SAVE_STREAM){
        result=QedSavePoll(active_save);if(!result)return;
        if(result==QED_SAVE_SAVED || result==QED_SAVE_CANCELLED)drain(result);
        else report_start();
        return;
    }
    if(saving_kind==SAVE_REPORT){report_step();return;}
    /* Require an idle input poll after completion. Busy keys/messages have
       been consumed, including the editor's own queue, before unfreezing. */
    if((last_events&(MU_KEYBD|MU_BUTTON|MU_MESAG)) || QedEventsPending())return;
    if(operation_result==QED_SAVE_SAVED){
        set_text_name(save_text,active_save->target.name,FALSE);save_text->moved=0;
        save_text->readonly=FALSE;save_text->file_date_time=-1;
        qed_undo_boundary();window=get_window(save_text->link);window->flags&=~WI_CHANGED;
        set_wtitle(window,save_text->filename);make_chg(save_text->link,TOTAL_CHANGE,0);
    }
    if(needs_recovery(active_save)){recovery=active_save;active_save=NULL;}
    QedSaveDispose(active_save);active_save=NULL;
    last_result=operation_result;saving_kind=SAVE_IDLE;status("");SetIoErr(save_error);
}
void QedSavingShutdown(void)
{
    QedSaveDispose(active_save);active_save=NULL;QedSavingForget();
}
