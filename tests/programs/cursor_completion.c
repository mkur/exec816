#include "aes-private.h"
#include "vdi-private.h"
#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <exec816/runtime.h>
#include "gem-drawing.h"

struct ExecAESContext context;
static struct AESDirectory directory;
static struct ExecVDIWorkstation workstation;
static struct Task *parent,*worker;
static struct TaskLease lease;
static volatile UWORD variant,ready,stop;
UWORD checks,failures,borrows;
volatile UWORD progress;
LONG EXEC_CALL ExecAESMouseApply(ULONG value);
#define OTHER 0x20000UL

static void Check(int okay) { ++checks;if (!okay) ++failures; }

/* Only the hardware boundary is substituted. Admission BUSY must defer;
 * a device failure must report failure; a newer completed target satisfies us. */
UWORD GemDrawingMouseBorrow(struct DisplayGrant *grant,struct AESMouseState *mouse)
{
    (void)grant;
    ++borrows;
    Check(context.busy==1);
    if (variant==3) return DISPLAY_BUSY;
    if (variant==4) return DISPLAY_DEVICE_FAULT;
    if (variant==5) ++mouse->revision;
    mouse->completed=mouse->revision;
    return DISPLAY_OK;
}

void CompletionWorker(void)
{
    AllocSignal(16);
    ready=1;Signal(parent,OTHER);
    for (;;) {
        Wait(0x10000UL);
        if (stop) break;
        ++progress;
        directory.mouse.completed=directory.mouse.revision;
        Signal(parent,1UL<<context.replies->mp_SigBit);
    }
    FreeSignal(16);Signal(parent,OTHER);Wait(0);
}

int main(void)
{
    UWORD i;
    static const UWORD expectedBorrows[]={1,0,0,1,1,1,0};
    parent=FindTask(NULL);
    Check(AllocSignal(17)==17);
    context.replies=CreateMsgPort();Check(context.replies!=NULL);
    context.directory=&directory;
    Forbid();
    worker=CreateTask("cursor completion",0,(APTR)CompletionWorker,1);
    Check(worker!=NULL && RetainTask(worker,&lease));
    Permit();
    while (!ready) Wait(OTHER);
    SetSignal(0,OTHER);
    directory.owner=worker;directory.mask=0x10000UL;
    for (i=0;i<7;++i) {
        LONG result;
        variant=i;borrows=0;
        context.busy=1;context.request.status=AES_OK;
        context.request.mouseWait=2;
        context.workstation=i==2 ? NULL:&workstation;
        directory.mouse.revision=2;
        directory.mouse.completed=i==1 ? 2:1;
        directory.mouse.status=i==6 ? DISPLAY_DEVICE_FAULT:0;
        Signal(parent,OTHER);
        result=ExecAESMouseApply((ULONG)&context);
        Check(result==(i!=4 && i!=6));
        Check(context.request.status==((i==4 || i==6) ? AES_DISPLAY_ERROR:AES_OK));
        Check(!context.request.mouseWait && borrows==expectedBorrows[i]);
        Check((SetSignal(0,OTHER)&OTHER)!=0);
    }
    Check(progress==2);
    stop=1;Signal(worker,0x10000UL);Wait(OTHER);
    Forbid();Check(ReleaseTask(&lease));RemTask(worker);Permit();
    DeleteMsgPort(context.replies);FreeSignal(17);
    return failures;
}

LONG EXEC_CALL CompletionRun(ULONG unused)
{
    (void)unused;
    return main();
}
