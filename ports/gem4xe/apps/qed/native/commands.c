/* SPDX-License-Identifier: GPL-3.0-only
 * One private command draft. Native dialogs retire before outer event policy.
 */
#include "qed-commands.h"
#include "qed-document.h"
#include "qed-saving.h"
#include "menu.h"
#include "block.h"
#include "edit.h"
#include "find.h"
#include "memory.h"
#include "rsc.h"
#include "text.h"
#include <exec816/aes.h>
#include <proto/dos.h>

enum { CMD_NONE,CMD_FIND_FORM,CMD_FIND_SEARCH,CMD_ABOUT,CMD_ABOUT2,
       CMD_OPEN_FORM,CMD_PREPARE,CMD_DOCUMENT_READ,CMD_ERROR,CMD_ARGUMENT_ERROR,CMD_EXIT_DECISION };
static short command_kind;
static bool command_waiting;
static TEXTP command_text;
static char find_draft[HIST_LEN+1];
static LINEP search_line;
static long search_row;
static short search_column,search_length;
static char selector_path[128],selector_leaf[13];
static char open_path[256];
static bool new_document;
static LONG command_error;
static short bad_path(void){SetIoErr(ERROR_BAD_ARGUMENTS);return QED_DIALOG_FAILED;}

short QedNativeForm(OBJECT *tree,short start)
{
    GRECT bounds;short answer;
    if(!form_center(tree,&bounds.g_x,&bounds.g_y,&bounds.g_w,&bounds.g_h))return -1;
    answer=form_do(tree,start);
    if(answer>=0){answer&=0x7fff;set_state(tree,answer,OS_SELECTED,FALSE);}
    return answer;
}
short QedChooseFile(const char *initial,char *destination,const char *title)
{
    const char *leaf=initial,*p;short button=0,result;unsigned prefix=0,length;
    selector_path[0]=selector_leaf[0]=0;
    if(initial){
        if(strlen(initial)>=256)return bad_path();
        for(p=initial;*p;p++)if(*p==':' || *p=='/')leaf=p+1;
        prefix=(unsigned)(leaf-initial);
        if(prefix+3>=sizeof(selector_path) || strlen(leaf)>=sizeof(selector_leaf))return bad_path();
        memcpy(selector_path,initial,prefix);selector_path[prefix]=0;
        strcpy(selector_leaf,leaf);strcat(selector_path,"*.*");
    }
    result=fsel_exinput(selector_path,selector_leaf,&button,title);
    if(!result)return ExecAESDiagnostic()==AES_PENDING?QED_DIALOG_INTERRUPTED:QED_DIALOG_FAILED;
    if(button!=1)return QED_DIALOG_CANCELLED;
    leaf=selector_path;
    for(p=selector_path;*p;p++)if(*p==':' || *p=='/')leaf=p+1;
    prefix=(unsigned)(leaf-selector_path);length=(unsigned)strlen(selector_leaf);
    if(prefix+length>=256 || !length)return bad_path();
    memcpy(destination,selector_path,prefix);strcpy(destination+prefix,selector_leaf);
    return QED_DIALOG_ACCEPTED;
}
void QedCommandsCancel(void)
{
    if(command_kind==CMD_DOCUMENT_READ)QedDocumentCancel();
    command_kind=CMD_NONE;command_waiting=FALSE;command_text=NULL;search_line=NULL;
}
bool QedCommandsSearching(void){return command_kind==CMD_FIND_SEARCH;}
bool QedCommandsWorking(void)
{
    return QedSavingBusy() || command_kind==CMD_EXIT_DECISION ||
           QedCommandsSearching() || command_kind==CMD_PREPARE ||
           command_kind==CMD_DOCUMENT_READ || command_kind==CMD_ERROR || command_kind==CMD_ARGUMENT_ERROR;
}
void QedArgumentsError(void)
{
    QedCommandsCancel();command_error=ERROR_BAD_ARGUMENTS;command_kind=CMD_ARGUMENT_ERROR;
}
void QedOpenStart(TEXTP text,const char *path)
{
    QedCommandsCancel();command_text=text;new_document=FALSE;
    if(!path){command_kind=CMD_OPEN_FORM;return;}
    if(!*path || strlen(path)>=sizeof(open_path)){
        command_error=ERROR_BAD_ARGUMENTS;command_kind=CMD_ERROR;return;
    }
    strcpy(open_path,path);command_kind=CMD_PREPARE;
}
void QedNewStart(TEXTP text)
{
    QedCommandsCancel();command_text=text;new_document=TRUE;command_kind=CMD_PREPARE;
}
void QedSaveCommand(TEXTP text,bool save_as)
{
    QedCommandsCancel();QedSavingStart(text,save_as);
}
void QedExitStart(void)
{
    QedCommandsCancel();command_text=get_top_text();command_kind=CMD_EXIT_DECISION;
}
void QedFindStart(TEXTP text,bool prompt)
{
    QedCommandsCancel();command_text=text;
    if(prompt){strcpy(find_draft,s_str);command_kind=CMD_FIND_FORM;}
    else if(s_str[0]){
        search_line=text->cursor_line;search_row=text->ypos;search_column=text->xpos;
        search_length=(short)strlen(s_str);command_kind=CMD_FIND_SEARCH;
    }
}
void QedAboutStart(void)
{
    QedCommandsCancel();command_kind=CMD_ABOUT;
}
void QedCommandsMessage(short *message)
{
    if(command_kind==CMD_NONE)return;
    switch(message[0]){
    case WM_REDRAW:case WM_MOVED:case WM_SIZED:case WM_FULLED:
    case WM_ARROWED:case WM_HSLID:case WM_VSLID:
    case WM_TOPPED:case WM_NEWTOP:case WM_ONTOP:
        command_waiting=FALSE;break;
    default:QedCommandsCancel();break;
    }
}
static void find_step(void)
{
    unsigned budget=256;
    while(budget--){
        if(IS_TAIL(search_line)){
            QedCommandsCancel();form_alert(1,"[1][Text not found.][OK]");return;
        }
        if(search_column+search_length<=search_line->len &&
           !memcmp(TEXT(search_line)+search_column,s_str,search_length)){
            TEXTP t=command_text;
            t->cursor_line=search_line;t->ypos=search_row;t->xpos=search_column;blk_mark(t,0);
            t->xpos+=search_length;blk_mark(t,1);t->up_down=FALSE;
            make_chg(t->link,POS_CHANGE,0);QedCommandsCancel();return;
        }
        if(++search_column>search_line->len){search_line=search_line->next;search_row++;search_column=0;}
    }
}
void QedCommandsStep(void)
{
    short answer,kind;OBJECT *tree;
    if(QedSavingBusy()){QedSavingStep();if(QedSavingBusy())return;}
    if(QedSavingExitPending()){QedExitStart();return;}
    kind=command_kind;
    if(kind==CMD_NONE || command_waiting)return;
    if(kind==CMD_EXIT_DECISION){
        answer=1;
        if(command_text && (command_text->moved || QedSavingAttention()))
            answer=form_alert(2,"[2][Discard unsaved text and save details?][Discard|Cancel]");
        if(!answer && ExecAESDiagnostic()==AES_PENDING){command_waiting=TRUE;return;}
        QedCommandsCancel();
        if(answer==1){QedSavingForget();do_quit();}
        return;
    }
    if(kind==CMD_ERROR || kind==CMD_ARGUMENT_ERROR){
        LONG cause=command_error;
        if(kind==CMD_ARGUMENT_ERROR)answer=form_alert(1,"[1][Use zero or one document argument.][OK]");
        else if(cause==ERROR_NO_FREE_STORE)answer=form_alert(1,"[1][Not enough memory for the document.][OK]");
        else if(cause==ERROR_BAD_ARGUMENTS)answer=form_alert(1,"[1][Unsupported text format or path.|Use LF or CRLF; lines up to 1023 bytes.][OK]");
        else answer=form_alert(1,"[1][The document could not be read.|The current document is unchanged.][OK]");
        if(!answer && ExecAESDiagnostic()==AES_PENDING){command_waiting=TRUE;return;}
        QedCommandsCancel();
        make_chg(get_top_text()->link,TOTAL_CHANGE,0);
        SetIoErr(cause);return;
    }
    if(kind==CMD_OPEN_FORM){
        answer=QedChooseFile(NULL,open_path,"Open text document");
        if(answer==QED_DIALOG_ACCEPTED)command_kind=CMD_PREPARE;
        else if(answer==QED_DIALOG_FAILED){command_error=ERROR_BAD_ARGUMENTS;command_kind=CMD_ERROR;}
        else QedCommandsCancel();
        return;
    }
    if(kind==CMD_PREPARE){
        if(QedDocumentBegin(new_document?NULL:open_path))command_kind=CMD_DOCUMENT_READ;
        else {command_error=QedDocumentError();command_kind=CMD_ERROR;}
        return;
    }
    if(kind==CMD_DOCUMENT_READ){
        answer=QedDocumentPoll();
        if(answer<0){command_error=QedDocumentError();command_kind=CMD_ERROR;return;}
        if(answer>0){
            if(!command_text->moved || form_alert(2,"[2][Discard unsaved changes?][Discard|Cancel]")==1)
                QedDocumentCommit(command_text);
            QedCommandsCancel();
        }
        return;
    }
    if(kind==CMD_FIND_SEARCH){find_step();return;}
    tree=kind==CMD_FIND_FORM?replace:(kind==CMD_ABOUT?about:about2);
    if(kind==CMD_FIND_FORM)set_string(tree,RPTEXT1,find_draft);
    answer=QedNativeForm(tree,kind==CMD_FIND_FORM?RPTEXT1:0);
    if(kind==CMD_FIND_FORM)get_string(tree,RPTEXT1,find_draft);
    if(answer<0){
        if(ExecAESDiagnostic()==AES_PENDING){command_waiting=TRUE;return;}
        QedCommandsCancel();
        if(ExecAESDiagnostic()!=AES_OK)form_alert(1,"[1][The dialog cannot open here.][OK]");
        return;
    }
    if(kind==CMD_FIND_FORM){
        TEXTP target=command_text;
        QedCommandsCancel();
        if(answer==RPOK && find_draft[0]){strcpy(s_str,find_draft);QedFindStart(target,FALSE);}
    }else if(kind==CMD_ABOUT && answer==AINFO)command_kind=CMD_ABOUT2;
    else QedCommandsCancel();
}
