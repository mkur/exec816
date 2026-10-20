/* Controlled AES decisions and the actual document/file controller. */
#define BASIC_FILE_MOCK
#define main BasicFileUnusedMain
#include "basic_files.c"
#undef main
#include "../../examples/gem-basic/file-ui.h"
#include <exec816/aes.h>
#include "../../c/calypsi/aes-alert-private.h"
#undef CHECK
#define CHECK(x) do { if (!(x)) return __LINE__; ++BasicUIChecks; } while (0)
volatile UWORD BasicUIChecks;
static struct BasicEditor editor;
static struct ExecAESAlert parsed;
static WORD invalidAlert;
static char selectorPattern[128]="RAM:*.BAS",selectorName[13]="ONE.BAS";
static char recoveryTemporary[128],recoveryBackup[128],deepPath[128];
static WORD decision=3,selector=1,diagnostic,selected=FSEL_OK,selectors,alerts;
WORD form_alert(WORD button,const char *text)
{
    WORD i;char *target=0;
    ++alerts;
    if (ExecAESAlertParse(&parsed,button,text)!=AES_OK || parsed.tree[0].ob_width>288 || parsed.tree[0].ob_height>128) invalidAlert=1;
    if (!strcmp(parsed.lines[0],"Completed temporary path")) target=recoveryTemporary;
    if (!strcmp(parsed.lines[0],"Backup recovery path")) target=recoveryBackup;
    if (target) { *target=0;for (i=1;i<parsed.lineCount;++i) strcat(target,parsed.lines[i]); }
    diagnostic=decision ? AES_OK:AES_PENDING;return decision;
}
WORD fsel_exinput(char *path,char *file,WORD *button,const char *title)
{ (void)title;++selectors;strcpy(path,selectorPattern);strcpy(file,selectorName);*button=selected;
  diagnostic=selector ? AES_OK:AES_PENDING;return selector; }
UWORD ExecAESDiagnostic(void) { return diagnostic; }
void BasicEditorDamage(struct BasicEditor *e,UWORD first,UWORD end)
{ (void)first;(void)end;e->dirty=1; }
static WORD run(void)
{ UWORD steps=0;while (BasicFilesWork() && ++steps<100) if (BasicFilesStep(&editor)==1) return 1;return steps<100 ? 0:-1; }
LONG EXEC_CALL BasicUIProbe(ULONG unused)
{
    ULONG baseline=AvailMem(MEMF_UPPER),generation;WORD i,target,result;
    (void)unused;CHECK(!BasicDocumentInit(&editor.document));
    CHECK(!BasicReplace(&editor.document,0,0,(const UBYTE *)"A\n",2));
    BasicFilesRequest(BASIC_FILE_NEW);CHECK(!run() && editor.document.bytes==2);
    decision=2;BasicFilesRequest(BASIC_FILE_NEW);CHECK(!run() && !editor.document.bytes && !*BasicFilesPath());
    CHECK(!BasicReplace(&editor.document,0,0,(const UBYTE *)"A\n",2));
    BasicFilesRequest(BASIC_FILE_SAVE_AS);CHECK(!run() && !strcmp(BasicFilesPath(),"RAM:ONE.BAS"));
    CHECK(equals("RAM:ONE.BAS",(const UBYTE *)"A\x9b",2) && !BasicDirty(&editor.document));
    CHECK(!BasicReplace(&editor.document,0,0,(const UBYTE *)"B",1));
    selected=FSEL_CANCEL;BasicFilesRequest(BASIC_FILE_SAVE_AS);CHECK(!run() && !strcmp(BasicFilesPath(),"RAM:ONE.BAS") && BasicDirty(&editor.document));
    selected=FSEL_OK;decision=3;i=selectors;BasicFilesRequest(BASIC_FILE_OPEN);CHECK(!run() && selectors==i && editor.document.bytes==3);
    decision=1;BasicFilesRequest(BASIC_FILE_NEW);CHECK(!run() && !editor.document.bytes && !*BasicFilesPath());
    CHECK(equals("RAM:ONE.BAS",(const UBYTE *)"BA\x9b",3));
    selector=0;BasicFilesRequest(BASIC_FILE_OPEN);CHECK(BasicFilesStep(&editor)==2 && BasicFilesWork() && !editor.document.bytes);
    selector=1;CHECK(!run() && editor.document.bytes==3 && !BasicDirty(&editor.document));
    CHECK(!BasicReplace(&editor.document,0,0,(const UBYTE *)"KEEP",4));editor.document.saved=editor.document.generation;
    generation=editor.document.generation;BasicFilesRequest(BASIC_FILE_OPEN);CHECK(!BasicFilesStep(&editor) && BasicFilesLoading());
    fault=8;CHECK(!run() && editor.document.bytes==7 && editor.document.generation==generation && !opened);fault=0;
    /* Cancellation at every save publication stage retains complete copies. */
    for (target=1;target<=7;++target) {
        reset();CHECK(store("RAM:OLD.BAS",(const UBYTE *)"OLD",3));
        CHECK(BasicSaveBegin(&job,&editor.document,&named,"RAM:OLD.BAS"));
        for (i=0;i<100 && job.phase!=target;++i) CHECK(!BasicFileStep(&job,&editor.document,&named));
        CHECK(job.phase==target);BasicFileCancel(&job);
        CHECK(job.error==ERROR_BREAK && !job.phase && !opened && !job.snapshot && !job.handle);
        if (target>=4) CHECK(job.complete && (job.temporary[0] || job.backup[0]));
        CHECK(BasicSaveBegin(&job,&editor.document,&named,"RAM:OLD.BAS"));
        result=0;for (i=0;i<100 && !result;++i) result=BasicFileStep(&job,&editor.document,&named);
        CHECK(result==1 && !opened);
    }
    reset();CHECK(BasicSaveBegin(&job,&editor.document,&named,"RAM:UNCERT.BAS"));
    CHECK(!BasicFileStep(&job,&editor.document,&named) && job.handle);fault=8;BasicFileCancel(&job);
    CHECK(job.error==ERROR_BREAK && !job.handle && !opened && job.temporary[0]);fault=0;
    reset();strcpy(deepPath,"RAM:");
    for (i=4;i<116;i+=2) { deepPath[i]='D';deepPath[i+1]='/'; }
    deepPath[20]=']';deepPath[22]='|';strcpy(deepPath+116,"TARGET0.BAS");
    CHECK(strlen(deepPath)==127 && store(deepPath,(const UBYTE *)"OLD",3));
    memcpy(selectorPattern,deepPath,116);strcpy(selectorPattern+116,"*.BAS");strcpy(selectorName,"TARGET0.BAS");
    decision=1;fault=11;renameCount=0;editor.document.saved=0;
    BasicFilesRequest(BASIC_FILE_SAVE_AS);CHECK(!run() && BasicDirty(&editor.document));
    CHECK(!invalidAlert && strlen(recoveryTemporary)==124 && strlen(recoveryBackup)==124);
    CHECK(!memcmp(recoveryTemporary,deepPath,116) && !memcmp(recoveryBackup,deepPath,116));
    CHECK(equals(recoveryBackup,(const UBYTE *)"OLD",3));
    CHECK(equals(recoveryTemporary,(const UBYTE *)"KEEPBA\x9b",7));
    CHECK(!strcmp(BasicFilesPath(),"RAM:ONE.BAS"));
    BasicFilesRequest(BASIC_FILE_RECOVERY);CHECK(!run() && !invalidAlert);
    strcpy(selectorPattern,"RAM:*.BAS");strcpy(selectorName,"ONE.BAS");
    reset();editor.document.saved=0;decision=3;selected=FSEL_CANCEL;
    BasicFilesRequest(BASIC_FILE_QUIT);CHECK(!run() && BasicDirty(&editor.document));
    decision=2;BasicFilesRequest(BASIC_FILE_QUIT);CHECK(run()==1);
    BasicFilesDispose();BasicDocumentDispose(&editor.document);CHECK(AvailMem(MEMF_UPPER)==baseline);return 0;
}
int main(void) { return 0; }
