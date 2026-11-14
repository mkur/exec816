/* Physical page callbacks, preemptible CPU work and exact VRAM preservation. */
#include "../../platform/altirraos/vbxe-internal.h"
#include <hardware/vbxe-snapshots.h>
#include <string.h>

volatile UWORD mappedChecks,mappedFailures,mappedCallbacks,mappedTicks;
static UBYTE bytes[256];
static UWORD pageIndex;

static void check(UWORD good)
{
    ++mappedChecks;
    if (!good) ++mappedFailures;
}

static void modify(UBYTE *window,void *context)
{
    volatile UBYTE *v=window;
    UWORD i,start=DisplayTicks();
    check(context==&pageIndex);
    check((ULONG)window==0x8000UL);
    for (i=0;i<4096;++i) {
        check(v[i]==(UBYTE)(i+pageIndex*37));
        v[i]^=0x5a;
    }
    /* Keep the real mapping live across VBI and ordinary peer preemption.
     * This is CPU work only; the callback makes no scheduling or I/O call. */
    while ((UWORD)(DisplayTicks()-start)<2) { }
    mappedTicks+=(UWORD)(DisplayTicks()-start);
    ++mappedCallbacks;
}

void MappedScratchCases(struct VbxeDisplay *d)
{
    UWORD block,i;
    ULONG base;
    for (pageIndex=0;pageIndex<4;++pageIndex) {
        base=DESKTOP_RASTER_SCRATCH_BASE+((ULONG)pageIndex<<12);
        for (i=0;i<256;++i) bytes[i]=(UBYTE)(i+pageIndex*37);
        for (block=0;block<16;++block)
            check(VbxeWrite(d,base+((ULONG)block<<8),bytes,256)==DISPLAY_OK);
        check(VbxeOwnerMapPage(d,base,modify,&pageIndex)==DISPLAY_OK);
        check(*(volatile UBYTE *)0xd65eUL==0);
        for (block=0;block<16;++block) {
            check(VbxeRead(d,base+((ULONG)block<<8),bytes,256)==DISPLAY_OK);
            for (i=0;i<256;++i) check(bytes[i]==(UBYTE)((i+pageIndex*37)^0x5a));
        }
    }
    check(mappedCallbacks==4);
    check(mappedTicks>=8);
}
