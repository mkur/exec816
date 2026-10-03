/* Shared drawing library without the GEM service/client or cursor objects. */
#include "gem-drawing.h"
#include <exec/input.h>
#include <proto/exec.h>
#include <string.h>
volatile UWORD stage,checkpoint,gate,failures,checks,finished;
WORD workout[57];
static struct InputLease mouse __attribute__((aligned(2)));
static struct InputConfig config __attribute__((aligned(2)));
static const UBYTE text[]="AB W 09";
static void check(UWORD good) { ++checks; if (!good) ++failures; }
UWORD main(void)
{
    WORD bit;
    UWORD pen;
    if (!stage) return 0;
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    check(GemDrawingFill(0,0,640,240,5)==DISPLAY_OK);
    for (pen=0;pen<16;pen++)
        check(GemDrawingText(32+(pen&1),8+pen*9,text,7,pen,5)==DISPLAY_OK);
    bit=AllocSignal(-1); check(bit>=16);
    memset(&config,0,sizeof(config));
    config.version=INPUT_VERSION; config.source=INPUT_SOURCE_POINTER;
    config.wakeMask=1UL<<bit; config.pointerProtocol=INPUT_POINTER_ST;
    config.pointerPort=1; config.maxX=639; config.maxY=239;
    check(InputAcquire(&mouse,&config)==INPUT_OK);
    checkpoint=1;
    while (!gate) { }
    check(InputRelease(&mouse)==INPUT_OK);
    FreeSignal(bit);
    check(GemDrawingClose()==DISPLAY_OK);
    finished=1;
    return failures;
}
