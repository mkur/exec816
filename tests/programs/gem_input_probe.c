#include "../../examples/gem-input/input.h"
#include <exec816/runtime.h>
#include <proto/exec.h>
#include <exec/memory.h>
extern struct InputApp GEMInputs[2];
volatile UWORD InputPause[2],InputHeld[2],InputEvents[2],InputBoth[2];
volatile UWORD InputMessages[2][4];
void InputBeforeWait(struct InputApp *app)
{
    UWORD who=app==GEMInputs ? 0:1;
    while (InputPause[who]) { InputHeld[who]=1; ExecYield(); }
    InputHeld[who]=0;
}
void InputNoticeOne(void) {}
void InputNoticeTwo(void) {}
void InputObserved(struct InputApp *app,WORD events)
{
    UWORD who=app==GEMInputs ? 0:1;
    ++InputEvents[who];
    if ((events & (MU_MESAG|MU_TIMER))==(MU_MESAG|MU_TIMER)) ++InputBoth[who];
    if (events & MU_MESAG) {
        if (who) InputNoticeTwo(); else InputNoticeOne();
        switch (app->message[0]) {
        case WM_REDRAW: ++InputMessages[who][0]; break;
        case WM_TOPPED: ++InputMessages[who][1]; break;
        case WM_MOVED: ++InputMessages[who][2]; break;
        case WM_CLOSED: ++InputMessages[who][3]; break;
        }
    }
}

#include <exec816/aes.h>
#include <clib/alib_protos.h>
extern UWORD GEMInputsStart(void),GEMInputsStop(void);
volatile UWORD InputTimerPause[2],InputTimerHeld[2];
volatile UWORD InputPostCommand,InputPostDone,InputPostStatus;
WORD InputPostWords[8];
#define HOLD_COUNT 5
extern volatile UWORD GEMInputsDone;
static struct Task *holds[HOLD_COUNT];
static volatile UWORD holdDone,holdReady;
static ULONG holdMasks[HOLD_COUNT];
void InputEventWait(struct ExecAESContext *c)
{
    UWORD who=c->gemId==GEMInputs[0].id ? 0:1;
    while (InputTimerPause[who]) { InputTimerHeld[who]=1; ExecYield(); }
    InputTimerHeld[who]=0;
}
UWORD InputPost(void)
{
    UWORD who;
    if (!InputPostCommand) return 1;
    who=InputPostCommand-1;
    InputPostWords[3]=GEMInputs[who].window;
    InputPostStatus=appl_write(GEMInputs[who].id,16,InputPostWords);
    InputPostCommand=0; ++InputPostDone;
    return InputPostStatus;
}
void InputHold(void)
{
    UWORD i;
    BYTE signal=AllocSignal(-1);
    for (i=0;i<HOLD_COUNT && holds[i]!=FindTask(NULL);++i) {}
    holdMasks[i]=1UL<<signal;
    Forbid(); ++holdReady; Permit();
    Wait(holdMasks[i]); FreeSignal(signal);
    Forbid(); ++holdDone; RemTask(NULL);
}
static UWORD out_of_memory(void)
{
    struct Block { struct Block *next; ULONG bytes; } *head=NULL,*block;
    static const ULONG sizes[3]={32768,1024,16};
    ULONG available=AvailMem(0),empty;
    UWORD i,okay;
    for (i=0;i<3;++i) while ((block=AllocMem(sizes[i],MEMF_PUBLIC))!=NULL) {
        block->bytes=sizes[i]; block->next=head; head=block;
    }
    empty=AvailMem(0);
    okay=!GEMInputsStart() && AvailMem(0)==empty;
    while (head) {
        ULONG bytes=head->bytes;
        block=head; head=head->next; FreeMem(block,bytes);
    }
    return okay && AvailMem(0)==available;
}

UWORD InputCapacity(void)
{
    UWORD i,okay;
    ULONG available=AvailMem(0);
    holdDone=holdReady=0;
    Forbid();
    for (i=0;i<HOLD_COUNT;++i) {
        holds[i]=CreateTask("Admission reserve",1,(APTR)InputHold,1024UL);
        if (!holds[i]) { Permit(); return 0; }
    }
    Permit();
    while (holdReady!=HOLD_COUNT) ExecYield();
    okay=!GEMInputsStart() && GEMInputsDone==1;
    for (i=0;i<HOLD_COUNT;++i) Signal(holds[i],holdMasks[i]);
    while (holdDone!=HOLD_COUNT) ExecYield();
    return okay && AvailMem(0)==available && out_of_memory();
}

volatile UWORD InputMark,InputPaintPause,InputPaintHeld;
void InputUpdateBegin(void) { InputMark=1; }
void InputUpdateOwned(void)
{
    InputMark=2;
    while (InputPaintPause) { InputPaintHeld=1; ExecYield(); }
    InputPaintHeld=0;
}
void InputPaintDone(void) { InputMark=3; }
void InputUpdateEnd(void) { InputMark=4; }
