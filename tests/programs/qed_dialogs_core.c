/* Actual private adapters; deterministic signed-result/buffer boundary probes.
 * Mock form/selector calls here claim no native dialog or input delivery. */
#include "qed-runtime.h"
#include "qed-commands.h"
#include "memory.h"
#include "find.h"
#include <exec816/aes.h>
#include <proto/dos.h>
#include <string.h>
static short answer,center_ok=1,state_calls,form_calls,selector_calls,selector_result=1,button=1;
static UWORD diagnostic;
static const char *expected_path="WORK:*.*",*expected_leaf="OLD.TXT";
static bool bad_input;
WORD QedProbeCenter(OBJECT *tree,WORD *x,WORD *y,WORD *w,WORD *h)
{*x=*y=0;*w=512;*h=72;return center_ok;}
WORD QedProbeForm(OBJECT *tree,WORD start){++form_calls;return answer;}
void QedProbeState(OBJECT *tree,WORD object,WORD state,WORD set)
{++state_calls;if(object!=3 || state!=OS_SELECTED || set)bad_input=TRUE;}
UWORD QedProbeDiagnostic(void){return diagnostic;}
WORD QedProbeSelector(char *path,char *leaf,WORD *pressed,const char *title)
{
    ++selector_calls;
    if(strcmp(path,expected_path) || strcmp(leaf,expected_leaf))bad_input=TRUE;
    strcpy(path,"SYS:DOCS/*.TXT");strcpy(leaf,"FILE.TXT");*pressed=button;return selector_result;
}
static OBJECT tree[4];
OBJECT *replace=tree,*about=tree,*about2=tree;
static TEXT document;
static unsigned short not_found,changes;
void set_string(OBJECT *objects,short object,char *value){}
void get_string(OBJECT *objects,short object,char *value){}
WORD QedProbeAlert(WORD def,const char *message){++not_found;return 0;}
void debug(char *format,...){}
short note(short def,short undo,short index){return 0;}
void make_chg(short link,short kind,long row){++changes;}
void hl_insert(RINGP ring,LINEP line){}
void hl_remove(RINGP ring,LINEP line){}
void hl_update_zeile(RINGP ring,LINEP line){}
static struct {unsigned short before;char path[256];unsigned short after;} output;
#define CHECK(test,code) do{if(!(test))return code;}while(0)
static int body(int argc,char **argv)
{
    static char oversized[257];short n;
    answer=-1;CHECK(QedNativeForm(tree,0)==-1 && !state_calls,101);
    answer=(short)0x8001;CHECK(QedNativeForm(tree,0)==(short)0x8001 && !state_calls,102);
    center_ok=0;n=form_calls;CHECK(QedNativeForm(tree,0)<0 && form_calls==n && !state_calls,103);
    center_ok=1;answer=3;CHECK(QedNativeForm(tree,0)==3 && state_calls==1 && !bad_input,104);
    output.before=0x1234;output.after=0x5678;strcpy(output.path,"unchanged");
    CHECK(QedChooseFile("WORK:OLD.TXT",output.path,"Open")==QED_DIALOG_ACCEPTED,105);
    CHECK(!strcmp(output.path,"SYS:DOCS/FILE.TXT") && !bad_input,106);
    button=0;strcpy(output.path,"unchanged");
    CHECK(QedChooseFile("WORK:OLD.TXT",output.path,"Open")==QED_DIALOG_CANCELLED && !strcmp(output.path,"unchanged"),107);
    selector_result=0;diagnostic=AES_PENDING;
    CHECK(QedChooseFile("WORK:OLD.TXT",output.path,"Open")==QED_DIALOG_INTERRUPTED && !strcmp(output.path,"unchanged"),108);
    diagnostic=AES_RESOURCE;
    CHECK(QedChooseFile("WORK:OLD.TXT",output.path,"Open")==QED_DIALOG_FAILED && !strcmp(output.path,"unchanged"),109);
    n=selector_calls;memset(oversized,'a',256);oversized[256]=0;
    CHECK(QedChooseFile(oversized,output.path,"Open")==QED_DIALOG_FAILED && selector_calls==n && IoErr()==ERROR_BAD_ARGUMENTS,110);
    CHECK(QedChooseFile("SYS:TOO_LONG_NAME.TXT",output.path,"Open")==QED_DIALOG_FAILED && selector_calls==n,111);
    memset(oversized,'a',124);oversized[124]=':';oversized[125]=0;
    CHECK(QedChooseFile(oversized,output.path,"Open")==QED_DIALOG_FAILED && selector_calls==n,112);
    expected_path="*.*";expected_leaf="OLD.TXT";selector_result=1;button=1;
    CHECK(QedChooseFile("OLD.TXT",output.path,"Open")==QED_DIALOG_ACCEPTED && !bad_input,113);
    CHECK(output.before==0x1234 && output.after==0x5678,114);
    /* More than one search budget, including a long-line end and cancellation.
     * No GUI claim: the real form and selection pixels have a loaded cohort. */
    {
        static char bytes[1024];LINEP line;short i;unsigned short before;
        init_memory();init_textring(&document.text);kill_textring(&document.text);
        document.text.head.next=&document.text.tail;document.text.tail.prev=&document.text.head;
        document.text.lines=0;
        memset(bytes,'a',1023);bytes[1023]=0;bytes[1021]='*';bytes[1022]='z';
        line=new_col(bytes,1023);CHECK(line!=NULL,115);col_append(&document.text,line);
        document.cursor_line=line;strcpy(s_str,"*z");
        QedFindStart(&document,FALSE);QedCommandsStep();
        CHECK(QedCommandsSearching() && document.xpos==0 && !document.block,116);
        for(i=0;i<4 && QedCommandsSearching();i++)QedCommandsStep();
        CHECK(!QedCommandsSearching() && document.xpos==1023 && document.x1==1021 &&
            document.x2==1023 && document.block && !document.moved,117);
        before=not_found;QedFindStart(&document,FALSE);QedCommandsStep();
        CHECK(!QedCommandsSearching() && not_found==before+1 && document.xpos==1023 && document.block,118);
        document.xpos=0;strcpy(s_str,"absent");QedFindStart(&document,FALSE);QedCommandsStep();
        CHECK(QedCommandsSearching() && document.xpos==0 && document.block,119);
        QedCommandsCancel();kill_textring(&document.text);before=changes;
        QedCommandsStep();CHECK(!QedCommandsSearching() && changes==before,120);
        kill_memory();
    }
    return -321;
}
int main(void){return QedRuntimeRun(body);}
