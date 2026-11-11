/* GF7: caller visibility, route rollback and lifetime publication. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService,VisNative,VisBusy,VisFail,VisFocus,VisHold,VisHeld,VisRelease;
ULONG VisEpoch,VisWaiting,VisLocks,VisOwner,VisReady;
ULONG VisRetireBusy,VisEndpoint;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD VisPhase,VisGo,VisPoint,VisPeerHeld,VisPeerRelease,VisWake;
volatile UWORD VisPublisherHeld,VisPublisherGo,VisExitPending;
volatile UWORD VisQueue;
WORD VisOperation,VisResult,VisStatus;
ULONG VisSequence,VisView;
static volatile UWORD command,peerReady,peerDone;
static struct Task *controller,*peer;
static ULONG wake;
static WORD window;
/* Exercise the real producer hold across view deletion and destination exit. */
extern struct AESDelivery *ExecAESReserve(struct ExecAESContext *,WORD,
                                        struct AESEndpoint **);
extern void ExecAESPublish(struct ExecAESContext *,struct AESEndpoint *,
                           struct AESDelivery *);

static void check(BOOL okay,UWORD line)
{
    Forbid();++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

void AESClientOne(void)
{
    struct ExecAESContext *c;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();peerReady=1;
    for (;;) {
        if (VisWake) { VisWake=0;Signal(c->directory->owner,c->directory->mask); }
        if (VisQueue==1) {
            VisQueue=2;CHECK(wind_update(BEG_UPDATE));
            CHECK(wind_update(END_UPDATE));VisQueue=3;
        }
        if (command==2) break;
        if (command==1 && !peerDone && *(volatile UBYTE *)VisHeld) {
            CHECK(wind_update(BEG_UPDATE));VisPeerHeld=1;
            while (!VisPeerRelease) ExecYield();
            CHECK(wind_update(END_UPDATE));peerDone=1;
        }
        if (command==3) {
            struct AESEndpoint *destination;
            struct AESDelivery *delivery=ExecAESReserve(c,1,&destination);
            UWORD i;
            CHECK(delivery!=NULL);
            VisPublisherHeld=1;
            while (!VisPublisherGo) ExecYield();
            for (i=0;i<8;++i) delivery->words[i]=3000+i;
            ExecAESPublish(c,destination,delivery);
            command=0;
        }
        ExecYield();
    }
    CHECK(ExecAESDetach());
    Forbid();AESDone=1;Signal(controller,wake);RemTask(NULL);
}
void AESClientTwo(void) {}

static void call(UWORD phase,WORD operation,WORD pb,WORD x,WORD y,
                 WORD width,WORD height,WORD expected,WORD status)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    BYTE nesting=self->tc_TDNestCnt;
    WORD scoped=phase!=9 && phase!=11 && phase!=16 && phase!=18 && phase!=21;
    ULONG sequence;
    WORD in[5],out[1]={0},global[15],control[5]={0,0,1,0,0};
    AESPB block={control,global,in,out,NULL,NULL};
    /* Hold normal mutations stable against unrelated frame preparation.
     * The two admission-race cases deliberately remain unheld. */
    if (scoped) CHECK(wind_update(BEG_UPDATE));
    VisPhase=phase;VisPoint=0;VisOperation=operation;
    while (VisGo<phase*2-1) ExecYield();
    sequence=c->sequence;
    in[0]=window;in[1]=x;in[2]=y;in[3]=width;in[4]=height;
    if (pb) {
        control[0]=operation;control[1]=operation==AES_OP_OPEN ? 5:1;
        aes_call(&block);VisResult=out[0];
    } else if (operation==AES_OP_OPEN) VisResult=wind_open(window,x,y,width,height);
    else if (operation==AES_OP_DELETE) VisResult=wind_delete(window);
    else VisResult=wind_close(window);
    VisStatus=ExecAESDiagnostic();VisSequence=c->sequence-sequence;
    VisView=(ULONG)c->view;
    CHECK(VisResult==expected && VisStatus==status);
    CHECK(c->view && c->view->handle==window && !c->busy);
    CHECK(c==ExecAESContext() && FindTask(NULL)==self);
    CHECK(self->tc_TDNestCnt==nesting);
    VisPoint=3;
    while (VisGo<phase*2) ExecYield();
    if (scoped) CHECK(wind_update(END_UPDATE));
}

UWORD AESRun(void)
{
    ULONG available=AvailMem(0),epoch;
    BYTE bit;
    WORD i,message[8];
    struct ExecAESContext *c;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();controller=FindTask(NULL);bit=AllocSignal(-1);
    CHECK(bit>=0);wake=1UL<<bit;
    window=wind_create(AES_WINDOW_KIND|SIZER,32,24,160,80);CHECK(window>0);
    peer=CreateTask("Visibility peer",0,(APTR)AESClientOne,1024);CHECK(peer!=NULL);
    while (!peerReady) ExecYield();
    AESReady=1;
    call(1,AES_OP_OPEN,0,33,24,159,80,1,AES_OK);
    CHECK(c->view->shown && c->view->epoch);
    CHECK(c->view->bounds.left==32 && c->view->bounds.right==192);
    epoch=c->view->epoch;
    call(2,AES_OP_OPEN,1,32,24,160,80,0,AES_BUSY);
    CHECK(c->view->epoch==epoch);
    call(3,AES_OP_CLOSE,0,0,0,0,0,1,AES_OK);
    CHECK(!c->view->shown && !c->view->epoch);
    call(4,AES_OP_OPEN,1,40,32,160,80,1,AES_OK);
    CHECK(c->view->epoch>epoch);epoch=c->view->epoch;
    call(5,AES_OP_CLOSE,1,0,0,0,0,1,AES_OK);
    call(6,AES_OP_OPEN,0,-1,24,160,80,0,AES_MALFORMED);
    call(7,AES_OP_OPEN,1,32,24,160,80,0,AES_RESOURCE);
    call(8,AES_OP_OPEN,0,32,24,160,80,0,AES_OVERFLOW);
    command=1;
    call(9,AES_OP_OPEN,1,48,40,160,80,1,AES_OK);
    while (!peerDone) ExecYield();
    CHECK(VisPeerHeld && c->view->epoch>epoch);
    call(10,AES_OP_CLOSE,0,0,0,0,0,1,AES_OK);
    call(11,AES_OP_OPEN,0,32,24,160,80,1,AES_OK);
    call(12,AES_OP_CLOSE,1,0,0,0,0,1,AES_OK);
    call(13,AES_OP_OPEN,1,32,24,160,80,1,AES_OK);
    call(14,AES_OP_CLOSE,0,0,0,0,0,1,AES_OK);
    call(15,AES_OP_OPEN,0,32,24,160,80,1,AES_OK);
    call(16,AES_OP_CLOSE,1,0,0,0,0,1,AES_OK);
    call(17,AES_OP_OPEN,1,32,24,160,80,1,AES_OK);
    {
        ULONG sequence=c->sequence;
        c->sequence=0xfffffffeUL;
        call(18,AES_OP_CLOSE,0,0,0,0,0,0,AES_OVERFLOW);
        c->sequence=sequence;
    }
    CHECK(!c->view->shown && !c->view->epoch);
    call(19,AES_OP_OPEN,0,32,24,160,80,0,AES_BUSY);
    call(20,AES_OP_DELETE,0,0,0,0,0,0,AES_BUSY);
    call(21,AES_OP_CLOSE,0,0,0,0,0,1,AES_OK);
    call(22,AES_OP_OPEN,1,32,24,160,80,1,AES_OK);
    CHECK(wind_close(window));
    /* Full ordinary messages and stale GUI deliveries cannot pin an epoch. */
    CHECK(wind_open(window,32,24,160,80));epoch=c->view->epoch;
    for (i=0;i<16;++i) {
        message[0]=1000+i;CHECK(appl_write(c->gemId,16,message));
    }
    CHECK(wind_close(window));CHECK(wind_open(window,48,32,160,80));
    CHECK(c->view->epoch>epoch);
    for (i=0;i<16;++i) { CHECK(evnt_mesag(message));CHECK(message[0]==1000+i); }
    CHECK(evnt_mesag(message));CHECK(message[0]==WM_REDRAW && message[3]==window);
    VisEndpoint=(ULONG)c->endpoint;command=3;
    while (!VisPublisherHeld) ExecYield();
    CHECK(wind_close(window));CHECK(wind_delete(window));
    CHECK(ExecAESWindowView(window)==NULL);
    /* Exit also retires a replacement shown view while a producer is held. */
    window=wind_create(AES_WINDOW_KIND,32,24,160,80);CHECK(window>0);
    CHECK(wind_open(window,32,24,160,80));
    VisExitPending=1;CHECK(ExecAESDetach());
    while (command==3) ExecYield();
    command=2;while (!AESDone) Wait(wake);FreeSignal(bit);
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
