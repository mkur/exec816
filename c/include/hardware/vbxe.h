#ifndef EXEC_VBXE_H
#define EXEC_VBXE_H
#include <exec/display.h>
#include <hardware/vbxe-copy.h>

#define VBXE_VRAM_BYTES 0x80000UL
#define VBXE_SCREEN 0UL
#define VBXE_SCREEN_BYTES 76800UL
#define VBXE_XDL 0x30000UL
#define VBXE_BCB 0x38000UL
#define VBXE_BCB_BYTES 4096
#define VBXE_RECORD_BYTES 21
#define VBXE_LIST_RECORDS 64
#define VBXE_LIST_WORK 8192UL
#define VBXE_CHUNK_ROWS 16
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
/* Packed 21-byte CPU records, immutable until return. X steps +/-1,
 * canonical signed 13-bit Y steps -4096..4095;
 * chain, pattern, zoom and collision fields must be zero. The driver owns
 * chaining and rejects a whole list before changing VRAM. Empty lists are OK.
 * Work counts source/destination bus accesses (2 for copy, 3 for other modes).
 * The command arena cannot be a raster source or destination. */
UWORD VbxeSubmit(struct VbxeDisplay *display, const UBYTE *records, UWORD count);
UWORD VbxeBlitExtent(ULONG address, UWORD stride, UWORD bytes, UWORD rows);
UWORD VbxeCopyRect(struct VbxeDisplay *display, const struct VbxeCopy *copy);
/* Positive row steps, no chaining or IRQ. Every call completes before return. */
UWORD VbxeBlit(struct VbxeDisplay *display, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode);
UWORD VbxePalette(struct VbxeDisplay *display, const UBYTE *rgb);
UWORD VbxeShow(struct VbxeDisplay *display);
UWORD VbxeWaitFrame(struct VbxeDisplay *display);
#endif
