#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks, AESFailures, AESFirstFailure;
volatile UWORD SceneVariant, ScenePhase, SceneGo, SceneHolderGo, SceneHeld;
volatile UWORD SceneHoldGo, SceneEffectArm, SceneEffectHeld, SceneEffectGo;
volatile UWORD SceneReady, SceneSeen, SceneSend, SceneSent, SceneStop;
volatile ULONG SceneHoldClient, ScenePeer;
volatile ULONG SceneWaiterTask;
volatile UWORD SceneWaiterGo;
ULONG SceneView;
static struct Task *parent;
static ULONG holderExit, peerExit,waiterExit;
static WORD recipient;

static void check(BOOL okay)
{
    Forbid();
    ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t)!=0)

void SceneHolder(void)
{
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    SceneHoldClient=ExecAESContext()->identity;
    Forbid(); ++SceneReady; Permit();
    while (!SceneHolderGo) ExecYield();
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_update(END_UPDATE));
    CHECK(ExecAESDetach());
    Forbid(); Signal(parent,holderExit); RemTask(NULL);
}

void SceneWorker(void)
{
    WORD message[8]={777,0,0,0,0,0,0,0};
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    Forbid(); ++SceneReady; Permit();
    while (!SceneStop) {
        ++ScenePeer;
        if (SceneSend && !SceneSent) {
            CHECK(appl_write(recipient,16,message));
            SceneSent=1;
        }
    }
    CHECK(ExecAESDetach());
    Forbid(); Signal(parent,peerExit); RemTask(NULL);
}

void SceneWaiter(void)
{
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    SceneWaiterTask=(ULONG)FindTask(NULL);
    Forbid(); ++SceneReady; Permit();
    while (!SceneWaiterGo) ExecYield();
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_update(END_UPDATE));
    CHECK(ExecAESDetach());
    Forbid(); Signal(parent,waiterExit); RemTask(NULL);
}

static void phase(UWORD value)
{
    ScenePhase=value;
    while (SceneGo<value) ExecYield();
}

UWORD AESRun(void)
{
    WORD input[11]={1,1,1,1,1,1,1,1,1,1,2},output[57];
    WORD window,vdi=1,message[8],rect[4],x,y,w,h,mx,my,buttons,mods,key,clicks,flags,wanted;
    ULONG available=AvailMem(0);
    BYTE holderBit,peerBit,waiterBit;

    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    recipient=appl_init(); CHECK(recipient>0);
    window=wind_create(AES_WINDOW_KIND|SIZER,32,32,200,120);
    CHECK(window>0 && wind_open(window,32,32,200,120));
    do { CHECK(evnt_mesag(message)); } while (message[0]!=WM_REDRAW);
    SceneView=(ULONG)ExecAESContext()->view;
    v_opnvwk(input,&vdi,output); CHECK(vdi>0);
    CHECK(ExecAESBeginUpdate(window));
    CHECK(wind_get(window,WF_WORKXYWH,&x,&y,&w,&h));
    rect[0]=x;rect[1]=y;rect[2]=x+w-1;rect[3]=y+h-1;
    vs_clip(vdi,1,rect);vsf_color(vdi,3);v_bar(vdi,rect);
    CHECK(ExecAESPainted(window,x,y,w,h));
    CHECK(wind_update(END_UPDATE));
    parent=FindTask(NULL);
    holderBit=AllocSignal(-1); peerBit=AllocSignal(-1);waiterBit=AllocSignal(-1);
    CHECK(holderBit>=0 && peerBit>=0 && waiterBit>=0);
    holderExit=1UL<<holderBit;peerExit=1UL<<peerBit;
    waiterExit=1UL<<waiterBit;
    CHECK(CreateTask("Scene holder",0,(APTR)SceneHolder,2048)!=NULL);
    CHECK(CreateTask("Scene peer",0,(APTR)SceneWorker,1024)!=NULL);
    CHECK(CreateTask("Scene waiter",0,(APTR)SceneWaiter,1024)!=NULL);
    while (SceneReady!=3) ExecYield();
    phase(1);
    if (!SceneVariant) {
        SceneHolderGo=1;
        while (!SceneHeld) ExecYield();
        ScenePhase=2;
        SceneSend=1;
        while (SceneSeen!=(MU_KEYBD|MU_BUTTON|MU_TIMER|MU_MESAG)) {
            wanted=(MU_KEYBD|MU_BUTTON|MU_TIMER|MU_MESAG)&~SceneSeen;
            flags=evnt_multi(wanted,
                1,1,1,0,0,0,0,0,0,0,0,0,0,message,50,0,
                &mx,&my,&buttons,&mods,&key,&clicks);
            CHECK(flags>0);
            if (flags&MU_KEYBD) {
                CHECK(key==0x1e61); SceneSeen|=MU_KEYBD;
            }
            if (flags&MU_BUTTON) {
                CHECK(buttons==1 && clicks==1); SceneSeen|=MU_BUTTON;
            }
            if (flags&MU_TIMER) SceneSeen|=MU_TIMER;
            if ((flags&MU_MESAG) && message[0]==777) SceneSeen|=MU_MESAG;
        }
        phase(3);
    } else if (SceneVariant==1) {
        SceneEffectArm=1;
        ScenePhase=2;
        CHECK(wind_set(window,WF_CURRXYWH,64,48,200,120));
        CHECK(ExecAESContext()->view->bounds.left==64);
        CHECK(ExecAESContext()->view->bounds.top==48);
        phase(3);
    } else {
        SceneEffectArm=1;
        ScenePhase=2;
        while (!SceneEffectHeld) ExecYield();
        while (!SceneHoldGo) ExecYield();
        phase(3);
    }
    Wait(holderExit);
    Wait(waiterExit);
    SceneStop=1;Wait(peerExit);
    FreeSignal(holderBit);FreeSignal(peerBit);FreeSignal(waiterBit);
    CHECK(wind_close(window));CHECK(wind_delete(window));
    v_clsvwk(vdi);
    CHECK(ExecAESDetach());
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
