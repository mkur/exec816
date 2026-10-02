/* One application owns input and GEM. Root is a disk supervisor only. All
 * control slots/ports have static upper-RAM storage, independent of the heap. */
#include "ui.h"
#include "ui-keymap.h"
#include "ui-events.h"
#include <clib/alib_protos.h>
#include <string.h>

#ifdef GEM_DIAGNOSTIC
extern volatile UWORD variant;
extern void UiProbe(UWORD point);
#define PROBE(point) UiProbe(point)
#else
#define PROBE(point) ((void)0)
#endif

struct UiBoot boot __attribute__((aligned(2)));
struct GemServer server;
struct GemClient client;
struct InputLease input __attribute__((aligned(2)));
static struct InputConfig config __attribute__((aligned(2)));
static struct InputEvent event __attribute__((aligned(2)));
static struct TaskLease selfLease, rootLease;
static struct MsgPort rootPort, rootReplies, appPort, exitReplies;
static struct UiControl control __attribute__((aligned(2)));
static struct UiControl progressMessage __attribute__((aligned(2)));
static struct UiControl diskMessage __attribute__((aligned(2)));
static struct UiControl exitMessage __attribute__((aligned(2)));
static UWORD outstanding, progressWanted, exitSent;
static struct UiControl *startMessage, *exitNotice;
static ULONG generation;
static ULONG route __attribute__((aligned(2)));
static BYTE rootBit=-1, appBit=-1, inputBit=-1;
static UWORD inputPending __attribute__((aligned(2)));
static UWORD caps, lastValid, lastCode, lastTick;
volatile UWORD stage, rootValue, finished, failures, firstFailure, checks;
volatile UWORD focus, count, length, diskProgress, dirty, initialReady;
volatile UWORD received, submitted, collected, inputWhilePending, lastCapture, lastConsume;
volatile UWORD lastSubmit, lastComplete, maxCommands, maxGlyphs;
UBYTE text[25];
static UWORD renderTile, cursorTurn;
volatile WORD pointerX, pointerY, armed=-1;
volatile UWORD pointerVisible, pointerDirty, pointerReady=1, pointerButtons;
volatile UWORD pointerEvents, pointerActivations, inputLosses, cursorPackets;

static void check(UWORD good)
{
    ++checks;
    if (!good) { if (!failures) firstFailure=checks; ++failures; }
}
static ULONG mask(struct MsgPort *p) { return 1UL<<p->mp_SigBit; }
static void port(struct MsgPort *p, UBYTE bit)
{
    memset(p,0,sizeof(*p));
    NewList(&p->mp_MsgList);
    p->mp_Node.ln_Type=NT_MSGPORT;
    p->mp_Flags=PA_SIGNAL;
    p->mp_SigBit=bit;
    p->mp_SigTask=FindTask(NULL);
}
static void message(struct UiControl *m, UWORD command, ULONG value, struct MsgPort *reply)
{
    memset(m,0,sizeof(*m));
    m->message.mn_Length=UI_CONTROL_BYTES;
    m->message.mn_ReplyPort=reply;
    m->version=UI_VERSION;
    m->session=boot.session;
    m->command=command;
    m->value=value;
}
static void requestExit(void)
{
    if (exitSent) return;
    boot.exitRequested=1;
    message(&exitMessage,UI_EXIT,0,&exitReplies);
    exitSent=1;
    PutMsg(&rootPort,&exitMessage.message);
    Signal(boot.root,boot.rootMask);
}
static void failure(UWORD status)
{
    if (!boot.result) boot.result=status;
    requestExit();
}
static UWORD finishGraphics(void)
{
    UWORD status=GEM_OK;
    UiEventsClose();
    PROBE(4);
    if (input.state==INPUT_ACTIVE) check(InputRelease(&input)==INPUT_OK);
    if (inputBit>=0) { FreeSignal(inputBit); inputBit=-1; }
    if (client.pending) status=GemCollect(&client);
    if (client.session) status=GemClose(&client);
    if (server.state==GEM_RUNNING) status=GemServiceStop(&server);
    if (client.server) check(GemClientDispose(&client)==GEM_OK);
    return status;
}
static UWORD startGraphics(void)
{
    UWORD status=boot.result;
    PROBE(1);
    if (!status) status=GemClientInit(&client,&server);
    if (!status) status=GemOpen(&client);
    if (!status) {
        inputBit=AllocSignal(-1);
        if (inputBit<0) status=GEM_NO_MEMORY;
    }
    if (!status) {
        config.version=INPUT_VERSION;
        config.source=INPUT_SOURCE_KEYBOARD;
        config.wakeMask=1UL<<inputBit;
        config.filter0Value=0x1c;
        config.filter0Mask=0x3f;
        config.filterCount=1;
        config.flags=INPUT_CAPTURE_BREAK;
        status=InputAcquire(&input,&config);
    }
    if (!status) status=InputCreateRoute(&input,0,&route);
    if (!status) status=InputPublishRoute(&input,route);
    if (status) { finishGraphics(); PROBE(2); return status; }
    UiEventsOpen();
    dirty=511;
    return GEM_OK;
}
static UWORD controls(void)
{
    UWORD n;
    for (n=0;n<8;++n) {
        struct UiControl *m=(struct UiControl *)GetMsg(&appPort);
        if (!m) break;
        if ((m!=&control && m!=&progressMessage && m!=&diskMessage) ||
            m->message.mn_Length!=UI_CONTROL_BYTES || m->version!=UI_VERSION ||
            m->session!=boot.session || m->reserved || !ExecSameAddress(m->message.mn_ReplyPort,&rootReplies)) {
            /* Never accept/free foreign storage as one of our four slots. */
            check(0); failure(GEM_BAD_PACKET); continue;
        }
        m->result=GEM_OK;
        if (m==&control && m->command==UI_START && !startMessage && !initialReady && !boot.exitRequested) {
            m->result=startGraphics();
            if (!m->result) { startMessage=m; continue; }
            failure(m->result);
        } else if (m==&control && m->command==UI_STOP) requestExit();
        else if (m==&progressMessage && m->command==UI_PROGRESS && m->value<=2048) {
            diskProgress=(UWORD)m->value;
            dirty|=64;
        } else if (m==&diskMessage && m->command==UI_DISK_DONE) {
            boot.diskDone=1;
            dirty|=256;
            if (m->value) failure((UWORD)m->value);
        } else { m->result=GEM_BAD_PACKET; failure(m->result); }
        ReplyMsg(&m->message);
    }
    return n;
}
static UWORD decode(struct InputEvent *e)
{
    UWORD code=e->code, index=code&63, value;
    if (lastValid && lastCode==code && lastTick==e->tick) return 0;
    lastValid=1; lastCode=code; lastTick=e->tick;
    if (index==60) { caps^=1; return 0; }
    value=normalKeys[index];
    if (code&128) return 0;
    if (value>='a' && value<='z') {
        if (caps^((code>>6)&1)) value-=32;
    } else if ((code&64) && value>=32) value=shiftedKeys[index];
    return value;
}
static void activate(UWORD target)
{
    if (target==1) { ++count; dirty|=16; }
    else if (target==2) requestExit();
}
static WORD hit(WORD x, WORD y)
{
    if (y>=52 && y<=72 && x>=32 && x<224) return 0;
    if (y>=92 && y<=112 && x>=32 && x<96) return 1;
    if (y>=92 && y<=112 && x>=176 && x<240) return 2;
    return -1;
}
static void pointerEvent(struct InputEvent *e)
{
    WORD target=hit(e->x,e->y);
    ++pointerEvents;
    pointerX=e->x; pointerY=e->y; pointerVisible=pointerDirty=1;
    if (!pointerReady) {
        if (!e->buttons) { pointerReady=1; pointerButtons=0; }
        return;
    }
    if (e->kind==INPUT_EVENT_BUTTON) {
        if (e->buttons && !pointerButtons) {
            armed=target;
            if (target>=0) { focus=target; dirty|=62; }
        } else if (!e->buttons && pointerButtons) {
            if (armed>=0 && armed==target) { ++pointerActivations; activate(target); }
            armed=-1;
        }
    } else if (e->buttons!=pointerButtons) {
        /* A state change without its BUTTON record cannot complete a click. */
        armed=-1;
    }
    pointerButtons=e->buttons;
}
static void keyEvent(struct InputEvent *e)
{
    UWORD key;
    if (e->acquisition!=input.acquisition || e->route!=route) return;
    if (boot.exitRequested) return;
    if (e->kind==INPUT_EVENT_LOSS) { armed=-1; pointerReady=0; ++inputLosses; return; }
    if (e->kind==INPUT_EVENT_POINTER || e->kind==INPUT_EVENT_BUTTON) { pointerEvent(e); return; }
    ++received;
    if (client.pending) ++inputWhilePending;
    lastCapture=e->tick; lastConsume=DisplayTicks();
    if (e->kind==INPUT_EVENT_CANCEL) { armed=-1; pointerReady=0; requestExit(); return; }
    if (e->kind!=INPUT_EVENT_KEY) return;
    key=decode(e);
    if (key==9) { focus=(focus+1)%3; dirty|=62; }
    else if (key==10 || key==13) activate(focus);
    else if (!focus && key==8 && length) { text[--length]=0; dirty|=14; }
    else if (!focus && key>=32 && key<127 && length<24) { text[length++]=(UBYTE)key; dirty|=14; }
}
/* Each tile is one immutable packet. Construct payload in its final owned
 * storage; the renderer never observes temporary stack arrays or live text. */
static UWORD paint(void)
{
    enum { DATA=GEM_REQUEST_BYTES+4*GEM_COMMAND_BYTES };
    static const struct GemCommand commands[4]={
        {25,0,0,1,0,DATA}, {11,1,2,0,DATA+2,0},
        {22,0,0,1,0,DATA+10}, {8,0,1,8,DATA+12,DATA+16}
    };
    WORD *values;
    const char *label;
    UWORD i,tile,status,x,y,pen=0;
    for (tile=0;tile<9;++tile) if (dirty&(1<<tile)) break;
    if (tile==9) return GEM_OK;
    status=GemPrepare(&client,GEM_OP_SUBMIT,4,4*GEM_COMMAND_BYTES+32);
    if (status) return status;
    memcpy(client.packet+1,commands,sizeof(commands));
    values=(WORD *)((UBYTE *)client.packet+DATA);
    label=tile==0 ? "GEM/Exec" : tile==4 ? "Count000" : tile==5 ? "Exit    " :
          tile==6 ? "Disk000%" : tile==7 ? "Tab/Ente" : boot.diskDone ? "Done    " : "Reading ";
    x=tile>=1 && tile<=3 ? 32+(tile-1)*64 : tile==5 ? 176 : 32;
    y=tile==0 ? 24 : tile<=3 ? 64 : tile<=5 ? 104 : tile==6 ? 144 : tile==7 ? 168 : 184;
    if (tile==4) pen=2+count%14;
    if ((tile>=1 && tile<=3 && focus==0) || (tile==5 && focus==2)) pen=6;
    values[0]=pen;
    values[1]=x; values[2]=y-10; values[3]=x+63; values[4]=y-8;
    values[5]=tile==4 && focus==1 ? 2 : 1;
    values[6]=x; values[7]=y;
    for (i=0;i<8;++i) {
        UWORD glyph=label[i];
        if (tile>=1 && tile<=3) glyph=(tile-1)*8+i<length ? text[(tile-1)*8+i] : ' ';
        values[8+i]=glyph;
    }
    if (tile==4 || tile==6) {
        UWORD value=tile==4 ? count%1000 : diskProgress*100UL/2048;
        UWORD start=tile==4 ? 13 : 12;
        values[start]='0'+value/100;
        values[start+1]='0'+value/10%10;
        values[start+2]='0'+value%10;
    }
    status=GemSubmit(&client);
    if (!status) {
        dirty&=~(1<<tile); renderTile=tile; cursorTurn=0; ++submitted;
        lastSubmit=DisplayTicks(); maxCommands=4; maxGlyphs=8;
    }
    return status;
}
void GemApplication(void)
{
    struct Task *self=FindTask(NULL);
    UWORD status,n,ready,busy;
    check(ExecSameAddress(self->tc_UserData,&boot));
    check(GemAddressExtent(&boot,sizeof(boot)));
    check(boot.version==UI_VERSION && boot.session);
    check(boot.app==self);
    check(boot.appLease.task==self);
    check(ExecSameAddress(boot.appLease.identity,&boot.appLease));
    check(ExecSameAddress(boot.rootPort,&rootPort) && rootPort.mp_SigTask==boot.root);
    check(RetainTask(self,&selfLease) && RetainTask(boot.root,&rootLease));
    /* A fresh Task has all user bits free. Reserve the handshake before any
     * fallible service/input allocation; both embedded ports share this bit. */
    appBit=AllocSignal(-1); check(appBit>=16);
    port(&appPort,appBit); port(&exitReplies,appBit);
    boot.appPort=&appPort;
    PROBE(0);
    boot.result=GemServiceStart(&server,&GemVbxeBackend);
    PROBE(2);
    PROBE(3);
    boot.ready=1;
    Signal(boot.root,boot.rootMask);
    for (;;) {
        busy=controls();
        if (input.state==INPUT_ACTIVE) {
            for (n=0;n<8;++n) {
                status=InputTake(&input,&event);
                if (status==INPUT_EMPTY) break;
                if (status) { failure(status); break; }
                UiPostCaptured(&event); ++busy;
            }
        }
        for (n=0;n<8;++n) {
            if (UiTakeEvent(&event)==INPUT_EMPTY) break;
            keyEvent(&event); ++busy;
        }
        if (client.pending) {
            status=GemTryCollect(&client,&ready);
            if (status) failure(status);
            if (ready) { ++collected; lastComplete=DisplayTicks(); ++busy; }
        }
        if (startMessage && ((!dirty && !client.pending) || boot.exitRequested)) {
            initialReady=!boot.exitRequested;
            startMessage->result=boot.result;
            ReplyMsg(&startMessage->message); startMessage=NULL;
        }
        if (boot.exitRequested && boot.diskDone && !client.pending) break;
        if (!boot.exitRequested && client.session && (dirty || pointerDirty) && !client.pending) {
            if (pointerDirty && (!dirty || !cursorTurn)) {
                status=GemPrepareCursor(&client,pointerX,pointerY,pointerVisible);
                if (!status) status=GemSubmit(&client);
                if (!status) { pointerDirty=0; cursorTurn=1; ++submitted; ++cursorPackets; lastSubmit=DisplayTicks(); }
            } else status=paint();
            if (status) failure(status);
            ++busy;
        }
        inputPending=0;
        if (input.state==INPUT_ACTIVE) check(InputPending(&input,&inputPending)==INPUT_OK);
        if (busy || inputPending || UiEventsPending() || !IsListEmpty(&appPort.mp_MsgList) ||
            (client.pending && !IsListEmpty(&client.replies->mp_MsgList))) ExecYield();
        else Wait(mask(&appPort) | (inputBit<0 ? 0 : 1UL<<inputBit) |
                  (client.pending ? mask(client.replies) : 0));
    }
    status=finishGraphics();
    if (status && !boot.result) boot.result=status;
    check(WaitPort(&exitReplies)==&exitMessage.message);
    check(GetMsg(&exitReplies)==&exitMessage.message);
    check(IsListEmpty(&appPort.mp_MsgList) && !startMessage);
    boot.appPort=NULL;
    FreeSignal(appBit); appBit=-1;
    Forbid();
    boot.retired=1;
    Signal(boot.root,boot.rootMask);
    check(ReleaseTask(&rootLease)); check(ReleaseTask(&selfLease));
    RemTask(NULL);
}
static void collectRoot(void)
{
    struct Message *m;
    while ((m=GetMsg(&rootReplies))!=NULL) {
        if (m==&control.message) outstanding&=~1;
        else if (m==&progressMessage.message) outstanding&=~2;
        else if (m==&diskMessage.message) outstanding&=~4;
        else check(0);
    }
    if (!exitNotice) {
        m=GetMsg(&rootPort);
        if (m) {
            check(m==&exitMessage.message && exitMessage.session==boot.session &&
                  exitMessage.version==UI_VERSION && exitMessage.command==UI_EXIT);
            exitNotice=(struct UiControl *)m;
        }
    }
}
UWORD main(void)
{
    if (stage!=0 && (FindTask(NULL)!=boot.root || boot.retired)) return GEM_BAD_SESSION;
    if (stage==0) {
        if (boot.session) return GEM_BUSY;
        if (generation==0xffffffffUL) return GEM_EXHAUSTED;
        boot.version=UI_VERSION; boot.session=++generation;
        boot.root=FindTask(NULL); boot.rootPort=&rootPort;
        rootBit=AllocSignal(-1);
        if (rootBit<0) return GEM_NO_MEMORY;
        boot.rootMask=1UL<<rootBit;
        port(&rootPort,rootBit); port(&rootReplies,rootBit);
        Forbid();
        boot.app=CreateTask("GEM application",0,(APTR)GemApplication,2560UL);
        if (boot.app) {
            check(RetainTask(boot.app,&boot.appLease));
            boot.app->tc_UserData=&boot;
        }
        Permit();
        if (!boot.app) { FreeSignal(rootBit); rootBit=-1; return GEM_NO_MEMORY; }
        while (!boot.ready) Wait(boot.rootMask);
    } else if (stage==1 || stage==5) {
        collectRoot();
        while (outstanding&1) { Wait(boot.rootMask); collectRoot(); }
        message(&control,stage==1 ? UI_START : UI_STOP,0,&rootReplies);
        outstanding|=1; PutMsg(&appPort,&control.message);
        while (outstanding&1) { Wait(boot.rootMask); collectRoot(); }
        return control.result;
    } else if (stage==10 || stage==11) {
        PROBE(stage);
    } else if (stage==2) {
#ifdef GEM_DIAGNOSTIC
        if (variant==4 && !boot.exitRequested) {
            stage=5;
            return main();
        }
#endif
        progressWanted=rootValue;
        collectRoot();
        if (!(outstanding&2) && !boot.exitRequested) {
            message(&progressMessage,UI_PROGRESS,progressWanted,&rootReplies);
            outstanding|=2; PutMsg(&appPort,&progressMessage.message);
        }
    } else if (stage==3) {
        collectRoot();
        /* Final progress is published only after ownership of its slot returns. */
        while (outstanding&2) { Wait(boot.rootMask); collectRoot(); }
        if (!boot.exitRequested) {
            message(&progressMessage,UI_PROGRESS,progressWanted,&rootReplies);
            outstanding|=2; PutMsg(&appPort,&progressMessage.message);
        }
        message(&diskMessage,UI_DISK_DONE,rootValue,&rootReplies);
        outstanding|=4; PutMsg(&appPort,&diskMessage.message);
        while (!exitNotice || outstanding) { Wait(boot.rootMask); collectRoot(); }
        Forbid();
        check(ReleaseTask(&boot.appLease));
        ReplyMsg(&exitNotice->message);
        Permit();
        while (!boot.retired) Wait(boot.rootMask);
        check(IsListEmpty(&rootPort.mp_MsgList) && IsListEmpty(&rootReplies.mp_MsgList));
        boot.app=NULL;
        FreeSignal(rootBit); rootBit=-1;
        finished=1;
    }
    return failures ? GEM_BAD_PACKET : GEM_OK;
}
