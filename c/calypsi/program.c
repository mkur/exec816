/* Shared startup for one Process-owned, independently loaded GEM image. */
#include <exec816/aes.h>
#include <exec816/program.h>
#include <proto/dos.h>
#include <proto/exec.h>
#include <gem.h>
#include "program-flags.h"

struct ExecProgramInvocation {
    ULONG entry;
    struct MsgPort *service;
    const volatile UBYTE *stopFlags;
};

LONG EXEC_CALL ExecProgramRun(ULONG argument)
{
    const struct ExecProgramInvocation *invocation=(const void *)argument;
    int (*entry)(void)=(void *)invocation->entry;
    LONG result=20;
    if (!ExecAESAttach(invocation->service)) return 20;
    /* Register before checking an early stop. Later stops address this live
     * registration, including the interval before the first wind_open. */
    if (appl_init()>=0)
        result=(*invocation->stopFlags&EXEC_PROGRAM_STOP_PENDING) ? 0:entry();
    /* Detach settles windows, borrowed drawing records, resources and timers
     * before native Process cleanup releases DOS and execution ownership. */
    if (!ExecAESDetach()) {
        static const char failed[]="GEM teardown failed; Task and image retained.\n";
        Write(Output(),failed,sizeof(failed)-1);
        for (;;) Wait(0);
    }
    return result;
}
