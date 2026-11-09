/* SPDX-License-Identifier: MIT. One synchronous calling Task per loaded Image. */
#include "internal.h"
#include <proto/dos.h>
#include <proto/exec.h>
#include <setjmp.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

/* The builder emits this matching typed call to the selected main signature. */
extern int __exec_c_runtime_main(int,char **);
static struct ExecCRuntimeState scope;
static struct ExecCRuntimeCall *activeCall;
static int argc;
static char **argv;
static void (*handlers[EXEC_CRT_ATEXIT_SLOTS])(void);
static UWORD handlerCount,boundaryActive;
static jmp_buf boundary;

static void retained_fault(void)
{
    static const char message[]="C termination outside its boundary; Process retained.\n";
    Write(Output(),message,sizeof(message)-1);
    for (;;) Wait(0);
}
static void terminate(int status,int abnormal,LONG cause)
{
    if (!boundaryActive) retained_fault();
    if (abnormal) activeCall->flags|=EXEC_CRT_FLAG_ABNORMAL;
    activeCall->primary=status;
    activeCall->secondary=cause ? cause:status ? IoErr():0;
    longjmp(boundary,1);
    retained_fault();
}
void exit(int status) { terminate(status,0,0); }
void _Exit(int status) { terminate(status,1,0); }
void _Stub_exit(int status) { _Exit(status); }
void abort(void)
{
    static const char message[]="C program aborted.\n";
    Write(Output(),message,sizeof(message)-1);
    terminate(20,1,ERROR_BREAK);
}
void _Stub_assert(const char *file,int line)
{
    char message[96],digits[6];
    UWORD used=0,count=0,value=(unsigned int)line;
    const char *prefix="C assertion: ";
    while (*prefix) message[used++]=*prefix++;
    while (*file && used<76) message[used++]=*file++;
    message[used++]=':';
    do { digits[count++]='0'+value%10;value/=10; } while (value && count<sizeof(digits));
    while (count) message[used++]=digits[--count];
    message[used++]='\n';
    Write(Output(),message,used);
    terminate(20,1,ERROR_BAD_ARGUMENTS);
}
int atexit(void (*function)(void))
{
    if (handlerCount==EXEC_CRT_ATEXIT_SLOTS) { errno=ENOMEM;return -1; }
    handlers[handlerCount++]=function;return 0;
}
static LONG initialize(struct ExecCRuntimeCall *call)
{
    activeCall=call;argc=0;argv=NULL;handlerCount=boundaryActive=0;
    memset(handlers,0,sizeof(handlers));call->flags=0;
    ExecCRuntimeHeapBegin();
    ExecCRuntimeFilesBegin();ExecCRuntimeStdioBegin();ExecCRuntimeLibraryBegin();
    if (!ExecCRuntimeArguments(call->arguments,call->name,&argc,&argv)) {
        call->secondary=IoErr();return 0;
    }
    call->primary=call->secondary=0;SetIoErr(0);
    return 1;
}
static LONG run(struct ExecCRuntimeCall *call)
{
    activeCall=call;boundaryActive=1;
    if (!setjmp(boundary)) {
        call->primary=__exec_c_runtime_main(argc,argv);
        call->secondary=call->primary ? IoErr():0;
    }
    boundaryActive=0;
    return call->primary;
}
static void finish(struct ExecCRuntimeCall *call)
{
    LONG cause;
    activeCall=call;
    /* FINISH ends C object lifetimes but holds their backing through GUI ACK. */
    ExecCRuntimeHeapDefer();
    if (!(call->flags&EXEC_CRT_FLAG_ABNORMAL)) {
        boundaryActive=1;
        if (!setjmp(boundary)) while (handlerCount) handlers[--handlerCount]();
        boundaryActive=0;
    }
    handlerCount=0;
    cause=ExecCRuntimeStdioFinish((call->flags&EXEC_CRT_FLAG_ABNORMAL)!=0);
    if (!call->primary && cause) { call->primary=20;call->secondary=cause; }
    SetIoErr(call->secondary);
}
static void release(struct ExecCRuntimeCall *call)
{
    ExecCRuntimeHeapRelease();argc=0;argv=NULL;activeCall=NULL;
    memset(handlers,0,sizeof(handlers));
    SetIoErr(call->secondary);
}
LONG __exec_c_runtime_entry(struct ExecCRuntimeCall *call)
{
    static const struct ExecCRuntimeOps operations={initialize,run,finish,release};
    return ExecCRuntimePhase(&scope,call,&operations);
}
