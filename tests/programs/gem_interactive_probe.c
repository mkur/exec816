/* Diagnostic-only resource admission. Production does not link these hooks. */
#include "ui.h"
#include "ui-events.h"
#include <clib/alib_protos.h>
#include <string.h>
volatile UWORD variant;
/* Mailbox stimulus is copied by a real small diagnostic Task. Only the
 * ordinary queue publication path can change application input state. */
struct InputEvent injectEvents[33] __attribute__((aligned(2)));
static struct InputEvent injectCopy __attribute__((aligned(2)));
volatile UWORD injectRequest, injectDone, injectCount, injectResults[33];
volatile UWORD injectQueued, injectLost, injectWhilePending;
volatile UWORD holdCursor, cursorHeld, holdLossAck, lossAck, injectAckPhase;
void UiLossAck(void)
{
    UWORD tick;
    if (!holdLossAck) return;
    lossAck=1;
    tick=DisplayTicks();
    while ((UWORD)(DisplayTicks()-tick)<4) { }
    lossAck=0;
}
void UiCursorGate(void)
{
    if (holdCursor) {
        cursorHeld=1;
        while (holdCursor) ExecYield();
        cursorHeld=0;
    }
}
static struct Task *injector, *application;
static struct TaskLease injectorLease;
static BYTE injectorBit=-1;
static volatile UWORD injectorStop, injectorRetired;
static struct VbxeDisplay occupiedDisplay;
static struct InputLease occupiedInput __attribute__((aligned(2)));
static struct InputConfig occupiedConfig __attribute__((aligned(2)));
static void *held[32];
static ULONG sizes[32];
static UWORD heldCount;
static void check(UWORD good)
{
    ++checks;
    if (!good) { if (!failures) firstFailure=checks; ++failures; }
}
void UiUnusedTask(void) { Wait(0); }
void UiInjector(void)
{
    UWORD seen=0,i;
    for (;;) {
        if (injectorStop) break;
        if (injectRequest!=seen) {
            seen=injectRequest;
            injectAckPhase=lossAck;
            check(injectCount>0 && injectCount<=33);
            Forbid();
            for (i=0;i<injectCount && i<33;++i) {
                memcpy(&injectCopy,&injectEvents[i],sizeof(injectCopy));
                injectCopy.flags|=INPUT_INJECTED;
                injectResults[i]=UiPostPointer(&injectCopy);
            }
            injectQueued=uiQueued;
            injectLost=uiLoss;
            injectWhilePending=client.pending!=NULL;
            injectDone=seen;
            Permit();
        }
        ExecYield();
    }
    Forbid();
    injectorRetired=1;
    Signal(application,1UL<<injectorBit);
    RemTask(NULL);
}
static void exhaust(void)
{
    ULONG size;
    while ((size=AvailMem(MEMF_LARGEST))!=0 && heldCount<32) {
        held[heldCount]=AllocMem(size,MEMF_PUBLIC);
        sizes[heldCount++]=size;
        check(held[heldCount-1]!=NULL);
    }
    check(AvailMem(0)==0);
}
static void restore(void)
{
    while (heldCount) { --heldCount; FreeMem(held[heldCount],sizes[heldCount]); }
}
void UiProbe(UWORD point)
{
    if (point==0) {
        void EXEC_PTR *address=&boot;
        check(ExecSameAddress(address,&boot));
        check(!ExecSameAddress(address,(void *)((ULONG)&boot^0x10000UL)));
        check(!ExecSameAddress(address,(void *)((ULONG)&boot|0x1000000UL)));
    }
    if ((point==0 && variant==8) || (point==1 && variant==7)) exhaust();
    if (point==2) restore();
    if (point==3 && variant>=100) {
        application=FindTask(NULL);
        injectorBit=AllocSignal(-1); check(injectorBit>=0);
        Forbid();
        injector=CreateTask("pointer fixture",0,(APTR)UiInjector,1024UL);
        check(injector!=NULL && RetainTask(injector,&injectorLease));
        Permit();
    }
    if (point==4 && injector) {
        Forbid();
        check(ReleaseTask(&injectorLease));
        injectorStop=1;
        Permit();
        while (!injectorRetired) Wait(1UL<<injectorBit);
        injector=NULL;
        FreeSignal(injectorBit); injectorBit=-1;
    }
    if (point==3 && variant==9) check(CreateTask("third large",0,(APTR)UiUnusedTask,2560UL)==NULL);
    if (point==10) {
        if (variant==5) {
            occupiedConfig.version=INPUT_VERSION;
            occupiedConfig.source=INPUT_SOURCE_KEYBOARD;
            occupiedConfig.wakeMask=boot.rootMask;
            check(InputAcquire(&occupiedInput,&occupiedConfig)==INPUT_OK);
        }
        if (variant==6) check(VbxeOpen(&occupiedDisplay)==DISPLAY_OK);
    }
    if (point==11) {
        if (variant==5) check(InputRelease(&occupiedInput)==INPUT_OK);
        if (variant==6) check(VbxeClose(&occupiedDisplay)==DISPLAY_OK);
    }
}
