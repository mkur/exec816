#ifndef EXEC_VBXE_H
#define EXEC_VBXE_H
#include <exec/display.h>

#define VBXE_VRAM_BYTES 0x80000UL
#define VBXE_SCREEN 0UL
#define VBXE_SCREEN_BYTES 76800UL
#define VBXE_XDL 0x30000UL
#define VBXE_BCB 0x30100UL
#define VBXE_BCB_BYTES 252
#define VBXE_WAIT_TICKS 16

struct VbxeMapState { UBYTE pendingBank, pendingControl, bank, control; };
/* Zero once before use. Opaque, address-stable, upper CPU RAM, never VRAM. */
struct VbxeDisplay {
    struct DisplayLease lease;
    struct VbxeMapState map;
    UWORD savedList;
    UBYTE savedDma, mutated;
    UBYTE video, xdl[3], blit[3], irq, palette, color;
    UWORD lastError;
};
UWORD VbxeOpen(struct VbxeDisplay *display);
UWORD VbxeFence(struct VbxeDisplay *display);
UWORD VbxeClose(struct VbxeDisplay *display);
UWORD VbxeWrite(struct VbxeDisplay *display, ULONG address, const void *source, UWORD bytes);
UWORD VbxeRead(struct VbxeDisplay *display, ULONG address, void *destination, UWORD bytes);
UWORD VbxeFill(struct VbxeDisplay *display, ULONG address, UWORD stride, UWORD bytes, UWORD rows, UBYTE value);
UWORD VbxePresent(struct VbxeDisplay *display);
/* Positive row steps, no chaining or IRQ. Every call completes before return. */
UWORD VbxeBlit(struct VbxeDisplay *display, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode);
UWORD VbxePalette(struct VbxeDisplay *display, const UBYTE *rgb);
UWORD VbxeShow(struct VbxeDisplay *display);
UWORD VbxeWaitFrame(struct VbxeDisplay *display);
#endif
