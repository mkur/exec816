/* Focused atlas lifetime and frame raster probe, without an AES server. */
#include "gem-drawing.h"
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include <string.h>
volatile UWORD stage,checkpoint,gate,checks,failures,finished;
extern UWORD FrameAtlasMemory(UWORD);
extern UWORD FrameAtlasFail;
extern UWORD DesktopFrame(struct ConsoleBitmapPacket *);
static WORD workout[57];
static void check(UWORD good) { ++checks;if (!good) ++failures; }

UWORD FrameRun(void)
{
    if (!stage) return 0;
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(1));
    check(GemDrawingClose()==DISPLAY_OK);
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(0));
    check(GemDrawingClose()==DISPLAY_OK);
    FrameAtlasFail=1;
    check(GemDrawingOpen(workout)==DISPLAY_DEVICE_FAULT);
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(0));
    check(GemDrawingClose()==DISPLAY_OK);
    finished=1;
    return failures;
}
