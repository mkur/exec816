/* SPDX-License-Identifier: MIT */
#include "build.h"
#include "build-job.h"
#include "files.h"
#include "file-ui.h"
#include "assist.h"
#include "assist-ui.h"
#include "../../c/calypsi/file-list.h"
#include <exec816/program.h>
#include <exec816/console.h>
#include <exec816/fastbasic-diagnostic.h>
#include <exec816/aes.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <exec/memory.h>
#include <string.h>

enum { CHOOSE=1,RESERVE,RETRY_NAMES,SNAPSHOT,WRITE_SOURCE,CLOSE_SOURCE,LOAD_COMPILER,
    COMPILER,DIAGNOSTIC,LOAD_PROGRAM,PROGRAM,READ_BINARY,PUBLISH,RETIRE };
static struct BasicBuildJob b;
static struct BasicFileJob publication;
static char scratchRecovery[3][17];

static void status(struct BasicEditor *e,const char *text)
{
    UWORD n=strlen(text);if (n>80) n=80;
    memcpy(e->status,text,n);e->status[n]=0;BasicEditorDamage(e,0,BASIC_LINES);
}
static char *decimal(char *out,LONG number)
{
    char digits[10];UWORD n=0;ULONG value;
    if (number<0) { *out++='-';value=0UL-(ULONG)number; }else value=number;
    do { digits[n++]='0'+value%10;value/=10; } while (value);
    while (n) *out++=digits[--n];*out=0;return out;
}
static void cause(LONG error) { if (!b.cause) b.cause=error ? error:ERROR_DISK_NOT_VALIDATED; }
static void hex(char *out,ULONG value)
{
    static const char digits[]="0123456789ABCDEF";UWORD i;
    for (i=8;i;value>>=4) out[--i]=digits[value&15];out[8]=0;
}
static void output_name(char *out,const char *device)
{ strcpy(out,device);hex(out+strlen(out),b.unit); }
static void close_output(void)
{
    if (!b.unit) return;
    if (b.opened) wind_close(b.window);
    if (b.window>=0) wind_delete(b.window);
    if (b.input) Close(b.input);if (b.output) Close(b.output);
    ExecConsoleDestroy(b.unit);b.unit=b.input=b.output=0;b.opened=0;b.window=-1;
}
static WORD output(void)
{
    char path[13];
    if (b.unit) {
        if (!b.opened) { if (!wind_open(b.window,56,21,528,173)) return 0;b.opened=1; }
        return wind_set(b.window,WF_TOP,0,0,0,0);
    }
    b.window=-1;b.unit=ExecConsoleCreate(64,20);if (!b.unit) return 0;
    b.window=wind_create(NAME|CLOSER|MOVER,56,21,528,173);
    if (b.window<0 || !wind_set_str(b.window,WF_NAME,"FastBasic output") ||
        !ExecAESConsole(b.window,b.unit)) goto failed;
    output_name(path,"CON:");b.input=Open(path,MODE_OLDFILE);
    output_name(path,"RAW:");b.output=Open(path,MODE_NEWFILE);
    if (!b.input || !b.output || !ExecConsoleMode(b.input,EXEC_CONSOLE_ATASCII) ||
        !wind_open(b.window,56,21,528,173)) goto failed;
    b.opened=1;return 1;
failed:
    cause(IoErr());close_output();return 0;
}
WORD BasicBuildBusy(void) { return b.phase!=0; }
WORD BasicBuildWork(void) { return b.phase && !b.child; }
ULONG BasicBuildMask(void) { return b.child ? ExecProgramMask(b.child):0; }
void BasicBuildStop(void)
{ if (b.phase) { b.stop=1;if (b.child) ExecBreakProgram(b.child); } }

void BasicBuildRequest(struct BasicEditor *e,WORD action)
{
    if (action==BASIC_BUILD_STOP) { BasicBuildStop();return; }
    if (action==BASIC_BUILD_OUTPUT) { if (!output()) status(e,"Cannot open output");return; }
    if (b.phase || BasicFilesWork() || BasicAssistanceBusy()) { status(e,"Finish the current job first");return; }
    if (action==BASIC_BUILD_INTEGER) {
        b.integer=!b.integer;menu_icheck(e->menu,31,b.integer);
        status(e,b.integer ? "Integer compiler selected":"Floating-point compiler selected");return;
    }
    b.action=action;b.stop=b.owned=b.live=0;b.cause=b.warning=0;b.job=0;
    b.caret=e->caret;b.anchor=e->anchor;b.first=e->first;b.left=e->left;
    b.generation=e->document.generation;b.bytes=e->document.bytes;b.at=0;
    memset(&b.compilerResult,0,sizeof(b.compilerResult));memset(&b.programResult,0,sizeof(b.programResult));
    memset(&b.diagnostic,0,sizeof(b.diagnostic));
    b.project[0]=0;
    if (*BasicFilesPath()) {
        if (!FileSplit(BasicFilesPath(),b.project,b.mask)) { status(e,"Invalid project path");return; }
        b.directory=Lock(b.project,SHARED_LOCK);
        if (!b.directory) { status(e,"Cannot retain project directory");return; }
    }
    b.phase=action==BASIC_BUILD_PUBLISH ? CHOOSE:RESERVE;
    BasicAssistanceCancel(e);status(e,"Preparing immutable source");
}

static void retire(void) { b.phase=RETIRE;b.at=0; }
static WORD close_file(void)
{
    BPTR file=b.file;b.file=0;
    if (file && !Close(file)) { cause(IoErr());return 0; }return 1;
}
static void release_image(void)
{ if (b.image) { ExecReleaseProgram(b.image);b.image=0; } }
static LONG load(const char *name)
{
    LONG result;
    if (!b.loading) { b.loading=ExecLoadBegin(name);if (!b.loading) return -1;return 0; }
    result=ExecLoadStep(b.loading);if (result<=0) return result;
    b.image=ExecLoadTake(b.loading);b.loading=0;return b.image ? 1:-1;
}
static WORD start(WORD compiler)
{
    struct ExecProgramStart s={0};
    s.arguments=compiler ? b.args:NULL;s.length=compiler ? strlen(b.args):0;
    s.input=b.input;s.output=b.output;s.console=b.input;s.directory=b.directory;
    b.child=ExecStartLoaded(b.image,&s);
    if (!b.child) cause(IoErr());
    /* Collect owns execution; release the load reference before any next load. */
    release_image();return b.child!=0;
}
static void restore(struct BasicEditor *e)
{
    e->caret=b.caret;e->anchor=b.anchor;e->first=b.first;e->left=b.left;
    BasicEditorReveal(e);BasicEditorDamage(e,0,BASIC_LINES);
}
static void diagnostic(struct BasicEditor *e)
{
    ULONG line,at,end;
    if (b.diagnostic.native_cause) cause(b.diagnostic.native_cause);
    if (b.diagnostic.line && b.generation==e->document.generation) {
        line=b.diagnostic.line-1;
        if (line<e->document.lines) {
            at=e->document.line[line];end=e->document.line[line+1];
            if (end>at && BasicByte(&e->document,end-1)==10) --end;
            if (b.diagnostic.byte_column<=end-at) {
                b.caret=b.anchor=at+b.diagnostic.byte_column;
            }
        }
    }
    status(e,b.diagnostic.message);
}

static void load_turn(struct BasicEditor *e)
{
    const char *name;
    LONG result;
    WORD compiling=b.phase==LOAD_COMPILER;
    if (compiling) {
        if (b.integer) name="SYS:C/FBCI.COM";
        else name="SYS:C/FBC.COM";
    } else name=b.command;
    result=load(name);
    if (result<0) { cause(IoErr());retire();return; }
    if (!result) return;
    if (!compiling && b.action==BASIC_BUILD_PUBLISH) {
        release_image();b.phase=READ_BINARY;b.at=0;return;
    }
    if (!start(compiling)) { cause(IoErr());retire();return; }
    if (compiling) {
        b.phase=COMPILER;status(e,"Compiling - Ctrl+K Stop");
    } else {
        b.phase=PROGRAM;status(e,"Running - Ctrl+K Stop");
        wind_set(b.window,WF_TOP,0,0,0,0);
    }
}

void BasicBuildStep(struct BasicEditor *e)
{
    LONG result,count,error;UWORD i,n;WORD selected;const char *name;
    if (!b.phase) return;
    if (b.child) {
        struct ExecProgramResult *r=b.phase==COMPILER ? &b.compilerResult:&b.programResult;
        if (!ExecCollectProgram(b.child,r)) return;
        b.child=0;
        if (r->secondary) cause(r->secondary);
        else if (r->primary) cause(r->primary);
        if (b.stop) { cause(ERROR_BREAK);retire();return; }
        if (b.phase==PROGRAM) { retire();return; }
        b.phase=DIAGNOSTIC;return;
    }
    if (b.stop && b.phase!=RETIRE) {
        cause(ERROR_BREAK);if (publication.phase) BasicFileCancel(&publication);
        if (*publication.temporary || *publication.backup) b.recovery=1;
        retire();return;
    }
    switch (b.phase) {
    case CHOOSE:
        if (!*b.pattern) strcpy(b.pattern,"WORK:*.COM");
        selected=0;
        if (!fsel_exinput(b.pattern,b.leaf,&selected,"Build standalone command")) {
            if (ExecAESDiagnostic()==AES_PENDING) return;
            cause(ERROR_BAD_STREAM_NAME);retire();break;
        }
        if (selected!=FSEL_OK) { b.stop=1;retire();break; }
        if (!FileSplit(b.pattern,b.project,b.mask) ||
            !FileJoin(b.target,sizeof(b.target),b.project,b.leaf)) {
            cause(ERROR_BAD_STREAM_NAME);retire();break;
        }
        b.phase=RESERVE;break;
    case RESERVE:
        if (!b.job) {
            if (b.serial==0xffffffffUL) { cause(ERROR_BAD_NUMBER);retire();break; }
            b.job=++b.serial;hex(b.hex,b.job);
            strcpy(b.source,"RAM:");strcat(b.source,b.hex);strcat(b.source,".BAS");
            strcpy(b.command,"RAM:");strcat(b.command,b.hex);strcat(b.command,".COM");
            strcpy(b.diagnostics,"RAM:");strcat(b.diagnostics,b.hex);strcat(b.diagnostics,".DIA");
            /* FS83 requires a letter first. A..P encode the high nibble;
             * the remaining seven hex digits preserve the complete job ID. */
            b.source[4]=b.command[4]=b.diagnostics[4]='A'+(b.job>>28);
        }
        name=b.owned==0 ? b.source:b.owned==1 ? b.command:b.diagnostics;
        b.file=Open(name,MODE_CREATE_EXCLUSIVE);
        if (!b.file) {
            error=IoErr();
            if (error==ERROR_OBJECT_EXISTS) {
                b.phase=RETRY_NAMES;b.at=0;break;
            }
            cause(error);retire();break;
        }
        b.live|=1U<<b.owned;++b.owned;if (!close_file()) { retire();break; }
        if (b.owned<3) break;
        b.snapshot=AllocMem(BASIC_BYTES,MEMF_UPPER);
        if (!b.snapshot) { cause(ERROR_NO_FREE_STORE);retire();break; }
        b.phase=SNAPSHOT;break;
    case RETRY_NAMES:
        if (b.at<b.owned) {
            name=b.at==0 ? b.source:b.command;
            if (!DeleteFile(name)) { cause(IoErr());retire();break; }
            b.live&=~(1U<<b.at);
            ++b.at;break;
        }
        b.owned=0;b.at=b.job=0;b.phase=RESERVE;break;
    case SNAPSHOT:
        n=b.bytes-b.at>1024 ? 1024:b.bytes-b.at;
        BasicCopy(&e->document,b.at,b.snapshot+b.at,n);
        for (i=0;i<n;++i) if (b.snapshot[b.at+i]==10) b.snapshot[b.at+i]=155;
        b.at+=n;
        if (b.at==b.bytes) { b.at=0;b.phase=WRITE_SOURCE; }
        break;
    case WRITE_SOURCE:
        if (!b.file) { b.file=Open(b.source,MODE_NEWFILE);if (!b.file) { cause(IoErr());retire(); }break; }
        if (b.at==b.bytes) { b.phase=CLOSE_SOURCE;break; }
        n=b.bytes-b.at>1024 ? 1024:b.bytes-b.at;
        count=Write(b.file,b.snapshot+b.at,n);
        if (count<=0) { cause(IoErr());retire(); }else b.at+=count;
        break;
    case CLOSE_SOURCE:
        if (!close_file()) { retire();break; }
        if (!output()) { cause(IoErr());retire();break; }
        strcpy(b.args,b.source);strcat(b.args," ");strcat(b.args,b.command);
        strcat(b.args," ");strcat(b.args,b.diagnostics);strcat(b.args," ");strcat(b.args,b.hex);
        b.phase=LOAD_COMPILER;status(e,b.integer ? "Loading integer compiler":"Loading floating-point compiler");break;
    case LOAD_COMPILER:
    case LOAD_PROGRAM:
        load_turn(e);break;
    case DIAGNOSTIC:
        if (!b.file) { b.file=Open(b.diagnostics,MODE_OLDFILE);if (!b.file) { cause(IoErr());retire(); }break; }
        count=Read(b.file,&b.diagnostic,sizeof(b.diagnostic));
        if (count!=sizeof(b.diagnostic) || !ExecFastBasicDiagnosticMatches(&b.diagnostic,count,b.job,b.source) ||
            b.generation!=e->document.generation) { cause(ERROR_BAD_STREAM_NAME);close_file();retire();break; }
        /* The bounded file is a complete record, never a prefix of another one. */
        count=Read(b.file,b.buffer,1);
        if (count!=0) cause(count<0 ? IoErr():ERROR_OBJECT_TOO_LARGE);
        close_file();diagnostic(e);
        if (b.cause || b.diagnostic.stage!=FBD_STAGE_COMPLETE) { if (!b.cause) cause(306);retire();break; }
        if (b.action==BASIC_BUILD_CHECK) { retire();break; }
        b.phase=LOAD_PROGRAM;status(e,"Loading fresh command");break;
    case PROGRAM:case COMPILER:break;
    case READ_BINARY:
        if (!b.file) {
            b.file=Open(b.command,MODE_OLDFILE);if (!b.file) { cause(IoErr());retire();break; }
            if (Seek(b.file,0,OFFSET_END)<0 || (b.binaryBytes=Seek(b.file,0,OFFSET_BEGINNING))==0 ||
                b.binaryBytes>65552UL) { cause(IoErr());retire();break; }
            b.binary=AllocMem(b.binaryBytes,MEMF_UPPER);b.at=0;
            if (!b.binary) { cause(ERROR_NO_FREE_STORE);retire(); }break;
        }
        n=b.binaryBytes-b.at>1024 ? 1024:b.binaryBytes-b.at;
        if (n) {
            count=Read(b.file,b.binary+b.at,n);
            if (count<=0) { cause(IoErr());retire(); }else b.at+=count;
            break;
        }
        if (Read(b.file,b.buffer,1)!=0 || !close_file()) { cause(IoErr());retire();break; }
        if (!BasicSaveBufferBegin(&publication,b.binary,b.binaryBytes,b.target)) {
            cause(publication.error);retire();break;
        }
        b.binary=0;b.phase=PUBLISH;status(e,"Publishing standalone command");break;
    case PUBLISH:
        result=BasicFileStep(&publication,NULL,NULL);
        if (result) {
            if (result<0) cause(publication.error);
            b.warning=publication.warning;
            if (publication.error || publication.warning) b.recovery=1;
            retire();
        }
        break;
    case RETIRE:
        if (b.loading) { ExecLoadCancel(b.loading);b.loading=0;return; }
        if (b.image) { release_image();return; }
        if (b.file) { close_file();return; }
        if (b.at<b.owned) {
            name=b.at==0 ? b.source:b.at==1 ? b.command:b.diagnostics;
            if ((b.live&(1U<<b.at)) && !DeleteFile(name)) {
                if (!b.warning) b.warning=IoErr();
                strcpy(scratchRecovery[b.at],name);b.recovery=1;
            }
            b.live&=~(1U<<b.at);++b.at;return;
        }
        if (b.snapshot) { FreeMem(b.snapshot,BASIC_BYTES);b.snapshot=0; }
        if (b.binary) { FreeMem(b.binary,b.binaryBytes);b.binary=0; }
        if (b.directory) { UnLock(b.directory);b.directory=0; }
        b.owned=0;restore(e);wind_set(e->app.window,WF_TOP,0,0,0,0);
        if (b.stop) status(e,b.recovery ? "Stopped - File > Recovery paths":"Stopped");
        else if (b.cause) {
            if (!b.diagnostic.native_cause) {
                strcpy(b.notice,"Build/run failed (error ");decimal(b.notice+24,b.cause);
                strcat(b.notice,")");status(e,b.notice);
                if (b.output) { Write(b.output,b.notice,strlen(b.notice));Write(b.output,"\n",1); }
            }
        } else status(e,b.warning ? "Completed with cleanup warning":
            b.action==BASIC_BUILD_CHECK ? "Check passed":b.action==BASIC_BUILD_PUBLISH ? "Standalone command built":"Program completed");
        b.phase=0;
        break;
    }
}

WORD BasicBuildMessage(struct BasicEditor *e,WORD *m)
{
    (void)e;
    if (!b.unit || m[3]!=b.window) return 0;
    if (m[0]==WM_TOPPED) wind_set(b.window,WF_TOP,0,0,0,0);
    else if (m[0]==WM_MOVED) {
        m[4]=((m[4]+8)&~7)-8;m[5]=((m[5]+11)&~7)-11;
        wind_set(b.window,WF_CXYWH,m[4],m[5],528,173);
    } else if (m[0]==WM_CLOSED) {
        BasicBuildStop();if (b.opened) { wind_close(b.window);b.opened=0; }
    }
    return 1;
}
WORD BasicBuildRecovery(struct BasicEditor *e)
{
    UWORD i;
    if (!b.recovery) return 0;
    if (!*publication.temporary && !*publication.backup &&
        !*scratchRecovery[0] && !*scratchRecovery[1] && !*scratchRecovery[2]) return 0;
    status(e,"Build recovery paths retained in output");
    if (!output()) return 1;
    if (*publication.temporary) { Write(b.output,publication.temporary,strlen(publication.temporary));Write(b.output,"\n",1); }
    if (*publication.backup) { Write(b.output,publication.backup,strlen(publication.backup));Write(b.output,"\n",1); }
    for (i=0;i<3;++i) if (*scratchRecovery[i]) {
        Write(b.output,scratchRecovery[i],strlen(scratchRecovery[i]));Write(b.output,"\n",1);
    }
    return 1;
}
void BasicBuildDispose(void)
{
    UWORD i;const char *name;
    BasicBuildStop();
    if (b.child) { struct ExecProgramResult result;ExecWaitProgram(b.child,&result);b.child=0; }
    if (b.loading) { ExecLoadCancel(b.loading);b.loading=0; }
    release_image();close_file();
    for (i=0;i<b.owned;++i) if (b.live&(1U<<i)) {
        name=i==0 ? b.source:i==1 ? b.command:b.diagnostics;DeleteFile(name);
    }
    if (publication.phase) BasicFileCancel(&publication);
    if (b.snapshot) { FreeMem(b.snapshot,BASIC_BYTES);b.snapshot=0; }
    if (b.binary) { FreeMem(b.binary,b.binaryBytes);b.binary=0; }
    if (b.directory) { UnLock(b.directory);b.directory=0; }
    close_output();
}
