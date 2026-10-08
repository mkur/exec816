/* Private driver composition. Caller must have admitted this display owner
 * in the current synchronous invocation, or just acquired it successfully.
 * These helpers retain dependencies and recovery. Argument validation is
 * operation-specific; prepared Submit lists are an internal producer contract.
 * Admission covers trusted synchronous renderer callbacks only; never retain
 * it across a public return, independent callback, Yield or Wait. */
#ifndef EXEC_VBXE_INTERNAL_H
#define EXEC_VBXE_INTERNAL_H
#include <hardware/vbxe.h>
UWORD VbxeOwnerFence(struct VbxeDisplay *display);
UWORD VbxeOwnerClose(struct VbxeDisplay *display);
UWORD VbxeOwnerWrite(struct VbxeDisplay *display, ULONG address, const void *source, UWORD bytes);
UWORD VbxeOwnerRead(struct VbxeDisplay *display, ULONG address, void *destination, UWORD bytes);
/* Prepared CPU records only: stable through return, outside the aperture,
 * count <= VBXE_LIST_RECORDS and work <= VBXE_LIST_WORK. The internal producer
 * establishes legal fields/extents, excludes the command arena from raster
 * addresses and bounds every list while constructing it. No record validation
 * occurs here. Zero count is a no-op; nonempty lists retain both fences and
 * timeout recovery. Caller-supplied raw records must use public VbxeSubmit. */
UWORD VbxeOwnerSubmit(struct VbxeDisplay *display, const UBYTE *records, UWORD count);
/* Opaque even-X 8x8 text from a 256-glyph mask atlas, stride 1024. Validates
 * the whole run before generating bounded lists in the private command arena. */
UWORD VbxeOwnerText(struct VbxeDisplay *display, ULONG font, UWORD x, UWORD y,
                    const UBYTE *text, UWORD count, UBYTE ink, UBYTE paper);
struct VbxeTextFill { UWORD x,y,width,height; UBYTE value; };
UWORD VbxeOwnerTextFill(struct VbxeDisplay *display, ULONG font,UWORD x,UWORD y,
    const UBYTE *text,UWORD count,UBYTE ink,UBYTE paper,
    const struct VbxeTextFill *fill);
UWORD VbxeOwnerFill(struct VbxeDisplay *display, ULONG address, UWORD stride, UWORD bytes, UWORD rows, UBYTE value);
UWORD VbxeOwnerCopyRect(struct VbxeDisplay *display, const struct VbxeCopy *copy);
/* One overlap-safe, even-pixel copy, at most 640x240. OK with *id=0 is
 * empty/identical; otherwise use the common Poll/CompletionMask. BUSY leaves
 * the active list and new output unchanged. Accepted descriptors are copied. */
UWORD VbxeOwnerCopyStart(struct VbxeDisplay *display, const struct VbxeCopy *copy, ULONG *id);
UWORD VbxeOwnerScrollStart(struct VbxeDisplay *display, const struct VbxeCopy *copy,
                           UBYTE value, ULONG *id);
UWORD VbxeOwnerPoll(struct VbxeDisplay *display, ULONG id);
UWORD VbxeOwnerWaitFrame(struct VbxeDisplay *display);
UWORD VbxeOwnerShow(struct VbxeDisplay *display);
UWORD VbxeOwnerPalette(struct VbxeDisplay *display, const UBYTE *rgb);
UWORD VbxeOwnerPresent(struct VbxeDisplay *display);
UWORD VbxeOwnerBlit(struct VbxeDisplay *display, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode);
#endif
