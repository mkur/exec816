/* Shared ordinary-call drawing entry points. No client IPC or cursor policy.
 * One owner/session per linked image. Calls return DISPLAY_* statuses.
 * Text has a top-left origin; rectangles have half-open bounds. */
#ifndef EXEC_GEM_DRAWING_H
#define EXEC_GEM_DRAWING_H
#include <hardware/vbxe.h>
UWORD GemDrawingOpen(WORD *workout);
UWORD GemDrawingClose(void);
UWORD GemDrawingCopy(const struct VbxeCopy *copy);
/* One asynchronous screen scroll; pen is a GEM logical colour. The driver
 * geometry, ID, storage lifetime and Poll contracts are in hardware/vbxe.h. */
/* Copy upward by sourceY-destinationY (positive multiple of eight), then fill
 * the exposed strip. The copied descriptor and operation ID outlive the call. */
UWORD GemDrawingScrollStart(const struct VbxeCopy *copy,UWORD pen,ULONG *id);
UWORD GemDrawingCopyStart(const struct VbxeCopy *copy,ULONG *id);
UWORD GemDrawingPoll(ULONG id);
ULONG GemDrawingCompletionMask(void);
UWORD GemDrawingFence(void);
UWORD GemDrawingFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen);
UWORD GemDrawingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,
                     UWORD foreground,UWORD background);
/* Presenter-owned Shell bitmap, client-local coordinates. Internal producers
 * supply even X/width for fills within the fixed 512 by 160 surface. */
UWORD GemDrawingBackingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,UWORD fg,UWORD bg);
UWORD GemDrawingBackingFill(UWORD x,UWORD y,UWORD width,UWORD height,UWORD pen);
/* Nonempty text at either X parity followed by a nonempty even-X/even-width screen fill.
 * Fill area is at most VBXE_TEXT_FILL_WORK pixels. Validate both before any
 * drawing; append the fill to the final bounded text list and fence it once. */
UWORD GemDrawingTextFill(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD foreground,UWORD background,UWORD fillX,UWORD fillY,
    UWORD fillWidth,UWORD fillHeight,UWORD fillPen);
/* Half-open pixel clipping; a cut glyph preserves pixels outside the clip. */
UWORD GemDrawingTextClip(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD left,UWORD top,UWORD right,UWORD bottom);

/* Same owner; caller waits for its asynchronous drawing to retire first. */
UWORD GemDrawingOutline(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD visible);
UWORD GemDrawingPointer(UWORD x,UWORD y,UWORD visible);

/* Internal renderer closure: callback is linked trusted code, never a client
 * pointer. One owner check and fence cover the complete bounded paint quantum. */
UWORD GemDrawingBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,void (*draw)(void));
/* At most two disjoint, plain monochrome menu rows, each <=16 scanlines.
 * Coordinates are admitted by the presenter; exchange hardware white/black. */
UWORD GemDrawingInvertRows(const WORD *rectangles,UWORD count);
/* Widget-only strip buffer; first resets it, draw returns nonzero on completion.
 * The complete clipped strip replaces screen pixels only after the final chunk. */
UWORD GemDrawingWidgetBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                            UWORD first,UWORD (*draw)(void));
/* Private solid/atlas frame side, width <=16, height <=240. Uses the same
 * scratch allocation at a compact pitch and publishes once on completion. */
UWORD GemDrawingFrameBatch(UWORD left,UWORD top,UWORD right,UWORD bottom,
                           UWORD (*draw)(void));
void GemWidgetStipple(UWORD left,UWORD top,UWORD right,UWORD bottom);
/* Flat GEM pattern 2: black dots at odd window-relative X/Y, on white. */
void GemFramePattern(UWORD left,UWORD top,UWORD right,UWORD bottom,
                     UWORD originX,UWORD originY);
enum { GEM_GADGET_CLOSE,GEM_GADGET_FULL,GEM_GADGET_ICONIFY,GEM_GADGET_TILE,
       GEM_GADGET_UP,GEM_GADGET_DOWN,GEM_GADGET_SIZE };
/* Fixed opaque interior image. Caller owns the current frame batch/clip. */
void GemFrameGadget(UWORD image,WORD x,WORD y,UWORD left,UWORD top,
                    UWORD right,UWORD bottom);
/* One admitted synchronous unit, at most 32 rows. The callback is linked
 * renderer code, never a borrowed application function pointer. */
UWORD GemDrawingBorrow(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,void (*draw)(void *),void *context);
/* Solid replacement only: the caller splits visibility intersections at the
 * returned row capacity. These taller units share the ordinary borrow lifecycle. */
UWORD GemSolidRows(UWORD left,UWORD right);
UWORD GemDrawingSolidBorrow(struct DisplayGrant *grant,UWORD left,UWORD top,
    UWORD right,UWORD bottom,UWORD pen);
/* Trusted, nonempty screen/redirected-strip geometry; append to the current
 * batch and split at its existing work limit, without submitting each fill. */
void GemSolidFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen);
/* Native-word monochrome planes, word-aligned width <=64; visible strip <=32
 * rows. Caller holds the existing display grant; half-open clip is on screen. */
void GemIconBitmap(const UWORD *mask,const UWORD *data,UWORD width,
    WORD x,WORD y,UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD fg,UWORD bg);
void GemColourIconBitmap(const UWORD *mask,const UBYTE *data,UWORD width,UWORD height,
    WORD x,WORD y,UWORD left,UWORD top,UWORD right,UWORD bottom);
#endif
