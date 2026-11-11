#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure;
volatile UWORD EffectPhase, EffectGo, EffectVariant;
volatile ULONG EffectPeer;
ULONG EffectView;
volatile UWORD EffectQueryArm,EffectQueryDone;
volatile WORD EffectQueryResult,EffectQueryStatus;
static volatile UWORD peerDone,peerReady;
static struct Task *caller;
static ULONG peerMask;
extern volatile UWORD ConsoleFaultMode, ConsoleCopyChunks;

#define CHECK(t) do { ++AESChecks; if (!(t)) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; } } while (0)

void EffectWorker(void)
{
    WORD attached=ExecAESAttach((struct MsgPort *)AESService) && appl_init()>0;
    peerReady=attached ? 1 : 2;
    while (!peerDone) {
        ++EffectPeer;
        if (EffectQueryArm && !EffectQueryDone) {
            EffectQueryResult=wind_find(40,40);
            EffectQueryStatus=ExecAESDiagnostic();
            EffectQueryDone=1;
        }
    }
    if (attached) ExecAESDetach();
    Forbid();
    Signal(caller,peerMask);
    RemTask(NULL);
}

static void phase(UWORD number)
{
    EffectPhase=number;
    while (EffectGo<number) ExecYield();
}

UWORD AESRun(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2}, output[57];
    WORD window, vdi=1, message[8], rect[4], x,y,w,h;
    ULONG available=AvailMem(0), epoch;
    struct AESWindowView *view;
    BYTE bit;

    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    window=wind_create(AES_WINDOW_KIND|SIZER,32,32,160,96);
    CHECK(window>0);
    view=ExecAESContext()->view;
    EffectView=(ULONG)view;
    phase(1);
    CHECK(!wind_open(window,32,32,160,96));
    CHECK(ExecAESDiagnostic()==AES_OVERFLOW);
    CHECK(!view->shown && !view->epoch);
    phase(2);
    CHECK(wind_open(window,32,32,160,96));
    do { CHECK(evnt_mesag(message)); } while (message[0]!=WM_REDRAW);
    v_opnvwk(input,&vdi,output); CHECK(vdi>0);
    CHECK(ExecAESBeginUpdate(window));
    CHECK(wind_get(window,WF_WORKXYWH,&x,&y,&w,&h));
    rect[0]=x;rect[1]=y;rect[2]=x+w-1;rect[3]=y+h-1;
    vs_clip(vdi,1,rect);vsf_color(vdi,3);v_bar(vdi,rect);
    CHECK(ExecAESDiagnostic()==AES_OK);
    CHECK(ExecAESPainted(window,x,y,w,h));
    CHECK(wind_update(END_UPDATE));
    caller=FindTask(NULL);
    bit=AllocSignal(-1); CHECK(bit>=0);
    peerMask=1UL<<bit;
    CHECK(CreateTask("Window effect peer",0,(APTR)EffectWorker,512)!=NULL);
    while (!peerReady) ExecYield();
    CHECK(peerReady==1);
    phase(3);
    epoch=view->paintEpoch;
    ConsoleCopyChunks=0;
    ConsoleFaultMode=EffectVariant;
    if (!EffectVariant) {
        CHECK(wind_set(window,WF_CURRXYWH,64,48,160,96));
        CHECK(view->bounds.left==64 && view->bounds.top==48);
        CHECK(view->paintEpoch!=epoch && view->pixelsReady);
        /* A mutation inside UPDATE invalidates the caller's rectangle walk. */
        CHECK(ExecAESBeginUpdate(window));
        CHECK(wind_get(window,WF_FIRSTXYWH,&x,&y,&w,&h));
        CHECK(wind_set(window,WF_CURRXYWH,64,48,168,104));
        CHECK(!wind_get(window,WF_NEXTXYWH,&x,&y,&w,&h));
        CHECK(ExecAESDiagnostic()==AES_BUSY);
        CHECK(wind_update(END_UPDATE));
    } else {
        CHECK(!wind_set(window,WF_CURRXYWH,64,48,160,96));
        CHECK(ExecAESDiagnostic()==AES_DISPLAY_ERROR);
        CHECK(view->bounds.left==32 && view->bounds.top==32);
        CHECK(view->paintEpoch!=epoch);
    }
    phase(4);
    CHECK(wind_close(window));
    peerDone=1;
    Wait(peerMask);
    FreeSignal(bit);
    CHECK(wind_delete(window));
    v_clsvwk(vdi);
    CHECK(ExecAESDetach());
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
