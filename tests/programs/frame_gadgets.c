/* Focused atlas lifetime and frame raster probe, without an AES server. */
#include "gem-drawing.h"
#include <hardware/console-bitmap.h>
#include <exec816/desktop-geometry.h>
#include <string.h>
volatile UWORD stage,checkpoint,gate,checks,failures,finished,firstFailure,frameStatus;
extern UWORD FrameAtlasMemory(UWORD);
extern UWORD FrameScratchGuard(UWORD);
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
static void whole_frame(UWORD number)
{
    struct ConsoleBitmapPacket p;
    UWORD n;
    static const UWORD even[4][4]={{20,20,220,31},{20,189,220,200},{20,31,28,189},{204,31,220,189}};
    static const UWORD odd[4][4]={{21,0,221,11},{21,229,221,240},{21,11,29,229},{205,11,221,229}};
    const UWORD (*clips)[4]=number==6 ? even:odd;
    memset(&p,0,sizeof(p));
    p.x=number==6 ? 20:21;p.y=number==6 ? 20:0;
    p.width=200;p.height=number==6 ? 180:240;p.text=(ULONG)"SYS:";
    p.foreground=p.background=1;
    p.fillY=DESKTOP_FRAME_FULLER|DESKTOP_FRAME_VERTICAL|DESKTOP_FRAME_SIZER;
    p.fillWidth=number==6 ? 140:22;p.fillHeight=number==6 ? 18:8;
    check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
    for (n=0;n<4;++n) {
        p.clipLeft=clips[n][0];p.clipTop=clips[n][1];p.clipRight=clips[n][2];p.clipBottom=clips[n][3];
        do { frameStatus=DesktopFrame(&p);check(frameStatus==DISPLAY_OK); } while (p.fillX);
    }
}
static UWORD tall(void)
{
    GemSolidFill(27,0,43,240,0);
    GemFrameGadget(GEM_GADGET_SIZE,29,234,27,0,43,240);
    return 1;
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
    for (number=1;number<=9;++number) {
        if (number==6 || number==7) whole_frame(number);
        else if (number==8) {
            check(GemDrawingFill(0,0,640,240,3)==DISPLAY_OK);
            check(FrameScratchGuard(1));
            check(GemDrawingFrameBatch(27,0,43,240,tall)==DISPLAY_OK);
            check(FrameScratchGuard(0));
        } else title(number==9 ? 1:number);
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
