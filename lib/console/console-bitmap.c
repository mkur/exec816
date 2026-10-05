/* The console worker is the sole caller. No client IPC or GUI Task is linked. */
#include <hardware/console-bitmap.h>
#include "gem-drawing.h"
struct ConsoleBitmapPacket ConsoleBitmapPacket __attribute__((aligned(2)));
static WORD workout[57];
void ConsoleBitmapEntry(void)
{
    struct ConsoleBitmapPacket *p=&ConsoleBitmapPacket;
    switch (p->operation) {
    case CON_BITMAP_OUTLINE:
        p->status=GemDrawingOutline(p->x,p->y,p->x+p->width,p->y+p->height,p->foreground); break;
    case CON_BITMAP_POINTER:
        p->status=GemDrawingPointer(p->x,p->y,p->width); break;
    case CON_BITMAP_OPEN:
        p->completionMask=0;
        p->status=GemDrawingOpen(workout);
        if (p->status==DISPLAY_OK) p->completionMask=GemDrawingCompletionMask();
        break;
    case CON_BITMAP_CLOSE: p->status=GemDrawingClose(); break;
    case CON_BITMAP_TEXT:
        p->status=GemDrawingText(p->x,p->y,(const UBYTE *)p->text,p->width,
                                p->foreground,p->background); break;
    case CON_BITMAP_TEXT_CLIP:
        p->status=GemDrawingTextClip(p->x,p->y,(const UBYTE *)p->text,p->width,
            p->foreground,p->background,p->clipLeft,p->clipTop,p->clipRight,p->clipBottom);
        break;
    case CON_BITMAP_TEXT_FILL:
        p->status=GemDrawingTextFill(p->x,p->y,(const UBYTE *)p->text,p->width,
            p->foreground,p->background,p->fillX,p->fillY,p->fillWidth,
            p->fillHeight,p->fillPen); break;
    case CON_BITMAP_FILL:
        if (p->x>640 || p->y>240 || p->width>640-p->x || p->height>240-p->y)
            p->status=DISPLAY_BAD_ARGUMENT;
        else p->status=GemDrawingFill(p->x,p->y,p->x+p->width,p->y+p->height,p->background);
        break;
    case CON_BITMAP_COPY: p->status=GemDrawingCopy(&p->copy); break;
    case CON_BITMAP_SCROLL:
        p->status=GemDrawingScrollStart(&p->copy,p->background,&p->token); break;
    case CON_BITMAP_COPY_START: p->status=GemDrawingCopyStart(&p->copy,&p->token); break;
    case CON_BITMAP_POLL: p->status=GemDrawingPoll(p->token); break;
    case CON_BITMAP_FENCE: p->status=GemDrawingFence(); break;
    default: p->status=DISPLAY_BAD_ARGUMENT;
    }
}
int main(void) { return 0; }
