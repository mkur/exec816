/* Shared ordinary-call drawing entry points. No client IPC or cursor policy.
 * One owner/session per linked image. Calls return DISPLAY_* statuses.
 * Text has a top-left origin; rectangles have half-open bounds. */
#ifndef EXEC_GEM_DRAWING_H
#define EXEC_GEM_DRAWING_H
#include <hardware/vbxe.h>
UWORD GemDrawingOpen(WORD *workout);
UWORD GemDrawingClose(void);
UWORD GemDrawingCopy(const struct VbxeCopy *copy);
UWORD GemDrawingFence(void);
UWORD GemDrawingFill(UWORD left,UWORD top,UWORD right,UWORD bottom,UWORD pen);
UWORD GemDrawingText(UWORD x,UWORD y,const UBYTE *text,UWORD count,
                     UWORD foreground,UWORD background);
#endif
