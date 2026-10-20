/* WB6: actual Exec signals and GUI/timer retirement at controlled boundaries. */
#include "../../c/calypsi/aes-private.h"
#include <exec816/program.h>
#include <exec816/runtime.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <clib/alib_protos.h>
#include <exec/memory.h>
#include <string.h>
ULONG AESService;
volatile UWORD AESWaitChecks,AESWaitFailures,AESWaitFirstFailure;
volatile UWORD AESWaitStage;
static UWORD phase,waits,cancels;
static ULONG externalA,externalB,doneMask;
static struct Task *controller;
static volatile UWORD peerDone;
static void check(WORD okay,UWORD line)
{ Forbid();++AESWaitChecks;if (!okay) { ++AESWaitFailures;if (!AESWaitFirstFailure) AESWaitFirstFailure=line; }Permit(); }
#define CHECK(x) check((x)!=0,__LINE__)
static void publish(struct ExecAESContext *c)
{
    struct AESEndpoint *endpoint;UWORD i;
    struct AESDelivery *record=ExecAESReserve(c,c->gemId,&endpoint);
    CHECK(record!=NULL);if (!record) return;
    for (i=0;i<8;++i) record->words[i]=777+i;
    ExecAESPublish(c,endpoint,record);
}
void AESWaitBeforeForbid(struct ExecAESContext *c)
{
    if (phase==1 || phase==4) {
        if (phase==4) { Forbid();c->endpoint->input->loss|=AES_INPUT_KEY;Permit(); }
        phase=0;Signal(FindTask(NULL),externalA);
    }
}
void AESWaitBeforeWait(struct ExecAESContext *c,ULONG mask)
{
    (void)mask;++waits;
    if (phase==2) { phase=0;Signal(FindTask(NULL),externalA); }
    if (phase==3) { phase=5;publish(c);Signal(FindTask(NULL),externalA); }
}
void AESWaitBeforeCancel(struct ExecAESContext *c)
{
    (void)c;++cancels;
    if (phase==5) { phase=0;Signal(FindTask(NULL),externalB); }
}
void AESWaitPeer(void)
{
    struct ExecAESWaitSpec s={0};BYTE bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService) && appl_init()>0);
    bit=AllocSignal(-1);CHECK(bit>=0);s.signalMask=1UL<<bit;
    Signal(FindTask(NULL),s.signalMask);
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==s.signalMask);
    FreeSignal(bit);CHECK(ExecAESDetach());
    Forbid();peerDone=1;Signal(controller,doneMask);RemTask(NULL);
}
LONG EXEC_CALL AESWaitRun(ULONG unused)
{
    struct ExecAESWaitSpec s={0};struct ExecAESContext *c;
    struct MsgPort *port;struct Message *message;struct ExecProgramResult outcome;
    ULONG available=AvailMem(0),child,mask,windowEpoch;BYTE a,b,d;UWORD before,i;
    WORD window,close[8]={WM_CLOSED,0,0,0,0,0,0,0};
    (void)unused;AESWaitStage=1;controller=FindTask(NULL);
    a=AllocSignal(-1);b=AllocSignal(-1);d=AllocSignal(-1);CHECK(a>=0 && b>=0 && d>=0);
    externalA=1UL<<a;externalB=1UL<<b;doneMask=1UL<<d;
    CHECK(ExecAESAttach((struct MsgPort *)AESService) && appl_init()>0);c=ExecAESContext();
    /* Already pending, coalesced and unrelated bits. No timer allocation. */
    AESWaitStage=2;s.signalMask=externalA;Signal(controller,externalA|externalB);Signal(controller,externalA);
    before=waits;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==externalA && waits==before);
    CHECK(!c->timer.opened && (SetSignal(0,externalB)&externalB));
    /* Ordinary messages on a caller-owned port are never dequeued by AES. */
    AESWaitStage=3;port=CreateMsgPort();message=AllocMem(sizeof(*message),MEMF_PUBLIC|MEMF_CLEAR);
    CHECK(port!=NULL && message!=NULL);message->mn_Length=sizeof(*message);
    PutMsg(port,message);s.signalMask=1UL<<port->mp_SigBit;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==s.signalMask);
    CHECK(GetMsg(port)==message && GetMsg(port)==NULL);DeleteMsgPort(port);FreeMem(message,sizeof(*message));
    AESWaitStage=4;s.signalMask=externalA;publish(c);Signal(controller,externalA);
    s.flags=MU_MESAG;
    CHECK((UWORD)ExecAESWait(&s)==(MU_EXEC|MU_MESAG) && s.received==externalA && s.message[0]==777);
    /* An arrival after the first snapshot is rechecked before sleep. */
    AESWaitStage=5;s.flags=0;phase=1;before=waits;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==externalA && waits==before);
    phase=2;before=waits;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==externalA && waits==before+1);
    /* GUI + external readiness freezes before the later timer-cancel arrival. */
    AESWaitStage=6;s.flags=MU_MESAG|MU_TIMER;s.milliseconds=60000;s.signalMask=externalA|externalB;
    phase=3;before=cancels;
    CHECK((UWORD)ExecAESWait(&s)==(MU_EXEC|MU_MESAG) && s.received==externalA && s.message[0]==777);
    CHECK(cancels==before+1 && c->timer.state==AES_ALARM_IDLE && GetMsg(c->timer.port)==NULL);
    s.flags=0;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==externalB);
    /* A controlled presenter admits an input epoch, then reports loss after
     * selection. No key or physical window rendering is part of this race. */
    Forbid();windowEpoch=c->endpoint->input->windowEpoch;c->endpoint->input->windowEpoch=1;Permit();
    AESWaitStage=7;s.flags=MU_KEYBD;s.signalMask=externalA;phase=4;
    CHECK(!ExecAESWait(&s) && ExecAESDiagnostic()==AES_INPUT_LOST && !s.received);
    Forbid();c->endpoint->input->windowEpoch=windowEpoch;Permit();
    s.flags=0;CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==externalA);
    /* Private transport/timer signals cannot be borrowed by this extension. */
    AESWaitStage=8;s.flags=MU_TIMER;s.milliseconds=0;s.signalMask=1UL<<c->receiving->mp_SigBit;
    CHECK(!ExecAESWait(&s) && ExecAESDiagnostic()==AES_MALFORMED);
    s.signalMask=1UL<<c->replies->mp_SigBit;
    CHECK(!ExecAESWait(&s) && ExecAESDiagnostic()==AES_MALFORMED);
    s.signalMask=1UL<<c->timer.port->mp_SigBit;
    CHECK(!ExecAESWait(&s) && ExecAESDiagnostic()==AES_MALFORMED);
    s.flags=0;s.signalMask=0;CHECK(!ExecAESWait(&s) && ExecAESDiagnostic()==AES_UNSUPPORTED);
    /* A retired Process needs no keypress, timer or second completion signal. */
    AESWaitStage=9;child=ExecStartProgram("SYS:CHILD",NULL);CHECK(child);
    mask=ExecProgramMask(child);CHECK(mask);
    for (i=0;i<2000 && !(SetSignal(0,0)&mask);++i) ExecYield();
    CHECK(i<2000);s.signalMask=mask;before=waits;
    CHECK((UWORD)ExecAESWait(&s)==MU_EXEC && s.received==mask && waits==before);
    CHECK(ExecCollectProgram(child,&outcome) && !outcome.primary && !outcome.secondary);
    CHECK(!ExecCollectProgram(child,&outcome));
    /* Close is delivered with the external event; its window remains owned
     * until the ordinary caller explicitly deletes it. */
    AESWaitStage=10;window=wind_create(NAME|CLOSER|MOVER,0,0,128,64);CHECK(window>=0);
    close[1]=c->gemId;close[3]=window;CHECK(appl_write(c->gemId,16,close));
    Signal(controller,externalA);s.flags=MU_MESAG;s.signalMask=externalA;
    CHECK((UWORD)ExecAESWait(&s)==(MU_EXEC|MU_MESAG) && s.received==externalA &&
        s.message[0]==WM_CLOSED && s.message[3]==window);
    CHECK(wind_delete(window));
    /* Another ordinary Task consumes the same public interface. */
    AESWaitStage=11;CHECK(CreateTask("AES Exec wait",0,(APTR)AESWaitPeer,1024UL)!=NULL);
    while (!peerDone) Wait(doneMask);
    CHECK(ExecAESDetach());FreeSignal(a);FreeSignal(b);FreeSignal(d);
    CHECK(AvailMem(0)==available);AESWaitStage=12;
    return AESWaitFailures;
}
