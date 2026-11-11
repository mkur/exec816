/* Caller geometry/lookup, ownership and coherent published views. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService,GeoNative,GeoBusy,GeoWaiting,GeoLocks;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD GeoPhase,GeoGo,GeoPoint;
WORD GeoField,GeoHandle,GeoResult,GeoStatus;
ULONG GeoSequence,GeoView;
static struct Task *controller,*peer;
static ULONG wake,peerWake;
static volatile UWORD command,finished,entered;
static WORD rootWindow,peerWindow,hiddenWindow;
static struct AESWindowView *pendingView;
static ULONG pendingRevision;
extern void GeoCallBegin(void),GeoCallEnd(void);

static void check(BOOL okay,UWORD line)
{
    Forbid();++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

static void lookup(WORD x,WORD y,WORD expected,WORD pb)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    struct AESWindowView *selected=c->view;
    UWORD index=c->visibleIndex;
    BYTE nesting=self->tc_TDNestCnt;
    ULONG sequence=c->sequence;
    WORD control[5]={AES_OP_FIND,2,1,0,0},global[15],in[2],out[1]={-1};
    AESPB block={control,global,in,out,NULL,NULL};
    in[0]=x;in[1]=y;GeoField=AES_OP_FIND;GeoHandle=expected;GeoPoint=0;++GeoPhase;
    while (GeoGo<GeoPhase*2-1) ExecYield();
    GeoCallBegin();
    if (pb) { aes_call(&block);GeoResult=out[0]; }
    else GeoResult=wind_find(x,y);
    GeoCallEnd();GeoSequence=c->sequence-sequence;GeoStatus=ExecAESDiagnostic();
    GeoView=(ULONG)c->view;
    CHECK(GeoResult==expected && GeoStatus==AES_OK);
    CHECK(c->view==selected && c->visibleIndex==index && !c->busy);
    CHECK(FindTask(NULL)==self && self->tc_TDNestCnt==nesting);
    GeoPoint=3;while (GeoGo<GeoPhase*2) ExecYield();
}

static void bounds(WORD handle,WORD x,WORD y,WORD w,WORD h,WORD pb,WORD expected)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    BYTE nesting=self->tc_TDNestCnt;
    ULONG sequence=c->sequence;
    WORD control[5]={AES_OP_SET,6,1,0,0},global[15],in[6],out[1]={0};
    AESPB block={control,global,in,out,NULL,NULL};
    in[0]=handle;in[1]=WF_CXYWH;in[2]=x;in[3]=y;in[4]=w;in[5]=h;
    GeoField=WF_CXYWH;GeoHandle=handle;GeoPoint=0;++GeoPhase;
    while (GeoGo<GeoPhase*2-1) ExecYield();
    GeoCallBegin();
    if (pb) { aes_call(&block);GeoResult=out[0]; }
    else GeoResult=wind_set(handle,WF_CXYWH,x,y,w,h);
    GeoCallEnd();GeoSequence=c->sequence-sequence;GeoStatus=ExecAESDiagnostic();
    GeoView=(ULONG)c->view;
    CHECK((GeoResult!=0)==(expected==AES_OK) && GeoStatus==expected);
    CHECK(!c->busy && FindTask(NULL)==self && self->tc_TDNestCnt==nesting);
    GeoPoint=3;while (GeoGo<GeoPhase*2) ExecYield();
}

static void top(WORD handle,WORD pb,WORD expected)
{
    struct ExecAESContext *c=ExecAESContext();
    ULONG sequence=c->sequence;
    WORD control[5]={AES_OP_SET,6,1,0,0},global[15],in[6]={0},out[1]={0};
    AESPB block={control,global,in,out,NULL,NULL};
    in[0]=handle;in[1]=WF_TOP;
    GeoField=WF_TOP;GeoHandle=handle;GeoPoint=0;++GeoPhase;
    while (GeoGo<GeoPhase*2-1) ExecYield();
    GeoCallBegin();
    if (pb) { aes_call(&block);GeoResult=out[0]; }
    else GeoResult=wind_set(handle,WF_TOP,0,0,0,0);
    GeoCallEnd();GeoSequence=c->sequence-sequence;GeoStatus=ExecAESDiagnostic();
    GeoView=(ULONG)c->view;
    CHECK((GeoResult!=0)==(expected==AES_OK) && GeoStatus==expected);
    CHECK(!c->busy);GeoPoint=3;while (GeoGo<GeoPhase*2) ExecYield();
}

void AESClientOne(void)
{
    UWORD code;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    peerWindow=wind_create(AES_WINDOW_KIND|SIZER,80,64,240,128);
    CHECK(peerWindow>0);CHECK(wind_open(peerWindow,80,64,240,128));
    AESReady=1;Signal(controller,wake);
    for (;;) {
        Wait(peerWake);code=command;
        if (code==1) {
            CHECK(wind_update(BEG_UPDATE));entered=1;Signal(controller,wake);
            while (command==1) Wait(peerWake);
            CHECK(wind_update(END_UPDATE));
        } else if (code==2) {
            while (!(*(volatile UBYTE *)GeoWaiting)) ExecYield();
            CHECK(pendingView->revision==pendingRevision);
            (*(volatile UBYTE *)GeoBusy)=0;
            Signal(ExecAESContext()->directory->owner,ExecAESContext()->directory->mask);
        } else if (code==3) {
            CHECK(wind_update(BEG_UPDATE));
            bounds(peerWindow,96,72,240,128,1,AES_OK);
            top(peerWindow,0,AES_OK);
            CHECK(wind_update(END_UPDATE));
        } else break;
        finished=code;Signal(controller,wake);
    }
    CHECK(ExecAESDetach());FreeSignal(bit);
    Forbid();AESDone=1;Signal(controller,wake);RemTask(NULL);
}
void AESClientTwo(void) {}

static void send(UWORD code)
{
    finished=0;command=code;Signal(peer,peerWake);
    while (finished!=code) Wait(wake);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    WORD a,b,d,e;
    ULONG available=AvailMem(0),sequence;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);wake=1UL<<bit;controller=FindTask(NULL);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(!wind_find(0,0) && ExecAESDiagnostic()==AES_IDENTITY);
    CHECK(appl_init()>0);c=ExecAESContext();
    rootWindow=wind_create(AES_WINDOW_KIND|SIZER,32,32,240,160);
    CHECK(rootWindow>0);CHECK(wind_open(rootWindow,32,32,240,160));
    hiddenWindow=wind_create(AES_WINDOW_KIND,360,32,120,64);CHECK(hiddenWindow>0);
    peer=CreateTask("geometry peer",0,AESClientOne,1024);CHECK(peer!=NULL);
    while (!AESReady) Wait(wake);
    lookup(100,80,peerWindow,0);lookup(40,40,rootWindow,1);
    lookup(32,32,rootWindow,0);lookup(370,40,0,1);
    lookup(-1,-1,0,0);lookup(600,230,0,1);lookup(570,5,0,0);
    /* Neither logical ownership nor mutation readiness bars a coherent query. */
    command=1;Signal(peer,peerWake);while (!entered) Wait(wake);
    (*(volatile UBYTE *)GeoBusy)=1;
    lookup(100,80,peerWindow,1);lookup(40,40,rootWindow,0);
    (*(volatile UBYTE *)GeoBusy)=0;command=0;Signal(peer,peerWake);
    while (!finished) Wait(wake);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(wind_get(rootWindow,WF_FIRSTXYWH,&a,&b,&d,&e));
    bounds(rootWindow,48,40,240,160,0,AES_OK);
    CHECK(!wind_get(rootWindow,WF_NEXTXYWH,&a,&b,&d,&e));
    CHECK(ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_get(rootWindow,WF_FIRSTXYWH,&a,&b,&d,&e));
    bounds(rootWindow,48,40,248,168,1,AES_OK);
    bounds(rootWindow,-1,40,248,168,0,AES_MALFORMED);
    bounds(hiddenWindow,361,40,120,64,1,AES_OK);
    top(rootWindow,0,AES_OK);top(rootWindow,1,AES_OK);
    top(hiddenWindow,0,AES_MALFORMED);
    CHECK(wind_update(END_UPDATE));
    lookup(100,80,rootWindow,1);
    send(3);lookup(110,85,peerWindow,0);
    /* Readiness fallback cannot publish speculative bounds. */
    CHECK(wind_update(BEG_UPDATE));pendingView=c->view;
    CHECK(wind_update(END_UPDATE));pendingRevision=pendingView->revision;
    (*(volatile UBYTE *)GeoBusy)=1;finished=0;command=2;Signal(peer,peerWake);
    sequence=c->sequence;
    CHECK(wind_set(rootWindow,WF_CXYWH,48,40,256,176));
    CHECK(c->sequence==sequence);
    while (finished!=2) Wait(wake);
    sequence=c->sequence;
    CHECK(!wind_set(peerWindow,WF_TOP,0,0,0,0));
    CHECK(ExecAESDiagnostic()==AES_IDENTITY && c->sequence==sequence);
    command=4;Signal(peer,peerWake);while (!AESDone) Wait(wake);
    CHECK(ExecAESDetach());FreeSignal(bit);CHECK(AvailMem(0)==available);
    return AESFailures;
}
