/* Shared startup for one Process-owned, independently loaded GEM image. */
#include <exec816/aes.h>
#include <exec816/program.h>
#include <exec816/c-runtime.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include <gem.h>
#include <string.h>
#include "program-flags.h"

struct ExecProgramInvocation {
    ULONG entry;
    struct MsgPort *service;
    const volatile UBYTE *stopFlags;
};
static void retained(const char *message)
{
    Write(Output(),message,strlen(message));
    for (;;) Wait(0);
}
LONG EXEC_CALL ExecProgramRun(ULONG argument)
{
    const struct ExecProgramInvocation *invocation=(const void *)argument;
    ExecCRuntimeEntry entry=(void *)invocation->entry;
    struct ExecCRuntimeCall call;
    BOOL attached=FALSE;
    memset(&call,0,sizeof(call));
    call.version=EXEC_CRT_VERSION;call.phase=EXEC_CRT_INIT;
    call.name=FindTask(NULL)->tc_Node.ln_Name;call.arguments=ExecGetArgStr();
    if (entry(&call)) {
        attached=ExecAESAttach(invocation->service);
        if (attached && appl_init()>=0) {
            /* Register before observing stop, including before first wind_open. */
            if (*invocation->stopFlags&EXEC_PROGRAM_STOP_PENDING)
                call.flags|=EXEC_CRT_FLAG_EARLY_STOP;
            else {
                call.phase=EXEC_CRT_RUN;
                if (!entry(&call)) retained("C RUN rejected; Process retained.\n");
            }
        } else { call.primary=20;call.secondary=ERROR_NO_FREE_STORE; }
    }
    call.phase=EXEC_CRT_FINISH;
    if (!entry(&call)) retained("C FINISH rejected; Process retained.\n");
    /* All C backing stays owned until windows, borrowed drawing records,
     * resources and timers have their retirement acknowledgement. */
    if (attached && !ExecAESDetach())
        retained("GEM teardown failed; Task and image retained.\n");
    call.phase=EXEC_CRT_RELEASE;
    if (!entry(&call)) retained("C RELEASE rejected; Process retained.\n");
    SetIoErr(call.secondary);
    return call.primary;
}
