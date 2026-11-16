/* A caller opens its cold frame/VDI grants while the manager waits on UPDATE. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <exec/display.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
volatile UWORD AdmissionRequest,AdmissionEntered,AdmissionResumed;
volatile UWORD AdmissionPainted,AdmissionGo,AdmissionX,AdmissionY;
static volatile UWORD peerReady,peerDone;
static ULONG peerWake;


static void check(BOOL okay,UWORD line)
{
    Forbid();
    ++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(t) check((t)!=0,__LINE__)

void AdmissionPeer(void)
{
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);
    peerWake=1UL<<bit;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    CHECK(ExecAESMouseProfile(-1)>=0);
    peerReady=1;
    Wait(peerWake);
    CHECK(ExecAESDetach());
    FreeSignal(bit);
    Forbid();peerDone=1;RemTask(NULL);
}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct Task *manager,*peer;
    WORD window,handle,in[11],out[57],rect[4],i,cw,ch,bw,bh,x,y,w,h;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    c=ExecAESContext(); manager=c->directory->owner;
    window=wind_create(NAME|CLOSER|MOVER,48,40,160,104);
    CHECK(window>0 && wind_open(window,48,40,160,104));
    CHECK(wind_update(BEG_UPDATE));
    CHECK(c->request.displayGrant==NULL);
    AdmissionRequest=1;
    Signal(manager,c->directory->mask);
    while (!AdmissionEntered || manager->tc_State!=TS_WAIT) ExecYield();
    CHECK(!AdmissionResumed);
    peer=CreateTask("caller registration",0,(APTR)AdmissionPeer,1312UL);
    CHECK(peer!=NULL);
    while (!peerReady) ExecYield();
    CHECK(!AdmissionResumed && manager->tc_State==TS_WAIT);
    CHECK(wind_set_str(window,WF_NAME,"Caller admission"));
    CHECK(c->request.displayGrant!=NULL && c->request.service==(struct MsgPort EXEC_PTR *)AESService);
    CHECK(!AdmissionResumed && manager->tc_State==TS_WAIT);
    for (i=0;i<11;++i) in[i]=1;
    in[6]=1;in[9]=0;in[10]=2;
    handle=graf_handle(&cw,&ch,&bw,&bh);
    v_opnvwk(in,&handle,out);
    CHECK(handle!=0 && ExecAESDiagnostic()==AES_OK);
    CHECK(DisplayDelegated()==1);
    CHECK(!AdmissionResumed && manager->tc_State==TS_WAIT);
    CHECK(wind_get(window,WF_WXYWH,&x,&y,&w,&h));
    AdmissionX=x+8;AdmissionY=y+8;
    rect[0]=x+8;rect[1]=y+8;
    rect[2]=x+15;rect[3]=y+15;
    CHECK(vsf_color(handle,4)==4);
    v_bar(handle,rect);
    CHECK(ExecAESDiagnostic()==AES_OK);
    AdmissionPainted=1;
    while (!AdmissionGo) ExecYield();
    v_clsvwk(handle);
    CHECK(ExecAESDiagnostic()==AES_OK && DisplayDelegated()==0);
    CHECK(wind_update(END_UPDATE));
    while (!AdmissionResumed) ExecYield();
    Signal(peer,peerWake);
    CHECK(wind_close(window) && wind_delete(window));
    while (!peerDone) ExecYield();
    CHECK(ExecAESDetach());
    return AESFailures ? AESFirstFailure : 0;
}

