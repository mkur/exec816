/* Private driver composition. Caller must have admitted this display owner
 * in the current synchronous invocation, or just acquired it successfully.
 * These helpers retain argument/list validation, dependencies and recovery.
 * Never retain admission across a return, callback, Yield or Wait. */
#ifndef EXEC_VBXE_INTERNAL_H
#define EXEC_VBXE_INTERNAL_H
#include <hardware/vbxe.h>
UWORD VbxeOwnerFence(struct VbxeDisplay *display);
UWORD VbxeOwnerClose(struct VbxeDisplay *display);
UWORD VbxeOwnerWrite(struct VbxeDisplay *display, ULONG address, const void *source, UWORD bytes);
UWORD VbxeOwnerRead(struct VbxeDisplay *display, ULONG address, void *destination, UWORD bytes);
UWORD VbxeOwnerSubmit(struct VbxeDisplay *display, const UBYTE *records, UWORD count);
/* Opaque even-X 8x8 text from a 256-glyph mask atlas, stride 1024. Validates
 * the whole run before generating bounded lists in the private command arena. */
UWORD VbxeOwnerText(struct VbxeDisplay *display, ULONG font, UWORD x, UWORD y,
                    const UBYTE *text, UWORD count, UBYTE ink, UBYTE paper);
UWORD VbxeOwnerFill(struct VbxeDisplay *display, ULONG address, UWORD stride, UWORD bytes, UWORD rows, UBYTE value);
UWORD VbxeOwnerCopyRect(struct VbxeDisplay *display, const struct VbxeCopy *copy);
UWORD VbxeOwnerScrollStart(struct VbxeDisplay *display, const struct VbxeCopy *copy,
                           UBYTE value, ULONG *id);
UWORD VbxeOwnerScrollPoll(struct VbxeDisplay *display, ULONG id);
UWORD VbxeOwnerWaitFrame(struct VbxeDisplay *display);
UWORD VbxeOwnerShow(struct VbxeDisplay *display);
UWORD VbxeOwnerPalette(struct VbxeDisplay *display, const UBYTE *rgb);
UWORD VbxeOwnerPresent(struct VbxeDisplay *display);
UWORD VbxeOwnerBlit(struct VbxeDisplay *display, ULONG source, UWORD sourceStride,
               ULONG destination, UWORD destinationStride, UWORD bytes, UWORD rows,
               UBYTE andMask, UBYTE xorMask, UBYTE mode);
#endif
