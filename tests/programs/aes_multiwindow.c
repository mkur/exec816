#include <gem.h>
#include <exec816/aes.h>
#include <exec816/runtime.h>

ULONG AESService;
volatile UWORD AESChecks,AESFailures,AESFirstFailure;
#define CHECK(t) do { ++AESChecks; if (!(t)) { ++AESFailures; if (!AESFirstFailure) AESFirstFailure=AESChecks; } } while (0)
void AESClientOne(void) {}
void AESClientTwo(void) {}

static WORD message[8];
static void notice(WORD handle)
{
    do { CHECK(evnt_mesag(message)); } while (message[0]==WM_REDRAW && message[3]!=handle);
    CHECK(message[0]==WM_REDRAW && message[3]==handle);
}
UWORD AESRun(void)
{
    ULONG available=AvailMem(0),epoch;
    WORD a,b,back,x,y,w,h,i,reserved[3];
    struct ExecAESContext *c;
    struct AESWindowView *av,*bv;
    struct MsgPort *port;
    struct AESInputInbox *input;
    CHECK(ExecAESAttach((struct MsgPort *)AESService));
    CHECK(appl_init()>0);
    c=ExecAESContext();port=c->receiving;
    back=wind_create(0,0,16,640,224);CHECK(back>0);
    CHECK(ExecAESDesktop(back));CHECK(wind_open(back,0,16,640,224));
    notice(back);
    CHECK(wind_get(back,WF_WORKXYWH,&x,&y,&w,&h));
    CHECK(x==0 && y==16 && w==640 && h==224);
    a=wind_create(AES_WINDOW_KIND,16,32,200,120);CHECK(a>back);av=c->view;
    CHECK(wind_open(a,16,32,200,120));notice(a);
    b=wind_create(AES_WINDOW_KIND,96,64,200,120);CHECK(b>a);bv=c->view;
    CHECK(wind_open(b,96,64,200,120));notice(b);
    CHECK(av!=bv && av->epoch && bv->epoch!=av->epoch);
    CHECK(c->receiving==port);
    CHECK(wind_update(BEG_UPDATE));
    CHECK(av->updates==1 && bv->updates==1);
    CHECK(wind_get(a,WF_FIRSTXYWH,&x,&y,&w,&h));CHECK(c->view==av && w>0 && h>0);
    CHECK(wind_get(b,WF_FIRSTXYWH,&x,&y,&w,&h));CHECK(c->view==bv && x==104 && y==80 && w==184 && h==96);
    CHECK(wind_update(END_UPDATE));CHECK(!av->updates && !bv->updates);
    /* B has a pending GUI delivery when A closes. Its port/epoch survive. */
    CHECK(wind_set(b,WF_CURRXYWH,112,64,200,120));
    epoch=bv->epoch;
    /* Captured input for A is stale after close; B must remain consumable. */
    input=c->endpoint->input;
    Forbid();
    input->keyHead=0;input->keyTail=2;
    input->keys[0].epoch=input->keyEpoch;input->keys[0].window=a;
    input->keys[0].windowEpoch=av->epoch;input->keys[0].key=0x1e61;
    input->keys[1]=input->keys[0];input->keys[1].window=b;
    input->keys[1].windowEpoch=bv->epoch;input->keys[1].key=0x3062;
    Permit();
    CHECK(wind_close(a));CHECK(!av->epoch && bv->epoch==epoch);
    CHECK(c->endpoint->input->windowEpoch && c->receiving==port);
    CHECK(evnt_keybd()==0x3062);CHECK(ExecAESInputWindow(MU_KEYBD)==b);
    CHECK(input->keyHead==input->keyTail);
    notice(b);
    CHECK(wind_delete(a));CHECK(bv->handle==b);
    CHECK(wind_set(b,WF_CURRXYWH,128,64,200,120));
    CHECK(wind_close(b));CHECK(wind_open(b,128,64,200,120));
    CHECK(bv->epoch!=epoch);notice(b);
    /* Ordinary WM_REDRAW-shaped messages remain opaque after retirement. */
    message[0]=WM_REDRAW;message[3]=a;CHECK(appl_write(c->gemId,16,message));
    notice(a);
    /* Shell + background + B leaves three slots; no more Task registrations. */
    for (i=0;i<3;++i) { reserved[i]=wind_create(AES_WINDOW_KIND,16,32,200,120);CHECK(reserved[i]>0); }
    CHECK(wind_create(AES_WINDOW_KIND,16,32,200,120)==-1 && ExecAESDiagnostic()==AES_RESOURCE);
    for (i=0;i<3;++i) CHECK(wind_delete(reserved[i]));
    CHECK(wind_close(b));CHECK(wind_delete(b));
    CHECK(c->endpoint->input->windowEpoch && c->receiving==port);
    CHECK(wind_set(back,WF_TOP,0,0,0,0));
    CHECK(wind_update(BEG_UPDATE));CHECK(wind_get(back,WF_FIRSTXYWH,&x,&y,&w,&h));
    CHECK(wind_update(END_UPDATE));
    CHECK(wind_close(back));CHECK(wind_delete(back));
    CHECK(c->endpoint->input->windowEpoch==0);
    CHECK(ExecAESDetach());CHECK(AvailMem(0)==available);
    return AESFailures;
}
