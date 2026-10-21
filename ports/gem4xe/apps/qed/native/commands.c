/* SPDX-License-Identifier: GPL-3.0-only
 * One private command draft. Native dialogs retire before outer event policy.
 */
#include "qed-commands.h"
#include "block.h"
#include "edit.h"
#include "find.h"
#include "memory.h"
#include "rsc.h"
#include <exec816/aes.h>
#include <proto/dos.h>

enum { CMD_NONE,CMD_FIND_FORM,CMD_FIND_SEARCH,CMD_ABOUT,CMD_ABOUT2 };
static short command_kind;
static bool command_waiting;
static TEXTP command_text;
static char find_draft[HIST_LEN+1];
static LINEP search_line;
static long search_row;
static short search_column,search_length;
static char selector_path[128],selector_leaf[13];
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
    command_kind=CMD_NONE;command_waiting=FALSE;command_text=NULL;search_line=NULL;
}
bool QedCommandsSearching(void){return command_kind==CMD_FIND_SEARCH;}
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
    short answer,kind=command_kind;OBJECT *tree;
    if(kind==CMD_NONE || command_waiting)return;
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
