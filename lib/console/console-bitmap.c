/* The console worker is the sole caller. No client IPC or GUI Task is linked. */
#include <hardware/console-bitmap.h>
#include "gem-drawing.h"
struct ConsoleBitmapPacket ConsoleBitmapPacket __attribute__((aligned(2)));
static WORD workout[57];
void ConsoleBitmapEntry(void)
{
    struct ConsoleBitmapPacket *p=&ConsoleBitmapPacket;
    switch (p->operation) {
    case CON_BITMAP_OPEN: p->status=GemDrawingOpen(workout); break;
    case CON_BITMAP_CLOSE: p->status=GemDrawingClose(); break;
    case CON_BITMAP_TEXT:
        p->status=GemDrawingText(p->x,p->y,(const UBYTE *)p->text,p->width,
                                p->foreground,p->background); break;
    case CON_BITMAP_FILL:
        if (p->x>640 || p->y>240 || p->width>640-p->x || p->height>240-p->y)
            p->status=DISPLAY_BAD_ARGUMENT;
        else p->status=GemDrawingFill(p->x,p->y,p->x+p->width,p->y+p->height,p->background);
        break;
    case CON_BITMAP_COPY: p->status=GemDrawingCopy(&p->copy); break;
    case CON_BITMAP_FENCE: p->status=GemDrawingFence(); break;
    default: p->status=DISPLAY_BAD_ARGUMENT;
    }
}
int main(void) { return 0; }
