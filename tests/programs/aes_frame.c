/* Bounded frame policy, transport, publication and deferred feedback. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService,FrameNative,FrameBusy,FrameWaiting;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
volatile UWORD FramePhase,FrameGo,FramePoint,FrameHeld,FramePB;
WORD FrameField,FrameHandle,FrameResult,FrameStatus;
ULONG FrameSequence,FrameView;
static struct Task *controller,*peer;
static ULONG wake,peerWake;
static volatile UWORD command,finished;
static WORD rootWindow,peerWindow;
static struct AESWindowView *pendingView;
static UWORD pendingRevision;
extern void FrameCallBegin(void),FrameCallEnd(void),FrameRelease(void);

static void check(BOOL okay,UWORD line)
{
    Forbid();++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

static void attribute(WORD handle,WORD field,WORD value,char *text,
                      WORD pb,WORD held,WORD expected)
{
    struct ExecAESContext *c=ExecAESContext();
    struct Task *self=FindTask(NULL);
    BYTE nesting=self->tc_TDNestCnt;
    WORD control[5]={AES_OP_SET,6,1,0,0},global[15],in[6],out[1]={0};
    AESPB block={control,global,in,out,NULL,NULL};
    ULONG sequence,pointer=(ULONG)text;
    WORD result;
    if (held) CHECK(wind_update(BEG_UPDATE));
    in[0]=handle;in[1]=field;
    in[2]=(field==WF_NAME || field==WF_INFO) ? (WORD)(pointer>>16) : value;
    in[3]=(WORD)pointer;in[4]=in[5]=0;
    FrameHandle=handle;FrameField=field;FrameHeld=held;FramePB=pb;
    FramePoint=0;++FramePhase;
    while (FrameGo<FramePhase*3-2) ExecYield();
    sequence=c->sequence;
    FrameCallBegin();
    if (pb) { aes_call(&block);result=out[0]; }
    else if (field==WF_NAME || field==WF_INFO) result=wind_set_str(handle,field,text);
    else result=wind_set(handle,field,value,0,0,0);
    FrameCallEnd();
    FrameSequence=c->sequence-sequence;FrameResult=result;
    FrameStatus=ExecAESDiagnostic();FrameView=(ULONG)c->view;
    CHECK((result!=0)==(expected==AES_OK));CHECK(FrameStatus==expected);
    CHECK(!c->busy && FindTask(NULL)==self && self->tc_TDNestCnt==nesting);
    /* The admitted string must outlive the caller's scratch, by value. */
    if (text && field==WF_NAME && text[0]=='T') text[0]='X';
    FramePoint=3;
    while (FrameGo<FramePhase*3-1) ExecYield();
    FrameRelease();
    if (held) CHECK(wind_update(END_UPDATE));
    FramePoint=4;
    while (FrameGo<FramePhase*3) ExecYield();
}

void AESClientOne(void)
{
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    peerWindow=wind_create(AES_WINDOW_KIND|INFO|UPARROW|DNARROW|VSLIDE,
                          80,64,240,128);
    CHECK(peerWindow>0);AESReady=1;Signal(controller,wake);
    for (;;) {
        Wait(peerWake);
        if (command==1) CHECK(wind_open(peerWindow,80,64,240,128));
        else if (command==2) {
            attribute(peerWindow,WF_NAME,0,"Peer frame",1,1,AES_OK);
            attribute(peerWindow,WF_INFO,0,"Peer info",0,1,AES_OK);
            attribute(peerWindow,WF_VSLIDE,750,NULL,1,1,AES_OK);
            attribute(peerWindow,WF_VSLSIZE,250,NULL,0,1,AES_OK);
        } else if (command==3) CHECK(wind_close(peerWindow));
        else if (command==4) {
            while (!(*(volatile UBYTE *)FrameWaiting)) ExecYield();
            CHECK(pendingView->revision==pendingRevision);
            (*(volatile UBYTE *)FrameBusy)=0;
            Signal(ExecAESContext()->directory->owner,ExecAESContext()->directory->mask);
        } else break;
        finished=command;Signal(controller,wake);
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
    ULONG available=AvailMem(0),sequence;
    struct ExecAESContext *c;
    char limit[66];
    WORD plain,i;
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);wake=1UL<<bit;controller=FindTask(NULL);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));CHECK(appl_init()>0);
    c=ExecAESContext();
    rootWindow=wind_create(AES_WINDOW_KIND|INFO|UPARROW|DNARROW|VSLIDE,
                          32,32,240,160);
    CHECK(rootWindow>0);CHECK(wind_open(rootWindow,32,32,240,160));
    plain=wind_create(AES_WINDOW_KIND,360,32,120,64);CHECK(plain>0);
    peer=CreateTask("frame peer",0,AESClientOne,1024);CHECK(peer!=NULL);
    while (!AESReady) Wait(wake);
    attribute(rootWindow,WF_NAME,0,"Caller frame",0,1,AES_OK);
    attribute(rootWindow,WF_NAME,0,"Caller frame",1,1,AES_OK);
    attribute(rootWindow,WF_INFO,0,"Frame details",1,1,AES_OK);
    attribute(rootWindow,WF_INFO,0,"Frame details",0,1,AES_OK);
    for (i=0;i<64;++i) limit[i]='T';limit[64]=0;
    attribute(rootWindow,WF_NAME,0,limit,0,1,AES_OK);
    for (i=0;i<65;++i) limit[i]='T';limit[65]=0;
    attribute(rootWindow,WF_NAME,0,limit,1,1,AES_MALFORMED);
    attribute(rootWindow,WF_NAME,0,NULL,0,1,AES_MALFORMED);
    attribute(rootWindow,WF_INFO,0,(char *)0x1000000UL,1,1,AES_MALFORMED);
    attribute(rootWindow,WF_INFO,0,"",0,1,AES_OK);
    attribute(rootWindow,0x7fff,12,NULL,1,1,AES_UNSUPPORTED);
    attribute(rootWindow,WF_VSLIDE,250,NULL,0,1,AES_OK);
    attribute(rootWindow,WF_VSLIDE,250,NULL,1,1,AES_OK);
    attribute(rootWindow,WF_VSLSIZE,400,NULL,1,1,AES_OK);
    attribute(rootWindow,WF_VSLSIZE,400,NULL,0,1,AES_OK);
    attribute(rootWindow,WF_VSLIDE,1000,NULL,0,1,AES_OK);
    attribute(rootWindow,WF_VSLSIZE,0,NULL,1,1,AES_OK);
    attribute(rootWindow,WF_VSLIDE,-1,NULL,1,1,AES_MALFORMED);
    attribute(rootWindow,WF_VSLSIZE,1001,NULL,0,1,AES_MALFORMED);
    attribute(rootWindow,WF_INFO,0,limit,1,1,AES_MALFORMED);
    attribute(plain,WF_NAME,0,"Hidden frame",1,1,AES_OK);
    attribute(plain,WF_VSLIDE,100,NULL,0,1,AES_UNSUPPORTED);
    attribute(plain,WF_INFO,0,"Hidden info",0,1,AES_OK);
    send(1);
    attribute(rootWindow,WF_NAME,0,"Covered frame",0,1,AES_OK);
    attribute(rootWindow,WF_INFO,0,"Covered info",1,1,AES_OK);
    attribute(rootWindow,WF_VSLIDE,0,NULL,1,1,AES_OK);
    attribute(rootWindow,WF_VSLSIZE,400,NULL,0,1,AES_OK);
    send(2);send(3);
    attribute(rootWindow,WF_NAME,0,"Feedback title",0,0,AES_OK);
    attribute(rootWindow,WF_INFO,0,"Feedback info",1,0,AES_OK);
    attribute(rootWindow,WF_VSLIDE,500,NULL,0,0,AES_OK);
    attribute(rootWindow,WF_VSLSIZE,600,NULL,1,0,AES_OK);
    /* A readiness miss must leave publication untouched until the RPC retry. */
    CHECK(wind_update(BEG_UPDATE));pendingView=c->view;
    pendingRevision=pendingView->revision;CHECK(wind_update(END_UPDATE));
    pendingRevision=pendingView->revision;
    (*(volatile UBYTE *)FrameBusy)=1;finished=0;command=4;Signal(peer,peerWake);
    sequence=c->sequence;CHECK(wind_set_str(rootWindow,WF_INFO,"After readiness"));
    CHECK(c->sequence==sequence+1);
    while (finished!=4) Wait(wake);
    sequence=c->sequence;
    CHECK(!wind_set_str(peerWindow,WF_NAME,"Foreign"));
    CHECK(ExecAESDiagnostic()==AES_IDENTITY && c->sequence==sequence);
    command=5;Signal(peer,peerWake);while (!AESDone) Wait(wake);
    CHECK(ExecAESDetach());FreeSignal(bit);CHECK(AvailMem(0)==available);
    return AESFailures;
}
