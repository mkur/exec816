#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
static struct Task *controller,*peers[3];
static ULONG wake,peerWake[3];
static volatile UWORD ready,done;
static OBJECT tree={-1,-1,-1,G_BOX,LASTOB,0,0x00001100UL,0,0,160,80};
static WORD message[8],in[11]={1,1,1,1,1,1,1,1,1,1,2},out[57];
static WORD control[5]={51,9,1,0,0},global[15],args[9],reply[7];
static AESPB pb={control,global,args,reply,0,0};
static UWORD fault;

/* One-shot faults at the new owner's resource transitions. */
static BOOL fail(UWORD stage)
{
    if (fault!=stage) return FALSE;
    fault=0; ExecAESContext()->diagnostic=stage<5 ? AES_RESOURCE:AES_DISPLAY_ERROR;
    return TRUE;
}
void *AESFormAlloc(ULONG bytes,ULONG flags)
{ return fail(1) ? NULL:AllocMem(bytes,flags); }
WORD AESFormCreate(WORD kind,WORD x,WORD y,WORD w,WORD h)
{ return fail(2) ? -1:wind_create(kind,x,y,w,h); }
WORD AESFormOpen(WORD handle,WORD x,WORD y,WORD w,WORD h)
{ return fail(3) ? 0:wind_open(handle,x,y,w,h); }
void AESFormVDIOpen(WORD *in,WORD *handle,WORD *out)
{ if (fail(4)) *handle=0; else v_opnvwk(in,handle,out); }
WORD AESFormClose(WORD handle)
{ return fail(5) ? 0:wind_close(handle); }
WORD AESFormDelete(WORD handle)
{ return fail(6) ? 0:wind_delete(handle); }
extern BOOL ExecVDIClose(struct ExecAESContext *);
BOOL AESFormVDIClose(struct ExecAESContext *c)
{ return fail(7) ? FALSE:ExecVDIClose(c); }

static void check(BOOL okay)
{
    Forbid(); ++AESChecks;
    if (!okay) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; }
    Permit();
}
#define CHECK(t) check((t)!=0)

void AESClientOne(void)
{
    UWORD who=ready;
    BYTE bit=AllocSignal(-1);
    WORD w;
    CHECK(bit>=0); peerWake[who]=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); CHECK(appl_init()>0);
    w=wind_create(NAME|CLOSER|MOVER,32+who*96,32,96,64); CHECK(w>0);
    CHECK(wind_open(w,32+who*96,32,96,64));
    ++ready; Signal(controller,wake);
    Wait(peerWake[who]);
    CHECK(ExecAESDetach()); FreeSignal(bit);
    Forbid(); ++done; Signal(controller,wake); RemTask(NULL);
}
void AESClientTwo(void) { AESClientOne(); }

static void drain(void)
{
    WORD x,y,b,k,key,click;
    while (evnt_multi(MU_MESAG|MU_TIMER,0,0,0,0,0,0,0,0,0,0,0,0,0,
        message,0,0,&x,&y,&b,&k,&key,&click)&MU_MESAG) {}
}

static WORD start(WORD x,WORD y,WORD w,WORD h)
{ return form_dial(FMD_START,0,0,0,0,x,y,w,h); }
static WORD finish(void)
{ return form_dial(FMD_FINISH,0,0,0,0,0,0,0,0); }

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct ExecVDIWorkstation *workstation;
    WORD x,y,w,h,window,handle=1,id,i;
    ULONG available=AvailMem(0),base;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0); controller=FindTask(NULL); wake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService)); id=appl_init(); CHECK(id>0);
    c=ExecAESContext(); base=AvailMem(0);
    CHECK(form_center(&tree,&x,&y,&w,&h));
    CHECK(x==240 && y==92 && w==160 && h==80 && !c->view);
    CHECK(start(x,y,w,h)); CHECK(c->form && c->view->shown && c->workstation);
    CHECK(!start(x,y,w,h) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(form_dial(FMD_GROW,0,0,0,0,x,y,w,h));
    CHECK(wind_update(BEG_UPDATE)); CHECK(c->updateDepth==1);
    CHECK(objc_draw(&tree,0,8,x,y,w,h)); CHECK(wind_update(END_UPDATE));
    CHECK(form_dial(FMD_SHRINK,0,0,0,0,x,y,w,h));
    CHECK(finish()); CHECK(!c->form && !c->view && !c->workstation);
    CHECK(AvailMem(0)==base);
    CHECK(finish());
    for (i=1;i<=4;++i) {
        fault=i;
        CHECK(!start(x,y,w,h) && ExecAESDiagnostic()==AES_RESOURCE && !fault);
        CHECK(!c->form && !c->view && !c->workstation && AvailMem(0)==base);
    }
    for (i=5;i<=7;++i) {
        CHECK(start(x,y,w,h)); fault=i;
        CHECK(!finish() && ExecAESDiagnostic()==AES_DISPLAY_ERROR && !fault && c->form);
        CHECK(finish());
        CHECK(!c->form && !c->view && !c->workstation && AvailMem(0)==base);
    }
    CHECK(!start(0,0,160,80) && ExecAESDiagnostic()==AES_RESOURCE && !c->form);
    CHECK(wind_update(BEG_UPDATE)); CHECK(wind_update(BEG_UPDATE));
    CHECK(c->updateDepth==2 && !start(x,y,w,h) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_update(END_UPDATE)); CHECK(wind_update(END_UPDATE));
    CHECK(wind_update(BEG_MCTRL));
    CHECK(c->mouseDepth==1 && !start(x,y,w,h) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_update(END_MCTRL)); CHECK(!c->mouseDepth && !c->updateDepth);
    v_opnvwk(in,&handle,out); CHECK(handle>0); workstation=c->workstation;
    window=wind_create(NAME|CLOSER|MOVER,32,32,240,160); CHECK(window>0);
    CHECK(!start(x,y,w,h) && ExecAESDiagnostic()==AES_BUSY);
    CHECK(wind_open(window,32,32,240,160)); drain();
    CHECK(form_center(&tree,&x,&y,&w,&h));
    CHECK(x==72 && y==76);
    args[0]=FMD_START; args[5]=x; args[6]=y; args[7]=w; args[8]=h;
    aes_call(&pb); CHECK(reply[0]==1 && c->form);
    CHECK(c->view->handle==window && c->workstation==workstation);
    CHECK(wind_update(BEG_UPDATE)); CHECK(objc_draw(&tree,0,8,x,y,w,h));
    CHECK(wind_update(END_UPDATE));
    /* Exact application-message order survives a full published queue and a
     * separate already-deferred message. No self-message allocation is used. */
    for (i=0;i<8;++i) c->deferredMessage[i]=100+i;
    c->messagePending=1; c->deferredEpoch=c->deferredMenuEpoch=0;
    for (i=0;i<16;++i) { message[0]=200+i; CHECK(appl_write(id,16,message)); }
    CHECK(!appl_write(id,16,message) && ExecAESDiagnostic()==AES_RESOURCE);
    args[0]=FMD_FINISH; aes_call(&pb); CHECK(reply[0]==1);
    CHECK(!c->form && c->repairEpoch && c->view->handle==window && c->workstation==workstation);
    CHECK(evnt_mesag(message) && message[0]==100 && message[7]==107 && !c->messageEpoch);
    CHECK(evnt_mesag(message) && message[0]==WM_REDRAW && message[3]==window && c->messageEpoch);
    CHECK(message[4]==40 && message[5]==48 && message[6]==224 && message[7]==136);
    for (i=0;i<16;++i) {
        do { CHECK(evnt_mesag(message)); } while (c->messageEpoch);
        CHECK(message[0]==200+i);
    }
    CHECK(start(x,y,w,h)); CHECK(finish()); CHECK(c->repairEpoch);
    CHECK(wind_close(window)); CHECK(wind_open(window,32,32,240,160));
    drain(); CHECK(!c->repairEpoch && !c->messagePending);
    CHECK(wind_close(window)); CHECK(wind_delete(window)); v_clsvwk(handle);
    /* Three other application windows plus the native shell fill the desktop. */
    for (i=0;i<3;++i) {
        peers[i]=CreateTask("Form capacity",0,(APTR)AESClientOne,1024UL);
        CHECK(peers[i]!=NULL); while (ready<=i) Wait(wake);
    }
    base=AvailMem(0);
    CHECK(form_center(&tree,&x,&y,&w,&h));
    CHECK(!start(x,y,w,h) && ExecAESDiagnostic()==AES_RESOURCE);
    CHECK(!c->form && !c->view && !c->workstation && AvailMem(0)==base);
    for (i=0;i<3;++i) Signal(peers[i],peerWake[i]);
    while (done<3) Wait(wake);
    CHECK(start(x,y,w,h));
    /* Detach must finish an abandoned explicit session before ordinary exit. */
    CHECK(ExecAESDetach()); FreeSignal(bit);
    CHECK(AvailMem(0)==available);
    return AESFailures;
}
