/* A caller opens its cold frame/VDI grants while the manager waits on UPDATE. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <exec/display.h>
#include <hardware/console-bitmap.h>
LONG EXEC_CALL ExecAESFrameApply(ULONG value);
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
volatile UWORD AdmissionRequest,AdmissionEntered,AdmissionResumed;
volatile UWORD AdmissionPainted,AdmissionGo,AdmissionX,AdmissionY;
static volatile UWORD peerReady,peerDone;
static ULONG peerWake;
static volatile UWORD appDone,appResult;


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

static WORD workstation(void)
{
    WORD in[11],out[57],i,handle,cw,ch,bw,bh;
    for (i=0;i<11;++i) in[i]=1;
    in[6]=1;in[9]=0;in[10]=2;
    handle=graf_handle(&cw,&ch,&bw,&bh);
    v_opnvwk(in,&handle,out);
    return handle;
}

static OBJECT menu[] = {
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,3,G_IBOX,0,0,0,8,0,424,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Test",0,0,64,11},
    {0,5,5,G_IBOX,0,0,0,0,11,640,229},
    {4,6,6,G_BOX,0,0,0x1100,8,0,112,11},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Item",0,0,112,11}
};

static void roundtrip(WORD x,WORD y)
{
        struct ConsoleBitmapPacket p={0};
        p.operation=CON_BITMAP_DESKTOP;
        p.clipLeft=x+32;p.clipTop=y+8;p.clipRight=x+40;p.clipBottom=y+16;
        ExecAESFrameApply((ULONG)&p);
        CHECK(p.status==DISPLAY_OK);
        /* No popup is open: exercise the existing save-under VRAM region. */
        p.operation=CON_BITMAP_COPY_START;
        p.copy.source.offset=0;p.copy.source.pitch=320;
        p.copy.source.width=640;p.copy.source.height=240;
        p.copy.sourceX=x+8;p.copy.sourceY=y+8;
        p.copy.destination.offset=81920UL;p.copy.destination.pitch=4;
        p.copy.destination.width=8;p.copy.destination.height=8;
        p.copy.destinationX=0;p.copy.destinationY=0;
        p.copy.width=8;p.copy.height=8;
        ExecAESFrameApply((ULONG)&p);
        CHECK(p.status==DISPLAY_OK);
        p.copy.source=p.copy.destination;
        p.copy.sourceX=0;p.copy.sourceY=0;
        p.copy.destination.offset=0;p.copy.destination.pitch=320;
        p.copy.destination.width=640;p.copy.destination.height=240;
        p.copy.destinationX=x+32;p.copy.destinationY=y+8;
        ExecAESFrameApply((ULONG)&p);
        CHECK(p.status==DISPLAY_OK);
    }

static UWORD application(void)
{
    struct ExecAESContext *c;
    struct Task *manager,*peer;
    WORD window,handle,rect[4],x,y,w,h;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    c=ExecAESContext(); manager=c->directory->owner;
    window=wind_create(NAME|CLOSER|MOVER,48,40,160,104);
    CHECK(window>0);
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
    CHECK(wind_open(window,48,40,160,104));
    CHECK(menu_bar(menu,1));
    CHECK(wind_set_str(window,WF_NAME,"Caller admission"));
    CHECK(c->request.displayGrant!=NULL && c->request.service==(struct MsgPort EXEC_PTR *)AESService);
    CHECK(!AdmissionResumed && manager->tc_State==TS_WAIT);
    handle=workstation();
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
    roundtrip(x,y);
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


/* Exercise the full path in the production ordinary application stack class. */
void AdmissionApp(void)
{
    appResult=application();
    Forbid();appDone=1;RemTask(NULL);
}

UWORD AESRun(void)
{
    struct Task *app=CreateTask("caller exposure",0,(APTR)AdmissionApp,1312UL);
    CHECK(app!=NULL);
    if (!app) return 1;
    while (!appDone) ExecYield();
    return appResult;
}
