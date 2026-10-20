/* SPDX-License-Identifier: MIT */
#include "file-ui.h"
#include "files.h"
#include "../../c/calypsi/file-list.h"
#include <exec816/aes.h>
#include <string.h>

/* All selector and transaction storage belongs to this loadable application.
 * The committed name is separate from editable selector fields. */
static struct {
    struct BasicFile named;
    struct BasicFileJob job;
    WORD request,after,dialog,quit,approved,cancelled;
    ULONG approvedGeneration;
    char pattern[128],file[13],directory[128],mask[128],target[128],alert[384];
} ui;

static void status(struct BasicEditor *e,const char *text)
{
    UWORD n=strlen(text);if (n>80) n=80;
    memcpy(e->status,text,n);e->status[n]=0;
    BasicEditorDamage(e,e->first,e->first+e->rows);
}
static char *decimal(char *p,ULONG value)
{
    char digits[10];UWORD n=0;
    do { digits[n++]='0'+value%10;value/=10; } while (value);
    while (n) *p++=digits[--n];*p=0;return p;
}
static void error(struct BasicEditor *e)
{
    char *p=ui.alert;
    strcpy(p,"File error ");decimal(p+11,ui.job.error ? ui.job.error:ui.job.warning);
    status(e,p);ui.dialog=1;
}
/* Standard alerts accept five 40-character lines. Present each full recovery
 * name separately, in 32-character pieces fitting the minimum work area.
 * Double the alert delimiters so legal filename bytes remain literal. */
static void recovery_alert(void)
{
    const char *name;char *out=ui.alert;UWORD i=0,unit=0;UBYTE c;
    if (ui.dialog==1) {
        strcpy(out,ui.job.error ? "[1][File error ":"[1][Warning ");
        decimal(out+strlen(out),ui.job.error ? ui.job.error:ui.job.warning);
        strcat(out,"|Recovery paths follow.][OK]");return;
    }
    name=ui.dialog==2 ? ui.job.temporary:ui.job.backup;
    strcpy(out,ui.dialog==3 ? "[0][Backup recovery path|":
        ui.job.complete ? "[0][Completed temporary path|":"[0][Uncertain temporary path|");
    out+=strlen(out);
    while (name[i]) {
        if (unit==32) { *out++='|';unit=0; }
        c=name[i++];*out++=c;if (c==']' || c=='|') *out++=c;++unit;
    }
    strcpy(out,"][OK]");
}
void BasicFilesRequest(WORD action) { ui.request=action;ui.approved=0; }
WORD BasicFilesWork(void) { return ui.request || ui.after || ui.job.phase || ui.dialog>0 || ui.cancelled; }
WORD BasicFilesLoading(void) { return ui.job.phase && !ui.job.save; }
const char *BasicFilesPath(void) { return ui.named.path; }
void BasicFilesCancel(void)
{
    if (ui.job.phase) { BasicFileCancel(&ui.job);ui.cancelled=1; }
    ui.request=ui.after=0;
}
void BasicFilesDispose(void) { BasicFilesCancel();ui.cancelled=0; }

static WORD choose(struct BasicEditor *e,WORD save)
{
    WORD button;
    if (!*ui.pattern) strcpy(ui.pattern,"WORK:*.BAS");
    if (!fsel_exinput(ui.pattern,ui.file,&button,save ? "Save BASIC source":"Open BASIC source")) {
        if (ExecAESDiagnostic()==AES_PENDING) return 0;
        status(e,"File selector failed");return -1;
    }
    if (button!=FSEL_OK) return -1;
    if (!FileSplit(ui.pattern,ui.directory,ui.mask) ||
        !FileJoin(ui.target,sizeof(ui.target),ui.directory,ui.file)) {
        status(e,"Path exceeds 127 bytes");return -1;
    }
    return 1;
}

WORD BasicFilesStep(struct BasicEditor *e)
{
    WORD action,result;
    if (ui.request==BASIC_FILE_RECOVERY) {
        ui.request=0;
        if (ui.job.error || ui.job.warning || *ui.job.temporary || *ui.job.backup) ui.dialog=1;
        else status(e,"No recovery paths retained");
    }
    if (ui.dialog<0) { if (ui.request) ui.dialog=0;else return 0; }
    if (ui.cancelled) { ui.cancelled=0;error(e);return 0; }
    if (ui.dialog) {
        recovery_alert();result=form_alert(1,ui.alert);
        if (!result && ExecAESDiagnostic()==AES_PENDING) return 2;
        /* A failed presentation preserves the recovery paths and source. */
        if (!result) { ui.dialog=-ui.dialog;status(e,"Recovery paths: File > Recovery");return 0; }
        if (ui.dialog==1 && *ui.job.temporary) ui.dialog=2;
        else if (ui.dialog<3 && *ui.job.backup) ui.dialog=3;
        else ui.dialog=0;
        return 0;
    }
    if (ui.job.phase) {
        if (ui.request==BASIC_FILE_QUIT) { BasicFileCancel(&ui.job);ui.after=0;error(e);return 0; }
        result=BasicFileStep(&ui.job,&e->document,&ui.named);
        if (!result) return 2;
        if (result<0) { ui.request=ui.after=0;error(e);return 0; }
        if (!ui.job.save) {
            e->caret=e->anchor=e->first=e->left=0;
            status(e,BasicDirty(&e->document) ? "Mixed line endings normalized; save to keep changes":"Source opened");
        } else {
            status(e,BasicDirty(&e->document) ? "Snapshot saved; newer edits remain unsaved":"Source saved");
            if (ui.job.warning) error(e);
        }
        if (ui.after) { ui.request=ui.after;ui.after=0; }
        return 0;
    }
    action=ui.request;if (!action) return ui.quit;
    if ((action==BASIC_FILE_NEW || action==BASIC_FILE_OPEN || action==BASIC_FILE_QUIT) && BasicDirty(&e->document) &&
        (!ui.approved || ui.approvedGeneration!=e->document.generation)) {
        result=form_alert(1,"[2][Save source changes?][Save|Discard|Cancel]");
        if (!result && ExecAESDiagnostic()==AES_PENDING) return 2;
        if (result==1) { ui.after=action;ui.request=BASIC_FILE_SAVE;return 0; }
        if (result!=2) {
            if (!result) status(e,"Restore window to confirm changes");
            ui.request=0;return 0;
        }
        ui.approved=1;ui.approvedGeneration=e->document.generation;
    }
    if (action==BASIC_FILE_QUIT) { ui.request=0;ui.quit=1;return 1; }
    if (action==BASIC_FILE_NEW) {
        struct BasicDocument fresh;
        if (BasicDocumentInit(&fresh)) status(e,"Not enough memory for a new source");
        else {
            BasicDocumentDispose(&e->document);e->document=fresh;
            memset(&ui.named,0,sizeof(ui.named));e->caret=e->anchor=e->first=e->left=0;status(e,"New source");
        }
        ui.request=0;return 0;
    }
    if (action==BASIC_FILE_OPEN || action==BASIC_FILE_SAVE_AS || !*ui.named.path) {
        result=choose(e,action!=BASIC_FILE_OPEN);
        if (!result) return 2;
        if (result<0) { ui.request=ui.after=0;return 0; }
    } else strcpy(ui.target,ui.named.path);
    ui.request=0;
    result=action==BASIC_FILE_OPEN ? BasicLoadBegin(&ui.job,ui.target):
        BasicSaveBegin(&ui.job,&e->document,&ui.named,ui.target);
    if (!result) { ui.after=0;error(e); }
    else status(e,action==BASIC_FILE_OPEN ? "Opening - Escape cancels":"Saving snapshot - Escape cancels");
    return 0;
}
