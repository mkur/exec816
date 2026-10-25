/* Small binding regression: shared contexts, public/PB calls and live drawing. */
#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>
#include <clib/alib_protos.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure,AESReady,AESDone;
static struct Task *controller;
static ULONG wake;
static volatile WORD stop;
static WORD window,work[4];
static OBJECT menu[]={
    {-1,1,4,G_IBOX,0,0,0,0,0,640,240},
    {4,2,2,G_BOX,0,0,0x1100,0,0,640,11},
    {1,3,3,G_IBOX,0,0,0,8,0,424,11},
    {2,-1,-1,G_TITLE,0,0,(ULONG)"Test",0,0,64,11},
    {0,5,5,G_IBOX,0,0,0,0,11,640,229},
    {4,6,6,G_BOX,0,0,0x1100,8,0,96,11},
    {5,-1,-1,G_STRING,LASTOB,0,(ULONG)"Item",0,0,96,11}
};
static OBJECT box={-1,-1,-1,G_BOX,LASTOB,0,0x1172,32,48,32,16};

static void check(WORD okay,WORD line)
{
    Forbid();
    ++AESChecks;
    if (!okay) { ++AESFailures;if (!AESFirstFailure) AESFirstFailure=line; }
    Permit();
}
#define CHECK(x) check((x)!=0,__LINE__)

/* Separate public entry retained for passive timing, with no guest counters. */
WORD AESBindingProbe(WORD kind)
{
    WORD a,b,c,d,result;
    WORD control[5]={104,2,5,0,0},global[15],in[8],out[5]={0};
    LONG address;
    AESPB pb={control,global,in,out,&address,0};
    in[0]=window;in[1]=WF_WORKXYWH;
    switch (kind) {
    case 0: return wind_get(window,WF_WORKXYWH,&a,&b,&c,&d);
    case 1: aes_call(&pb);return out[0];
    case 2:
        if (!ExecAESBeginUpdate(window)) return 0;
        return wind_update(END_UPDATE);
    case 3:
        control[0]=107;control[1]=control[2]=1;
        in[0]=BEG_UPDATE;aes_call(&pb);result=out[0];
        in[0]=END_UPDATE;aes_call(&pb);return result && out[0];
    case 4: return menu_ienable(menu,6,1);
    case 5:
        control[0]=31;control[2]=control[3]=1;
        in[0]=6;in[1]=1;address=(LONG)(ULONG)menu;
        aes_call(&pb);return out[0] && (menu[6].ob_state&CHECKED);
    case 6: return objc_draw(&box,0,0,0,0,640,240);
    case 7:
        control[0]=42;control[1]=6;control[2]=control[3]=1;
        in[0]=in[1]=in[2]=in[3]=0;in[4]=640;in[5]=240;
        address=(LONG)(ULONG)&box;aes_call(&pb);return out[0];
    }
    return 0;
}

void AESClientOne(void)
{
    struct ExecAESContext *c;
    WORD id,a,b,w,h;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init();CHECK(id>0);c=ExecAESContext();
    AESReady=1;Signal(controller,wake);
    while (!stop) {
        CHECK(wind_get(0,WF_WORKXYWH,&a,&b,&w,&h) && a==0 && w==640);
        CHECK(ExecAESContext()==c && c->gemId==id && !c->busy);
        ExecYield();
    }
    CHECK(ExecAESDetach());
    Forbid();AESDone=1;Signal(controller,wake);RemTask(NULL);
}
void AESClientTwo(void) {}

UWORD AESRun(void)
{
    struct ExecAESContext *c;
    struct Task *peer;
    ULONG available=AvailMem(0),sequence;
    WORD kind,i,id,handle=1,input[11],output[57],words[8]={777,0,0,0,0,0,0,0};
    BYTE bit=AllocSignal(-1);
    CHECK(bit>=0);wake=1UL<<bit;controller=FindTask(NULL);
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    id=appl_init();CHECK(id>0);c=ExecAESContext();
    window=wind_create(NAME|CLOSER|MOVER,16,24,160,100);CHECK(window>0);
    CHECK(wind_open(window,16,24,160,100));
    CHECK(wind_get(window,WF_WORKXYWH,&work[0],&work[1],&work[2],&work[3]));
    for (i=0;i<10;++i) input[i]=1;input[10]=2;
    v_opnvwk(input,&handle,output);CHECK(handle!=0);
    CHECK(menu_bar(menu,1));
    peer=CreateTask("AES binding peer",0,(APTR)AESClientOne,1024UL);CHECK(peer!=0);
    while (peer && !AESReady) Wait(wake);
    {
        WORD full[4]={work[0],work[1],work[0]+work[2]-1,work[1]+work[3]-1};
        WORD part[4]={work[0]+4,work[1]+4,work[0]+11,work[1]+11};
        CHECK(ExecAESBeginUpdate(window));v_bar(handle,full);
        CHECK(ExecAESPainted(window,work[0],work[1],work[2],work[3]));CHECK(wind_update(END_UPDATE));
        CHECK(c->view->pixelsReady && c->view->paintEpoch!=0);
        CHECK(ExecAESBeginUpdate(window));CHECK(c->view->pixelsReady);
        CHECK(ExecAESInvalidate(window,0,0,0,0));CHECK(wind_update(END_UPDATE));
        CHECK(ExecAESBeginUpdate(window));CHECK(c->view->pixelsReady);
        CHECK(ExecAESInvalidate(window,part[0],part[1],8,8));CHECK(wind_update(END_UPDATE));
        CHECK(!c->view->pixelsReady);
        CHECK(ExecAESBeginUpdate(window));CHECK(!c->view->pixelsReady);
        CHECK(ExecAESInvalidate(window,part[0],part[1],8,8));v_bar(handle,part);
        CHECK(ExecAESPainted(window,part[0],part[1],8,8));CHECK(wind_update(END_UPDATE));
        CHECK(c->view->pixelsReady);
        CHECK(ExecAESBeginUpdate(window));CHECK(c->view->pixelsReady);
        CHECK(wind_update(END_UPDATE));
        CHECK(ExecAESBeginUpdate(window));CHECK(!c->view->pixelsReady);
        v_bar(handle,full);CHECK(ExecAESPainted(window,work[0],work[1],work[2],work[3]));
        CHECK(wind_update(END_UPDATE));
    }
    for (kind=0;kind<8;++kind) {
        if (kind>=6) CHECK(ExecAESBeginUpdate(window));
        for (i=0;i<8;++i) CHECK(AESBindingProbe(kind));
        if (kind>=6) {
            CHECK(ExecAESPaintedChanges(window));
            CHECK(wind_update(END_UPDATE));
        }
    }
    c->busy=1;sequence=c->sequence;
    CHECK(!AESBindingProbe(0) && c->diagnostic==AES_BUSY);
    CHECK(!AESBindingProbe(1) && c->diagnostic==AES_BUSY);
    CHECK(!AESBindingProbe(2) && c->diagnostic==AES_BUSY);
    CHECK(!AESBindingProbe(6) && c->diagnostic==AES_BUSY);
    CHECK(c->busy && c->sequence==sequence);c->busy=0;
    Forbid();
    CHECK(AESBindingProbe(0));
    CHECK(controller->tc_TDNestCnt==0);
    Permit();
    CHECK(controller->tc_TDNestCnt==-1);
    CHECK(appl_write(id,16,words));
    do { CHECK(evnt_mesag(words)); } while (words[0]!=777 && !AESFailures);
    CHECK(words[0]==777);
    stop=1;while (peer && !AESDone) Wait(wake);
    CHECK(menu_bar(menu,0));
    v_clsvwk(handle);
    CHECK(wind_close(window));CHECK(wind_delete(window));
    CHECK(appl_exit());CHECK(!AESBindingProbe(0) && c->diagnostic==AES_IDENTITY);
    CHECK(appl_init()>id);CHECK(ExecAESDetach());
    FreeSignal(bit);CHECK(AvailMem(0)==available);
    return AESFailures;
}
