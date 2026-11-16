/* Caller-context hidden lifecycle, shared policy and transport boundaries. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <exec816/console.h>
#include <exec816/console-view.h>
#include <clib/alib_protos.h>

ULONG AESService,LifeNative,LifeResource,LifeWaiting,LifeNext,LifeBusy;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD LifeFailAlloc;
volatile UWORD LifePhase;
static struct Task *controller,*peer;
static ULONG wake,peerWake;
static volatile UWORD command,done,entered;
static WORD peerWindows[3];
static struct AESRequest *rootRequest;
#define NATIVE(i) (((volatile UWORD *)LifeNative)[i])
#define RESOURCE_FREE (!((volatile UWORD *)LifeResource)[2])
#define WAITING (*(volatile UBYTE *)LifeWaiting)

static void check(BOOL okay,UWORD line)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

APTR LifeAllocView(ULONG bytes,ULONG flags)
{
    if (LifeFailAlloc) { LifeFailAlloc=0;return NULL; }
    return AllocMem(bytes,flags);
}
void LifeFreeView(APTR view,ULONG bytes)
{ FreeMem(view,bytes); }

static WORD create(WORD index)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    BYTE nesting=self->tc_TDNestCnt;
    ULONG binding=(ULONG)c->request.service;
    WORD handle,in[5]={AES_WINDOW_KIND,33,24,129,64},out[1]={0};
    WORD control[5]={AES_OP_CREATE,5,1,0,0},global[15];
    AESPB pb={control,global,in,out,NULL,NULL};
    if (index&1) { aes_call(&pb);handle=out[0]; }
    else handle=wind_create(in[0],in[1],in[2],in[3],in[4]);
    CHECK(handle>0 && (ULONG)c->request.service==binding);
    CHECK(c->view && c->view->handle==handle && !c->view->shown && !c->view->epoch);
    CHECK(c->view->bounds.left==32 && c->view->bounds.right==162);
    CHECK(c->view->kind==AES_WINDOW_KIND && !c->busy);
    CHECK(FindTask(NULL)==self && self->tc_TDNestCnt==nesting);
    return handle;
}

static void remove_hidden(WORD handle,WORD parameterBlock)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    BYTE nesting=self->tc_TDNestCnt;
    ULONG binding=(ULONG)c->request.service;
    UWORD before=NATIVE(2),system=NATIVE(3),i,count=0;
    WORD control[5]={AES_OP_DELETE,1,1,0,0},global[15],out[1]={0};
    AESPB pb={control,global,&handle,out,NULL,NULL};
    for (i=0;i<AES_WINDOWS;++i) if (c->views[i]) ++count;
    if (parameterBlock) { aes_call(&pb);CHECK(out[0]); }
    else CHECK(wind_delete(handle));
    CHECK((ULONG)c->request.service==binding && NATIVE(2)==before+1 && NATIVE(3)==system);
    for (i=0;i<AES_WINDOWS;++i) if (c->views[i]) {
        CHECK(c->views[i]->handle!=handle);--count;
    }
    CHECK(count==1 && !c->busy);
    CHECK(FindTask(NULL)==self && self->tc_TDNestCnt==nesting);
}

void AESClientOne(void)
{
    struct ExecAESContext *c;
    UWORD i;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();AESReady=1;Signal(controller,wake);
    for (;;) {
        Wait(peerWake);
        if (command==1) {
            CHECK(wind_update(BEG_UPDATE));
            for (i=0;i<3;++i) peerWindows[i]=create(i);
            CHECK(wind_update(END_UPDATE));
        } else if (command==2) {
            while (!WAITING) ExecYield();
            CHECK(rootRequest->operation==AES_OP_CREATE ? rootRequest->view->handle==0 :
                rootRequest->view->handle==rootRequest->intin[0]);
            (*(volatile UBYTE *)LifeBusy)=0;
            Signal(c->directory->owner,c->directory->mask);
        } else if (command==3 || command==6) {
            entered=1;Signal(controller,wake);
            CHECK(wind_update(BEG_UPDATE));
            if (command==6) {
                CHECK(WAITING && rootRequest->view->handle==0);
            }
            CHECK(wind_update(END_UPDATE));
        } else if (command==4) {
            CHECK(wind_update(BEG_UPDATE));
            for (i=0;i<3;++i) remove_hidden(peerWindows[i],i&1);
            CHECK(wind_update(END_UPDATE));
        } else break;
        CHECK(c==ExecAESContext());done=command;Signal(controller,wake);
    }
    CHECK(ExecAESDetach());FreeSignal(bit);
    Forbid();AESDone=1;Signal(controller,wake);RemTask(NULL);
}
void AESClientTwo(void) {}

static void send(UWORD code)
{
    done=0;command=code;Signal(peer,peerWake);
    while (done!=code) Wait(wake);
}
static void stable(void) { CHECK(wind_update(BEG_UPDATE)); }
static void release(void) { CHECK(wind_update(END_UPDATE)); }

static void view_input(void)
{
    struct ExecAESContext *c=ExecAESContext();
    ULONG available=AvailMem(0),unit=ExecConsoleCreate(64,20),binding;
    ULONG view;
    WORD handle;
    CHECK(unit!=0);stable();binding=(ULONG)c->request.service;
    handle=wind_create(0,0,16,512,160);
    CHECK(handle>0 && (ULONG)c->request.service==binding);
    view=ExecConsoleViewSubscribe(unit,wake);CHECK(view!=0);
    CHECK(ExecConsoleViewBindWindow(view,handle)==EXEC_CONSOLE_VIEW_OK);
    binding=(ULONG)c->request.service;
    CHECK(wind_delete(handle));
    CHECK((ULONG)c->request.service==binding);
    CHECK(ExecConsoleViewUnsubscribe(view)==EXEC_CONSOLE_VIEW_OK);
    release();CHECK(ExecConsoleDestroy(unit));
    CHECK(AvailMem(0)==available);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct AESWindowView *saved;
    struct MsgPort *replies;
    ULONG available=AvailMem(0),before,binding;
    UWORD i,creates,system;
    WORD windows[3],reused,last;
    controller=FindTask(NULL);
    {
        BYTE bit=AllocSignal(-1);CHECK(bit>=0);wake=1UL<<bit;
    }
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();rootRequest=&c->request;
    peer=CreateTask("Hidden window peer",0,AESClientOne,1024);CHECK(peer!=NULL);
    while (!AESReady) Wait(wake);
    LifePhase=1;
    stable();
    for (i=0;i<3;++i) windows[i]=create(i);
    saved=c->view;replies=c->replies;
    binding=(ULONG)c->request.service;
    CHECK(wind_set_str(windows[0],WF_NAME,"Caller window"));
    CHECK((ULONG)c->request.service==binding); /* GF5 migrates bounded text. */
    CHECK(wind_set(windows[0],AES_WF_EXEC_PRESERVE,0,0,0,0));
    CHECK((ULONG)c->request.service==binding); /* Physical extension uses a system continuation. */
    release();send(1);stable();LifePhase=2;
    CHECK(NATIVE(0)==6 && NATIVE(1)==0);
    binding=(ULONG)c->request.service;creates=NATIVE(2);
    CHECK(!wind_delete(peerWindows[0]) && ExecAESDiagnostic()==AES_IDENTITY);
    CHECK((ULONG)c->request.service==binding && NATIVE(2)==creates);
    before=AvailMem(0);binding=(ULONG)c->request.service;c->visibleIndex=2;
    CHECK(wind_create(AES_WINDOW_KIND,32,24,128,64)==-1);
    CHECK(ExecAESDiagnostic()==AES_RESOURCE && (ULONG)c->request.service==binding);
    CHECK(AvailMem(0)==before && c->visibleIndex==2 && c->replies==replies);
    CHECK(saved->handle==windows[2] && !saved->epoch);
    release();send(4);stable();LifePhase=3;
    /* Allocation fails before scene admission and preserves selected storage. */
    creates=NATIVE(0);saved=c->view;before=AvailMem(0);binding=(ULONG)c->request.service;
    LifeFailAlloc=1;
    CHECK(wind_create(AES_WINDOW_KIND,32,24,128,64)==-1);
    CHECK(ExecAESDiagnostic()==AES_RESOURCE && NATIVE(0)==creates);
    CHECK(c->view==saved && c->request.view==saved && (ULONG)c->request.service==binding);
    CHECK(AvailMem(0)==before);
    CHECK(wind_create(AES_WINDOW_KIND,-1,24,128,64)==-1);
    CHECK(ExecAESDiagnostic()==AES_MALFORMED && (ULONG)c->request.service==binding);
    CHECK(AvailMem(0)==before && c->view==saved);
    remove_hidden(windows[1],0);
    reused=create(1);CHECK(reused>windows[2] && reused>peerWindows[2]);windows[1]=reused;
    /* A queued UPDATE cannot prevent its current owner from completing work. */
    LifePhase=4;done=entered=0;command=3;Signal(peer,peerWake);
    while (!entered || peer->tc_State!=TS_WAIT) ExecYield();
    last=create(0);CHECK(last>reused);
    release();while (done!=3) Wait(wake);
    stable();remove_hidden(last,1);release();
    /* The old lock must precede this window, without the window's barrier
     * preventing that predecessor from acquiring and releasing UPDATE. */
    LifePhase=5;stable();done=entered=0;command=6;Signal(peer,peerWake);
    while (!entered || peer->tc_State!=TS_WAIT) ExecYield();
    for (;;) { Forbid();if (RESOURCE_FREE) break;Permit();ExecYield(); }
    release();binding=(ULONG)c->request.service;system=NATIVE(1);
    last=wind_create(AES_WINDOW_KIND,32,24,128,64);
    CHECK(last>reused && (ULONG)c->request.service==binding && NATIVE(1)==system);
    CHECK(controller->tc_TDNestCnt==0);Permit();
    while (done!=6) Wait(wake);
    stable();remove_hidden(last,0);release();
    /* Forced readiness miss: one later caller commit, with an unapplied view. */
    LifePhase=6;(*(volatile UBYTE *)LifeBusy)=1;
    done=0;command=2;Signal(peer,peerWake);
    binding=(ULONG)c->request.service;system=NATIVE(1);
    last=wind_create(AES_WINDOW_KIND,32,24,128,64);
    CHECK(last>reused && (ULONG)c->request.service==binding && NATIVE(1)==system);
    while (done!=2) Wait(wake);
    stable();remove_hidden(last,1);release();
    /* Rejection preserves a shown view and its open epoch. */
    last=create(0);release();CHECK(wind_open(last,32,24,130,64));stable();
    saved=c->view;binding=(ULONG)c->request.service;
    CHECK(!wind_delete(last) && ExecAESDiagnostic()==AES_BUSY);
    CHECK((ULONG)c->request.service==binding && c->view==saved && saved->shown && saved->epoch);
    CHECK(wind_close(last));remove_hidden(last,1);release();
    /* Deletion's readiness miss also leaves its live view untouched until its caller resumes. */
    stable();last=create(0);release();
    (*(volatile UBYTE *)LifeBusy)=1;done=0;command=2;Signal(peer,peerWake);
    binding=(ULONG)c->request.service;system=NATIVE(3);CHECK(wind_delete(last));
    CHECK((ULONG)c->request.service==binding && NATIVE(3)==system);
    while (done!=2) Wait(wake);
    stable();
    for (i=0;i<3;++i) remove_hidden(windows[i],i&1);
    release();view_input();stable();
    /* Last representable identity is accepted once; exhaustion cannot alias. */
    LifePhase=8;*(volatile UWORD *)LifeNext=0x7fff;
    last=create(0);CHECK(last==0x7fff);
    before=AvailMem(0);binding=(ULONG)c->request.service;
    CHECK(wind_create(AES_WINDOW_KIND,32,24,128,64)==-1);
    CHECK(ExecAESDiagnostic()==AES_OVERFLOW && (ULONG)c->request.service==binding);
    CHECK(AvailMem(0)==before);remove_hidden(last,0);release();
    LifePhase=9;command=5;Signal(peer,peerWake);while (!AESDone) Wait(wake);
    CHECK(ExecAESDetach());
    for (i=0;i<32;++i) if (wake==(1UL<<i)) FreeSignal(i);
    CHECK(AvailMem(0)==available);
    LifePhase=10;
    return AESFailures;
}
