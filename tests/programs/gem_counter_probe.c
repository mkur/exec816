#include "../../examples/gem-counter/counter.h"
#include <exec816/runtime.h>
#include <proto/exec.h>
extern struct Counter GEMCounters[2];
volatile UWORD CounterPause[2],CounterHeld[2],CounterEvents[2],CounterBoth[2];
volatile UWORD CounterMessages[2][4];
void CounterBeforeWait(struct Counter *app)
{
    UWORD who=app==GEMCounters ? 0:1;
    while (CounterPause[who]) { CounterHeld[who]=1; ExecYield(); }
    CounterHeld[who]=0;
}
extern void CounterNoticeOne(void),CounterNoticeTwo(void);
void CounterObserved(struct Counter *app,WORD events)
{
    UWORD who=app==GEMCounters ? 0:1;
    ++CounterEvents[who];
    if ((events & (MU_MESAG|MU_TIMER))==(MU_MESAG|MU_TIMER)) ++CounterBoth[who];
    if (events & MU_MESAG) {
        if (who) CounterNoticeTwo(); else CounterNoticeOne();
        switch (app->message[0]) {
        case WM_REDRAW: ++CounterMessages[who][0]; break;
        case WM_TOPPED: ++CounterMessages[who][1]; break;
        case WM_MOVED: ++CounterMessages[who][2]; break;
        case WM_CLOSED: ++CounterMessages[who][3]; break;
        }
    }
}

#include <exec816/aes.h>
#include <clib/alib_protos.h>
extern UWORD GEMCountersStart(void),GEMCountersStop(void);
volatile UWORD CounterTimerPause[2],CounterTimerHeld[2];
volatile UWORD CounterPostCommand,CounterPostDone,CounterPostStatus;
WORD CounterPostWords[8];
#define HOLD_COUNT 5
extern volatile UWORD GEMCountersDone;
static struct Task *holds[HOLD_COUNT];
static volatile UWORD holdDone,holdReady;
static ULONG holdMasks[HOLD_COUNT];
void CounterEventWait(struct ExecAESContext *c)
{
    UWORD who=c->gemId==GEMCounters[0].id ? 0:1;
    while (CounterTimerPause[who]) { CounterTimerHeld[who]=1; ExecYield(); }
    CounterTimerHeld[who]=0;
}
UWORD CounterPost(void)
{
    UWORD who;
    if (!CounterPostCommand) return 1;
    who=CounterPostCommand-1;
    CounterPostWords[3]=GEMCounters[who].window;
    CounterPostStatus=appl_write(GEMCounters[who].id,16,CounterPostWords);
    CounterPostCommand=0; ++CounterPostDone;
    return CounterPostStatus;
}
void CounterHold(void)
{
    UWORD i;
    BYTE signal=AllocSignal(-1);
    for (i=0;i<HOLD_COUNT && holds[i]!=FindTask(NULL);++i) {}
    holdMasks[i]=1UL<<signal;
    Forbid(); ++holdReady; Permit();
    Wait(holdMasks[i]); FreeSignal(signal);
    Forbid(); ++holdDone; RemTask(NULL);
}
UWORD CounterCapacity(void)
{
    UWORD i,okay;
    ULONG available=AvailMem(0);
    holdDone=holdReady=0;
    Forbid();
    for (i=0;i<HOLD_COUNT;++i) {
        holds[i]=CreateTask("Admission reserve",1,(APTR)CounterHold,1024UL);
        if (!holds[i]) { Permit(); return 0; }
    }
    Permit();
    while (holdReady!=HOLD_COUNT) ExecYield();
    okay=!GEMCountersStart() && GEMCountersDone==1;
    for (i=0;i<HOLD_COUNT;++i) Signal(holds[i],holdMasks[i]);
    while (holdDone!=HOLD_COUNT) ExecYield();
    return okay && AvailMem(0)==available;
}

volatile UWORD CounterMark;
void CounterUpdateBegin(void) { CounterMark=1; }
void CounterUpdateOwned(void) { CounterMark=2; }
void CounterPaintDone(void) { CounterMark=3; }
void CounterUpdateEnd(void) { CounterMark=4; }
