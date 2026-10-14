/* Focused atlas lifetime and frame raster probe, without an AES server. */
#include "gem-drawing.h"
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include <string.h>
volatile UWORD stage,checkpoint,gate,checks,failures,finished,firstFailure,frameStatus;
extern UWORD FrameAtlasMemory(UWORD);
extern UWORD FrameAtlasFail;
extern UWORD DesktopFrame(struct ConsoleBitmapPacket *);
static WORD workout[57];
static void check(UWORD good) { ++checks;if (!good) { ++failures;if (!firstFailure) firstFailure=checks; } }
static void title(UWORD number)
{
    struct ConsoleBitmapPacket p;
    memset(&p,0,sizeof(p));
    p.x=number==2 ? 21:20;p.y=20;p.width=200;p.height=180;
    p.text=(ULONG)(number==4 ? "Shell":"SYS:");
    p.foreground=number!=2;p.background=number!=4;
    p.fillY=number==5 ? DESKTOP_FRAME_ICONIFIED:DESKTOP_FRAME_FULLER;
    if (number==5) { p.width=88;p.height=11; }
    p.clipLeft=number==2 ? 21:20;p.clipTop=20;
    p.clipRight=number==5 ? 108:number==2 ? 221:220;p.clipBottom=31;
    if (number==3) { p.clipLeft+=7;p.clipTop+=1;p.clipRight-=10; }
    check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
    do { frameStatus=DesktopFrame(&p);check(frameStatus==DISPLAY_OK); } while (p.fillX);
}

UWORD FrameRun(void)
{
    UWORD number;
    if (!stage) return 0;
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(1));
    check(GemDrawingClose()==DISPLAY_OK);
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(0));
    for (number=1;number<=5;++number) {
        title(number);
        checkpoint=number;
        while (gate<number) { }
    }
    check(GemDrawingClose()==DISPLAY_OK);
    FrameAtlasFail=1;
    check(GemDrawingOpen(workout)==DISPLAY_DEVICE_FAULT);
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(FrameAtlasMemory(0));
    check(GemDrawingClose()==DISPLAY_OK);
    finished=1;
    return failures;
}
