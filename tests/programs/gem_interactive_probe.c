/* Diagnostic-only resource admission. Production does not link these hooks. */
#include "ui.h"
#include "ui-events.h"
#include <clib/alib_protos.h>
#include <string.h>
volatile UWORD variant;
extern volatile UWORD mouseStatus;
/* Mailbox stimulus is copied by a real small diagnostic Task. Only the
 * ordinary queue publication path can change application input state. */
struct InputEvent injectEvents[33] __attribute__((aligned(2)));
static struct InputEvent injectCopy __attribute__((aligned(2)));
volatile UWORD injectSource;
volatile UWORD injectRequest, injectDone, injectCount, injectResults[33];
volatile UWORD injectQueued, injectLost, injectWhilePending;
volatile UWORD holdCursor, cursorHeld, holdLossAck, lossAck, injectAckPhase;
volatile UWORD holdInput, inputHeld, exhaustReady, exhaustedReady;
volatile UWORD faultNext, faultInjected, blitsStarted, stopped, permanent;
UBYTE UiBusy(void)
{
    if (faultInjected && (permanent || !stopped)) return 2;
    return *(volatile UBYTE *)0xd653UL;
}
void UiBlitStarted(void)
{
    ++blitsStarted;
    if (faultNext) { faultNext=0; faultInjected=1; }
}
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
static BYTE heldBits[16];
static UWORD bitCount;
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
                if (injectSource) injectResults[i]=UiPostMouse(&injectCopy);
                else {
                    injectCopy.flags|=INPUT_INJECTED;
                    injectResults[i]=UiPostPointer(&injectCopy);
                }
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
static void exhaustSignals(void)
{
    BYTE bit;
    while ((bit=AllocSignal(-1))>=0 && bitCount<16) heldBits[bitCount++]=bit;
    check(AllocSignal(-1)<0);
}
void UiProbe(UWORD point)
{
    if (point==16 && variant==30) exhaustSignals();
    if ((point==12 && variant==31) || (point==13 && variant==32) ||
        (point==14 && variant==33)) mouseStatus=INPUT_NO_MEMORY;
    if (point==15) while (bitCount) FreeSignal(heldBits[--bitCount]);
    if (point==0) {
        void EXEC_PTR *address=&boot;
        check(ExecSameAddress(address,&boot));
        check(!ExecSameAddress(address,(void *)((ULONG)&boot^0x10000UL)));
        check(!ExecSameAddress(address,(void *)((ULONG)&boot|0x1000000UL)));
    }
    if ((point==0 && variant==8) || (point==1 && variant==7)) exhaust();
    if (point==0 && variant==17) exhaustSignals();
    if (point==5 && variant==18) exhaustSignals();
    if (point==2) {
        restore();
        while (bitCount) FreeSignal(heldBits[--bitCount]);
    }
    if (point==7 && inputHeld==0 && holdInput) {
        Forbid(); inputHeld=1;
        while (holdInput) { }
        inputHeld=0; Permit();
    }
    if (point==7 && exhaustReady && !exhaustedReady) {
        exhaust(); exhaustedReady=1;
    }
    if (point==8 && exhaustedReady) restore();
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
        if (variant==5 || variant==34) {
            occupiedConfig.version=INPUT_VERSION;
            occupiedConfig.source=variant==34 ? INPUT_SOURCE_POINTER : INPUT_SOURCE_KEYBOARD;
            occupiedConfig.wakeMask=boot.rootMask;
            if (variant==34) { occupiedConfig.pointerProtocol=INPUT_POINTER_ST; occupiedConfig.pointerPort=1; }
            check(InputAcquire(&occupiedInput,&occupiedConfig)==INPUT_OK);
        }
        if (variant==6) check(VbxeOpen(&occupiedDisplay)==DISPLAY_OK);
    }
    if (point==11) {
        if (variant==5 || variant==34) check(InputRelease(&occupiedInput)==INPUT_OK);
        if (variant==6) check(VbxeClose(&occupiedDisplay)==DISPLAY_OK);
    }
}
