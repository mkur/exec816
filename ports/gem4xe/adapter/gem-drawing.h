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
UWORD GemDrawingScrollPoll(ULONG id);
ULONG GemDrawingCompletionMask(void);
UWORD GemDrawingFence(void);
UWORD GemDrawingFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen);
UWORD GemDrawingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,
                     UWORD foreground,UWORD background);
/* Nonempty even-X text followed by a nonempty even-X/even-width screen fill.
 * Fill area is at most VBXE_TEXT_FILL_WORK pixels. Validate both before any
 * drawing; append the fill to the final bounded text list and fence it once. */
UWORD GemDrawingTextFill(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD foreground,UWORD background,UWORD fillX,UWORD fillY,
    UWORD fillWidth,UWORD fillHeight,UWORD fillPen);
/* Half-open pixel clipping; a cut glyph preserves pixels outside the clip. */
UWORD GemDrawingTextClip(UWORD x,UWORD y,const UBYTE *text,UWORD count,
    UWORD fg,UWORD bg,UWORD left,UWORD top,UWORD right,UWORD bottom);

#endif
