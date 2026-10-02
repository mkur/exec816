/* Diagnostic-only resource admission. Production does not link these hooks. */
#include "ui.h"
#include <clib/alib_protos.h>
volatile UWORD variant;
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
