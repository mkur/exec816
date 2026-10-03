/* Shared drawing library without the GEM service/client or cursor objects. */
#include "gem-drawing.h"
#include <exec/input.h>
#include <proto/exec.h>
#include <clib/alib_protos.h>
#include <string.h>
volatile UWORD stage,checkpoint,gate,failures,checks,finished;
volatile UWORD ownerChecks;
static volatile UWORD peerArm,peerDone,peerRetired;
static struct Task *peer;
static struct TaskLease peerLease;
WORD workout[57];
static struct InputLease mouse __attribute__((aligned(2)));
static struct InputConfig config __attribute__((aligned(2)));
static const UBYTE text[]="AB W 09";
static void check(UWORD good) { ++checks; if (!good) ++failures; }

/* Test-only pause after owner admission with queued glyph work. The owner
 * spins with IRQ/NMI enabled; VBI must preempt it so the foreign Task can run. */
void DrawingAdmissionProbe(void)
{
    if (!peerArm) return;
    peerArm=0;
    Signal(peer,1);
    while (!peerDone) { }
}
void DrawingPeer(void)
{
    Wait(1);
    check(GemDrawingFill(0,0,0,0,0)==DISPLAY_INVALID_OWNER);
    check(GemDrawingText(0,0,NULL,0,1,0)==DISPLAY_INVALID_OWNER);
    check(GemDrawingCopy(NULL)==DISPLAY_INVALID_OWNER);
    check(GemDrawingFence()==DISPLAY_INVALID_OWNER);
    check(GemDrawingClose()==DISPLAY_INVALID_OWNER);
    check(GemDrawingOpen(workout)==DISPLAY_BUSY);
    peerDone=1;
    Wait(1);
    Forbid();
    peerRetired=1;
    RemTask(NULL);
}
UWORD main(void)
{
    WORD bit;
    UWORD pen,before;
    if (!stage) return 0;
    Forbid();
    peer=CreateTask("drawing peer",0,DrawingPeer,2560);
    check(peer!=NULL && RetainTask(peer,&peerLease));
    Permit();
    check(GemDrawingOpen(workout)==DISPLAY_OK);
    before=ownerChecks;
    check(GemDrawingFill(0,0,640,240,5)==DISPLAY_OK);
    check((UWORD)(ownerChecks-before)==1);
    peerArm=1;
    for (pen=0;pen<16;pen++) {
        before=ownerChecks;
        check(GemDrawingText(32+(pen&1),8+pen*9,text,7,pen,5)==DISPLAY_OK);
        check((UWORD)(ownerChecks-before)==(pen ? 1 : 6));
    }
    check(peerDone);
    before=ownerChecks;
    check(GemDrawingCopy(NULL)==DISPLAY_BAD_ARGUMENT);
    check((UWORD)(ownerChecks-before)==1);
    before=ownerChecks;
    check(GemDrawingFill(0,0,0,0,0)==DISPLAY_OK);
    check((UWORD)(ownerChecks-before)==1);
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
    Forbid();
    check(ReleaseTask(&peerLease));
    Signal(peer,1);
    Permit();
    while (!peerRetired) { }
    finished=1;
    return failures;
}
