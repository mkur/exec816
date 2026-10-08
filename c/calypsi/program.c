/* Shared startup for one Process-owned, independently loaded GEM image. */
#include <exec816/aes.h>
#include <exec816/program.h>
#include <proto/dos.h>
#include <proto/exec.h>

struct ExecProgramInvocation { ULONG entry; struct MsgPort *service; };

LONG EXEC_CALL ExecProgramRun(ULONG argument)
{
    const struct ExecProgramInvocation *invocation=(const void *)argument;
    int (*entry)(void)=(void *)invocation->entry;
    LONG result;
    if (!ExecAESAttach(invocation->service)) return 20;
    result=entry();
    /* Detach settles windows, borrowed drawing records, resources and timers
     * before native Process cleanup releases DOS and execution ownership. */
    if (!ExecAESDetach()) {
        static const char failed[]="GEM teardown failed; Task and image retained.\n";
        Write(Output(),failed,sizeof(failed)-1);
        for (;;) Wait(0);
    }
    return result;
}
